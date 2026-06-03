# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
FHIR Resource Map Compiler

Compiles a FHIR Resource Map (UI tables + custom_elements JSON) into a single,
self-contained ``compiled_mapping`` blueprint. The runtime consumes only this
blueprint and reads nothing else from the resource map.

Compiled shape::

    {
        "meta": {"resource_type", "primary_doctype", "fhir_version", "profiles"},
        "sources": {"<key>": {"doctype", "kind", "is_primary", "parent", "link_fieldname", "filters"}},
        "elements": {"<fhir_path>": {"source", "datatype", "is_array", "is_required", "value_spec"}},
    }

``value_spec`` mirrors the UI ``value_pointer``:
    - { "kind": "field",      "fieldname": "...", "default": <any?> }
    - { "kind": "fixed",      "value": <any>,     "default": <any?> }
    - { "kind": "expression", "expression": "..." }
    - { "kind": "json",       "value": <any> }
"""

import json

import frappe
from frappe.utils import cint

from healthcare.interoperability.doctype.fhir_resource_map.fhir_sd_loader import (
	FHIRStructureDefinitionLoader,
)

# primitive FHIR datatypes (lower-cased) the runtime knows how to coerce
PRIMITIVE_DATATYPES = {
	"string",
	"boolean",
	"integer",
	"decimal",
	"date",
	"datetime",
	"instant",
	"time",
	"uri",
	"url",
	"canonical",
	"code",
	"id",
	"oid",
	"uuid",
	"markdown",
	"base64binary",
	"positiveint",
	"unsignedint",
}


class FHIRCompiler:
	"""Compiles a FHIR Resource Map document into a compiled_mapping dict."""

	def __init__(self, resource_map):
		self.resource_map = resource_map
		self.warnings = []
		self._sd_index = {}
		self._custom = None

	def compile(self):
		"""Return ``(compiled_dict, warnings)``. Never raises on user-data issues."""
		self._sd_index = self._load_sd_index()
		self._custom = self._parse_json(self.resource_map.custom_elements) or {}

		compiled = {
			"meta": self._build_meta(),
			"sources": self._compile_sources(),
			"elements": self._compile_elements(),
		}

		self._validate(compiled)
		return compiled, self.warnings

	# =========================================================
	# Structure Definition index (for cardinality / datatype fallback)
	# =========================================================

	def _load_sd_index(self):
		index = {}
		if not self.resource_map.base_structure_definition:
			return index

		try:
			elements = FHIRStructureDefinitionLoader(resource_map=self.resource_map).load_merged_elements()
		except Exception as e:
			self.warnings.append(f"Could not load structure definition elements: {e!s}")
			return index

		for element in elements:
			path = (element.get("fhir_path") or "").strip()
			if path:
				index[path] = element
		return index

	# =========================================================
	# Meta
	# =========================================================

	def _build_meta(self):
		rm = self.resource_map
		fhir_version = None

		if rm.base_structure_definition:
			try:
				sd = frappe.get_cached_doc("FHIR Structure Definition", rm.base_structure_definition)
				fhir_version = getattr(sd, "fhir_version", None)
			except frappe.DoesNotExistError:
				self.warnings.append(f"Base structure definition '{rm.base_structure_definition}' not found.")

		profiles = []
		for row in rm.profiles or []:
			url = (getattr(row, "url", None) or "").strip()
			if url and url not in profiles:
				profiles.append(url)

		return {
			"resource_type": rm.resource_type,
			"primary_doctype": rm.primary_doctype,
			"fhir_version": fhir_version,
			"profiles": profiles,
		}

	# =========================================================
	# Sources
	# =========================================================

	def _compile_sources(self):
		sources = {}

		if self.resource_map.primary_doctype:
			sources["primary"] = {
				"doctype": self.resource_map.primary_doctype,
				"kind": "document",
				"is_primary": True,
				"parent": None,
				"link_fieldname": None,
				"filters": {},
			}

		for row in self.resource_map.sources or []:
			key = (row.source_key or "").strip()
			if not key:
				continue

			sources[key] = {
				"doctype": (row.source_doctype or "").strip(),
				"kind": self._normalize_kind(row.kind),
				"is_primary": False,
				"parent": "primary",
				"link_fieldname": (row.link_fieldname or "").strip() or None,
				"filters": self._parse_json(getattr(row, "config", None)) or {},
			}

		# custom_elements may declare additional sources (override UI on key clash)
		for source_def in self._custom.get("sources", []) or []:
			key = (source_def.get("key") or "").strip()
			if not key:
				continue
			sources[key] = {
				"doctype": (source_def.get("doctype") or "").strip(),
				"kind": self._normalize_kind(source_def.get("kind")),
				"is_primary": bool(source_def.get("is_primary")),
				"parent": source_def.get("parent") or source_def.get("parent_source_key") or "primary",
				"link_fieldname": source_def.get("link_fieldname") or source_def.get("link_field"),
				"filters": source_def.get("filters") or {},
			}

		return sources

	def _normalize_kind(self, kind):
		kind = (kind or "").strip().lower().replace(" ", "_")
		if kind in ("document", "child_table", "direct_link", "reverse_link"):
			return kind
		return "document"

	# =========================================================
	# Elements
	# =========================================================

	def _compile_elements(self):
		elements = {}

		for row in self.resource_map.element_maps or []:
			path = (row.fhir_path or "").strip()
			if not path:
				continue

			source, value_spec = self._element_value_spec(row)
			if value_spec is None:
				continue

			elements[path] = self._build_entry(path, source, value_spec, row)

		# custom_elements override / add (custom wins on path clash)
		for element_def in self._custom.get("elements", []) or []:
			path = (element_def.get("path") or element_def.get("fhir_path") or "").strip()
			if not path:
				continue
			elements[path] = self._build_custom_entry(path, element_def)

		return elements

	def _element_value_spec(self, row):
		"""Resolve (source_key, value_spec) for a UI element row.

		Prefers ``value_pointer`` JSON; falls back to the legacy columns.
		Returns (source_key, None) when the row carries no usable mapping.
		"""
		pointer = self._parse_json(getattr(row, "value_pointer", None))
		if isinstance(pointer, dict) and pointer.get("kind"):
			return self._spec_from_pointer(pointer)

		return self._spec_from_columns(row)

	def _spec_from_pointer(self, pointer):
		kind = (pointer.get("kind") or "").strip()
		source = (pointer.get("source_key") or "primary").strip() or "primary"

		if kind == "field":
			spec = {"kind": "field", "fieldname": self._clean_field(pointer.get("fieldname"))}
		elif kind == "fixed":
			spec = {"kind": "fixed", "value": pointer.get("value")}
		elif kind == "expression":
			spec = {"kind": "expression", "expression": pointer.get("expression")}
		elif kind == "json":
			spec = {"kind": "json", "value": pointer.get("value")}
		else:
			return source, None

		if pointer.get("default") is not None:
			spec["default"] = pointer.get("default")

		return source, spec

	def _spec_from_columns(self, row):
		mapping_type = (getattr(row, "mapping_type", None) or "").strip()
		source = (getattr(row, "source_name", None) or "primary").strip() or "primary"

		if mapping_type == "Frappe Field":
			field = self._clean_field(getattr(row, "frappe_field", None))
			spec = {"kind": "field", "fieldname": field} if field else None
		elif mapping_type == "Fixed":
			value = self._parse_json_or_text(getattr(row, "fixed_value", None))
			spec = {"kind": "fixed", "value": value} if value is not None else None
		elif mapping_type == "Expression":
			expr = (getattr(row, "expression", None) or "").strip()
			spec = {"kind": "expression", "expression": expr} if expr else None
		elif mapping_type == "JSON":
			value = self._parse_json(getattr(row, "fixed_value", None))
			spec = {"kind": "json", "value": value} if value is not None else None
		else:
			spec = None

		if spec is not None:
			default = self._parse_json_or_text(getattr(row, "default_value", None))
			if default is not None:
				spec["default"] = default

		return source, spec

	def _build_entry(self, path, source, value_spec, row):
		sd = self._sd_index.get(path, {})
		datatype = (getattr(row, "datatype", None) or sd.get("datatype") or "").strip()
		max_card = (str(getattr(row, "max", "") or "").strip()) or str(sd.get("max") or "").strip()
		min_card = cint(getattr(row, "min", None)) or cint(sd.get("min"))

		return {
			"source": source,
			"datatype": datatype,
			"is_array": self._is_array(max_card),
			"is_required": min_card >= 1,
			"value_spec": value_spec,
		}

	def _build_custom_entry(self, path, element_def):
		value_spec = element_def.get("value_spec")
		if not value_spec:
			value_spec = self._infer_custom_spec(element_def)

		sd = self._sd_index.get(path, {})
		datatype = (element_def.get("datatype") or sd.get("datatype") or "").strip()
		max_card = str(element_def.get("max") or sd.get("max") or "").strip()

		return {
			"source": element_def.get("source") or element_def.get("source_key") or "primary",
			"datatype": datatype,
			"is_array": bool(element_def.get("is_array")) or self._is_array(max_card),
			"is_required": bool(element_def.get("is_required")) or cint(sd.get("min")) >= 1,
			"value_spec": value_spec,
		}

	def _infer_custom_spec(self, element_def):
		"""Allow flat custom element definitions without a nested value_spec."""
		if element_def.get("fieldname") or element_def.get("field"):
			return {
				"kind": "field",
				"fieldname": self._clean_field(element_def.get("fieldname") or element_def.get("field")),
			}
		if "fixed" in element_def or "value" in element_def:
			return {"kind": "fixed", "value": element_def.get("fixed", element_def.get("value"))}
		if element_def.get("expression"):
			return {"kind": "expression", "expression": element_def.get("expression")}
		return None

	# =========================================================
	# Validation (warn-only)
	# =========================================================

	def _validate(self, compiled):
		elements = compiled.get("elements", {})
		sources = compiled.get("sources", {})
		mapped_paths = set(elements.keys())

		# required SD elements that are unmapped
		for path, sd in self._sd_index.items():
			if cint(sd.get("min")) < 1 or "[x]" in path:
				continue
			if path not in mapped_paths:
				self.warnings.append(f"Required element '{path}' is not mapped.")

		# mapped paths absent from the merged SD (typo / stale)
		if self._sd_index:
			for path in mapped_paths:
				if path not in self._sd_index and "[x]" not in path:
					self.warnings.append(f"Mapped element '{path}' is not in the merged StructureDefinition.")

		# elements pointing at undefined sources
		for path, element in elements.items():
			source_key = element.get("source")
			if source_key and source_key not in sources:
				self.warnings.append(f"Element '{path}' references unknown source '{source_key}'.")

		# sources referencing non-existent doctypes
		for key, source in sources.items():
			doctype = (source.get("doctype") or "").strip()
			if not doctype:
				self.warnings.append(f"Source '{key}' has no doctype.")
			elif not frappe.db.exists("DocType", doctype):
				self.warnings.append(f"Source '{key}' references non-existent doctype '{doctype}'.")

	# =========================================================
	# Helpers
	# =========================================================

	def _clean_field(self, field):
		if not field:
			return None
		return str(field).split("|")[0].strip()

	def _is_array(self, max_card):
		max_card = (str(max_card or "")).strip()
		if max_card == "*":
			return True
		try:
			return int(max_card) > 1
		except (ValueError, TypeError):
			return False

	def _parse_json(self, value):
		if not value:
			return None
		if isinstance(value, dict | list):
			return value
		try:
			return json.loads(value)
		except (json.JSONDecodeError, TypeError):
			self.warnings.append("Invalid JSON encountered while compiling.")
			return None

	def _parse_json_or_text(self, value):
		if value is None or value == "":
			return None
		if isinstance(value, dict | list):
			return value
		try:
			return json.loads(value)
		except (json.JSONDecodeError, TypeError):
			return value


def compile_fhir_resource_map(resource_map):
	"""Compile and return ``(compiled_dict, warnings)``."""
	return FHIRCompiler(resource_map).compile()
