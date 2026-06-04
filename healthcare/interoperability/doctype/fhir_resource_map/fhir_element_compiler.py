# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Element-level compilation for the FHIR Resource Map compiler.

Turns UI element rows and custom element definitions into compiled element
entries, and parses extension definitions. Kept separate from FHIRCompiler so
each module stays small and focused.
"""

import json

from frappe.utils import cint


def is_array(max_cardinality):
	max_cardinality = str(max_cardinality or "").strip()
	if max_cardinality == "*":
		return True
	try:
		return int(max_cardinality) > 1
	except (ValueError, TypeError):
		return False


def clean_field(field):
	if not field:
		return None
	return str(field).split("|")[0].strip()


def parse_json(value, warnings=None):
	if not value:
		return None
	if isinstance(value, dict | list):
		return value
	try:
		return json.loads(value)
	except (json.JSONDecodeError, TypeError):
		if warnings is not None:
			warnings.append("Invalid JSON encountered while compiling.")
		return None


def parse_json_or_text(value):
	if value is None or value == "":
		return None
	if isinstance(value, dict | list):
		return value
	try:
		return json.loads(value)
	except (json.JSONDecodeError, TypeError):
		return value


class ElementCompiler:
	"""Builds compiled element entries and extensions from UI rows / custom JSON."""

	def __init__(self, sd_index, warnings):
		self.sd_index = sd_index
		self.warnings = warnings

	# =========================================================
	# UI element rows
	# =========================================================

	def build_ui_element(self, row):
		path = (getattr(row, "fhir_path", None) or "").strip()
		if not path:
			return None, None

		source, value_spec = self._ui_value_spec(row)
		if value_spec is None:
			return None, None

		entry = self._entry(
			path,
			source,
			value_spec,
			datatype=getattr(row, "datatype", None),
			max_cardinality=getattr(row, "max", None),
			min_cardinality=cint(getattr(row, "min", None)),
		)
		if entry["datatype"].lower() == "reference":
			reference = self._reference_from_row(row)
			if reference:
				entry["reference"] = reference

		return path, entry

	def _ui_value_spec(self, row):
		pointer = parse_json(getattr(row, "value_pointer", None), self.warnings)
		if isinstance(pointer, dict) and pointer.get("kind"):
			return self._spec_from_pointer(pointer)
		return self._spec_from_columns(row)

	def _spec_from_pointer(self, pointer):
		kind = (pointer.get("kind") or "").strip()
		source = (pointer.get("source_key") or "primary").strip() or "primary"

		if kind == "field":
			spec = {"kind": "field", "fieldname": clean_field(pointer.get("fieldname"))}
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

		# optional inline code translation (local value -> FHIR code), authored in the UI
		mapping = pointer.get("map")
		if isinstance(mapping, dict) and mapping:
			spec["map"] = mapping

		return source, spec

	def _spec_from_columns(self, row):
		mapping_type = (getattr(row, "mapping_type", None) or "").strip()
		source = (getattr(row, "source_name", None) or "primary").strip() or "primary"

		if mapping_type == "Frappe Field":
			field = clean_field(getattr(row, "frappe_field", None))
			spec = {"kind": "field", "fieldname": field} if field else None
		elif mapping_type == "Fixed":
			value = parse_json_or_text(getattr(row, "fixed_value", None))
			spec = {"kind": "fixed", "value": value} if value is not None else None
		elif mapping_type == "Expression":
			expression = (getattr(row, "expression", None) or "").strip()
			spec = {"kind": "expression", "expression": expression} if expression else None
		elif mapping_type == "JSON":
			value = parse_json(getattr(row, "fixed_value", None))
			spec = {"kind": "json", "value": value} if value is not None else None
		else:
			spec = None

		if spec is not None:
			default = parse_json_or_text(getattr(row, "default_value", None))
			if default is not None:
				spec["default"] = default

		return source, spec

	# =========================================================
	# Custom element definitions
	# =========================================================

	def build_custom_element(self, element_def):
		path = (element_def.get("path") or element_def.get("fhir_path") or "").strip()
		if not path:
			return None, None

		value_spec = element_def.get("value_spec") or self._infer_spec(element_def)

		entry = self._entry(
			path,
			element_def.get("source") or element_def.get("source_key") or "primary",
			value_spec,
			datatype=element_def.get("datatype"),
			max_cardinality=element_def.get("max"),
			min_cardinality=0,
			force_array=bool(element_def.get("is_array")),
			force_required=bool(element_def.get("is_required")),
		)
		if entry["datatype"].lower() == "reference":
			reference = element_def.get("reference") or self._reference_from_keys(element_def)
			if reference:
				entry["reference"] = reference

		return path, entry

	def _infer_spec(self, element_def):
		"""Allow flat custom element / extension definitions without a nested value_spec."""
		if element_def.get("fieldname") or element_def.get("field"):
			fieldname = clean_field(element_def.get("fieldname") or element_def.get("field"))
			return {"kind": "field", "fieldname": fieldname}
		if "fixed" in element_def or "value" in element_def:
			return {"kind": "fixed", "value": element_def.get("fixed", element_def.get("value"))}
		if element_def.get("expression"):
			return {"kind": "expression", "expression": element_def.get("expression")}
		return None

	# =========================================================
	# Extensions
	# =========================================================

	def build_extension(self, extension_def, resource_type):
		url = (extension_def.get("url") or "").strip()
		if not url:
			self.warnings.append("Extension is missing 'url'.")
			return None

		return {
			"host": extension_def.get("host") or resource_type,
			"url": url,
			"value_type": extension_def.get("value_type") or "valueString",
			"source": extension_def.get("source") or extension_def.get("source_key") or "primary",
			"is_modifier": bool(extension_def.get("is_modifier")),
			"value_spec": extension_def.get("value_spec") or self._infer_spec(extension_def),
		}

	# =========================================================
	# Slices
	# =========================================================

	def build_slice(self, slice_def):
		path = (slice_def.get("path") or "").strip()
		if not path:
			self.warnings.append("Slice is missing 'path'.")
			return None

		return {
			"path": path,
			"slice_name": (slice_def.get("slice_name") or "").strip(),
			"source": slice_def.get("source") or slice_def.get("source_key") or "primary",
			"pattern": slice_def.get("pattern") or {},
			"elements": self._slice_elements(slice_def.get("elements", []) or []),
		}

	def _slice_elements(self, sub_defs):
		"""Sub-element mappings of a slice, with paths relative to the slice path."""
		elements = []
		for sub in sub_defs:
			rel_path = (sub.get("path") or sub.get("rel_path") or "").strip()
			value_spec = sub.get("value_spec") or self._infer_spec(sub)
			if not rel_path or not value_spec:
				continue

			entry = {
				"path": rel_path,
				"datatype": (sub.get("datatype") or "").strip(),
				"is_array": bool(sub.get("is_array")) or is_array(sub.get("max")),
				"value_spec": value_spec,
			}
			if entry["datatype"].lower() == "reference":
				reference = sub.get("reference") or self._reference_from_keys(sub)
				if reference:
					entry["reference"] = reference
			elements.append(entry)
		return elements

	# =========================================================
	# Shared entry / reference helpers
	# =========================================================

	def _entry(
		self,
		path,
		source,
		value_spec,
		datatype,
		max_cardinality,
		min_cardinality,
		force_array=False,
		force_required=False,
	):
		sd = self.sd_index.get(path, {})
		datatype = (datatype or sd.get("datatype") or "").strip()
		max_cardinality = (str(max_cardinality or "").strip()) or str(sd.get("max") or "").strip()
		required = force_required or min_cardinality >= 1 or cint(sd.get("min")) >= 1

		return {
			"source": source,
			"datatype": datatype,
			"is_array": force_array or is_array(max_cardinality),
			"is_required": required,
			"value_spec": value_spec,
		}

	def _reference_from_row(self, row):
		pointer = parse_json(getattr(row, "value_pointer", None)) or {}
		resource_type = pointer.get("reference_type") or self._type_from_targets(
			getattr(row, "target_profiles", None)
		)
		return self._reference_dict(resource_type, pointer.get("display_field"))

	def _reference_from_keys(self, element_def):
		resource_type = element_def.get("reference_type") or element_def.get("resource_type")
		return self._reference_dict(resource_type, element_def.get("display_field"))

	def _reference_dict(self, resource_type, display_field):
		reference = {}
		if resource_type:
			reference["resource_type"] = resource_type
		if display_field:
			reference["display_field"] = display_field
		return reference or None

	def _type_from_targets(self, targets):
		data = parse_json_or_text(targets)
		if isinstance(data, list) and data:
			url = data[0]
		elif isinstance(data, str):
			url = data
		else:
			return None

		segment = str(url).rstrip("/").split("/")[-1].strip()
		return segment or None
