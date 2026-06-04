# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
FHIR Resource Map Compiler

Compiles a FHIR Resource Map (UI tables + custom_elements JSON) into a single,
self-contained ``compiled_mapping`` blueprint that the runtime consumes on its
own. Element entries, references and extensions are built by ElementCompiler;
collection sources (child_table / reverse_link) carry ``is_collection`` and a
computed ``fhir_path`` (the repeating backbone they populate) so the runtime can
group rows without inspecting the StructureDefinition - source-driven grouping.
"""

import json

import frappe

from healthcare.interoperability.doctype.fhir_resource_map.fhir_element_compiler import (
	ElementCompiler,
	parse_json,
)
from healthcare.interoperability.doctype.fhir_resource_map.fhir_sd_loader import (
	FHIRStructureDefinitionLoader,
)
from healthcare.interoperability.doctype.fhir_resource_map.fhir_validator import MappingValidator

COLLECTION_KINDS = ("child_table", "reverse_link", "dynamic_link")


class FHIRCompiler:
	"""Compiles a FHIR Resource Map document into a compiled_mapping dict."""

	def __init__(self, resource_map):
		self.resource_map = resource_map
		self.warnings = []
		self._sd_index = {}
		self._custom = {}
		self._elements = None

	def compile(self):
		"""Return ``(compiled_dict, warnings)``. Never raises on user-data issues."""
		self._sd_index = self._load_sd_index()
		self._custom = self._parse_custom_elements()
		self._elements = ElementCompiler(self._sd_index, self.warnings)

		sources = self._compile_sources()
		elements = self._compile_elements()
		self._assign_collection_backbones(sources, elements)
		slices = self._compile_slices()

		compiled = {
			"meta": self._build_meta(),
			"sources": sources,
			"elements": elements,
			"extensions": self._compile_extensions(),
			"slices": slices,
			"array_paths": self._array_paths(sources, elements, slices),
		}

		self.warnings.extend(MappingValidator(self._sd_index).validate(compiled))
		return compiled, self.warnings

	# =========================================================
	# Structure Definition index (cardinality / datatype fallback)
	# =========================================================

	def _parse_custom_elements(self):
		raw = self.resource_map.custom_elements
		if not raw:
			return {}
		if isinstance(raw, dict):
			return raw
		try:
			return json.loads(raw)
		except (json.JSONDecodeError, TypeError) as e:
			self.warnings.append(f"custom_elements is not valid JSON: {e}")
			return {}

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
			sources["primary"] = self._source(self.resource_map.primary_doctype, "document", is_primary=True)

		for row in self.resource_map.sources or []:
			key = (row.source_key or "").strip()
			if not key:
				continue
			sources[key] = self._source(
				(row.source_doctype or "").strip(),
				self._normalize_kind(row.kind),
				link_fieldname=(row.link_fieldname or "").strip() or None,
				filters=parse_json(getattr(row, "config", None), self.warnings) or {},
			)

		for source_def in self._custom.get("sources", []) or []:
			key = (source_def.get("key") or "").strip()
			if not key:
				continue
			sources[key] = self._source(
				(source_def.get("doctype") or "").strip(),
				self._normalize_kind(source_def.get("kind")),
				is_primary=bool(source_def.get("is_primary")),
				parent=source_def.get("parent") or source_def.get("parent_source_key") or "primary",
				link_fieldname=source_def.get("link_fieldname") or source_def.get("link_field"),
				filters=source_def.get("filters") or {},
			)
			if source_def.get("fhir_path"):
				sources[key]["fhir_path"] = source_def["fhir_path"]

		return sources

	def _source(self, doctype, kind, is_primary=False, parent="primary", link_fieldname=None, filters=None):
		return {
			"doctype": doctype,
			"kind": kind,
			"is_primary": is_primary,
			"is_collection": kind in COLLECTION_KINDS,
			"parent": None if is_primary else parent,
			"link_fieldname": link_fieldname,
			"filters": filters or {},
		}

	def _normalize_kind(self, kind):
		kind = (kind or "").strip().lower().replace(" ", "_")
		if kind in ("document", *COLLECTION_KINDS, "direct_link"):
			return kind
		return "document"

	# =========================================================
	# Elements & extensions
	# =========================================================

	def _compile_elements(self):
		elements = {}

		for row in self.resource_map.element_maps or []:
			path, entry = self._elements.build_ui_element(row)
			if path:
				elements[path] = entry

		# custom_elements override / add (custom wins on path clash)
		for element_def in self._custom.get("elements", []) or []:
			path, entry = self._elements.build_custom_element(element_def)
			if path:
				elements[path] = entry

		return elements

	def _compile_extensions(self):
		extensions = []
		for extension_def in self._custom.get("extensions", []) or []:
			extension = self._elements.build_extension(extension_def, self.resource_map.resource_type)
			if extension:
				extensions.append(extension)
		return extensions

	def _compile_slices(self):
		slices = []
		for slice_def in self._custom.get("slices", []) or []:
			compiled_slice = self._elements.build_slice(slice_def)
			if compiled_slice:
				slices.append(compiled_slice)
		return slices

	# =========================================================
	# Collection backbones (source-driven grouping)
	# =========================================================

	def _assign_collection_backbones(self, sources, elements):
		for key, source in sources.items():
			if not source.get("is_collection") or source.get("fhir_path"):
				continue

			paths = [path for path, element in elements.items() if element.get("source") == key]
			backbone = self._backbone_path(paths)
			if backbone:
				source["fhir_path"] = backbone
			elif paths:
				self.warnings.append(f"Could not determine the repeating path for collection source '{key}'.")

	def _backbone_path(self, element_paths):
		if not element_paths:
			return None

		repeating = set()
		for path in element_paths:
			ancestors = self._repeating_ancestors(path, include_self=True)
			if ancestors:
				repeating.add(ancestors[0])
		if repeating:
			return min(repeating, key=lambda path: path.count("."))

		return self._common_parent(element_paths)

	def _common_parent(self, element_paths):
		common = []
		for segments in zip(*[path.split(".") for path in element_paths], strict=False):
			if len(set(segments)) == 1:
				common.append(segments[0])
			else:
				break

		if len(common) < 2:
			return None

		prefix = ".".join(common)
		if prefix in element_paths:
			prefix = prefix.rsplit(".", 1)[0]
		return prefix if prefix.count(".") >= 1 else None

	# =========================================================
	# Array paths (repeating complex backbones from single docs)
	# =========================================================

	def _array_paths(self, sources, elements, slices):
		"""Paths that must render as arrays from a single doc: explicit
		``custom_elements["arrays"]`` + repeating (max=*) SD ancestors of mapped
		paths. Collection backbones / slice paths already produce lists (excluded).
		"""
		explicit = {path for path in (self._custom.get("arrays") or []) if isinstance(path, str)}

		excluded = {source.get("fhir_path") for source in sources.values() if source.get("is_collection")}
		excluded |= {compiled_slice["path"] for compiled_slice in slices}

		derived = set()
		for path in self._mapped_object_paths(elements, slices):
			for ancestor in self._repeating_ancestors(path):
				if ancestor not in excluded:
					derived.add(ancestor)

		return sorted(explicit | derived)

	def _mapped_object_paths(self, elements, slices):
		paths = list(elements.keys())
		for compiled_slice in slices:
			for sub in compiled_slice.get("elements", []):
				paths.append(f"{compiled_slice['path']}.{sub['path']}")
		return paths

	def _repeating_ancestors(self, path, include_self=False):
		parts = path.split(".")
		end_limit = len(parts) + 1 if include_self else len(parts)
		ancestors = []
		for end in range(2, end_limit):
			prefix = ".".join(parts[:end])
			sd = self._sd_index.get(prefix)
			if sd and str(sd.get("max") or "").strip() == "*":
				ancestors.append(prefix)
		return ancestors


def compile_fhir_resource_map(resource_map):
	"""Compile and return ``(compiled_dict, warnings)``."""
	return FHIRCompiler(resource_map).compile()
