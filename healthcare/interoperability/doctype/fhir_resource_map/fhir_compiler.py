# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import frappe

from frappe.utils import cint, now_datetime


class FHIRMappingCompilationError(Exception):
	pass


class FHIRMappingCompiler:
	"""Compiles FHIR Resource Map into a runtime friendly mapping structure."""

	def __init__(self, resource_map):
		self.resource_map = resource_map
		self.resource_type = self.resource_map.resource_type
		self.primary_doctype = self.resource_map.primary_doctype
		self.base_structure_definition = self.resource_map.base_structure_definition

	def compile(self):
		self.validate_required_fields()

		sources = self.compile_sources()
		elements = self.compile_elements(sources)

		# Compile-time optimization:
		# Collapse leaf mappings that read from a child table into one container mapping
		# with value_spec.kind = "child_table_rows".
		elements = self.collapse_child_table_row_mappings(elements, sources)
		elements = self.collapse_object_group_mappings(elements)

		element_order = sorted(elements.keys())

		compiled = {
			"meta": {
				"primary_doctype": self.primary_doctype,
				"base_structure_definition": self.base_structure_definition,
				"resource_type": self.resource_type,
				"compiled_version": "fhir-map-compiled/v1",
				"compiled_at": str(now_datetime()),
			},
			"profiles": self.collect_profile_urls(),
			"sources": sources,
			"elements": elements,
			"element_order": element_order,
		}
		return compiled

	def validate_required_fields(self):
		if not self.primary_doctype:
			raise FHIRMappingCompilationError("primary_doctype is required.")
		if not self.resource_type:
			raise FHIRMappingCompilationError("resource_type is required.")

	# =========================================================
	# Sources
	# =========================================================

	def compile_sources(self):
		sources = {
			"primary": {
				"source_key": "primary",
				"kind": "primary",
				"doctype": self.primary_doctype,
			}
		}

		for source in self.resource_map.get("sources") or []:
			source_key = (source.get("source_key") or "").strip()
			kind = (source.get("kind") or "").strip()
			doctype = (source.get("source_doctype") or source.get("doctype") or "").strip()

			if not all([source_key, kind, doctype]):
				continue

			if source_key == "primary":
				raise FHIRMappingCompilationError(
					"Do not add a source with key 'primary' in the sources table."
				)

			supported_kinds = ("direct_link", "reverse_link")
			if kind not in supported_kinds:
				raise FHIRMappingCompilationError(
					f"Source '{source_key}': unsupported kind '{kind}'. Supported: {supported_kinds}"
				)

			if source_key in sources:
				raise FHIRMappingCompilationError(f"Duplicate source_key '{source_key}'.")

			link_fieldname = (source.get("link_fieldname") or "").strip()
			if not link_fieldname:
				raise FHIRMappingCompilationError(
					f"Source '{source_key}': link_fieldname is required for '{kind}'."
				)

			spec = {
				"source_key": source_key,
				"kind": kind,
				"doctype": doctype,
				"link_fieldname": link_fieldname,
				"filters": parse_json_object(source.get("filters_json")) or {},
				"order_by": (source.get("order_by") or "").strip() or "creation desc",
			}
			sources[spec["source_key"]] = spec

		return sources

	# =========================================================
	# Elements
	# =========================================================

	def compile_elements(self, compiled_sources):
		elements = {}

		for row in self.resource_map.get("element_maps") or []:
			fhir_path = (row.get("fhir_path") or "").strip()
			if not fhir_path:
				continue

			if fhir_path in elements:
				raise FHIRMappingCompilationError(f"Duplicate element mapping for fhir_path '{fhir_path}'.")

			pointer = parse_value_pointer(row.get("value_pointer"))
			if not pointer:
				continue

			value_spec = self.build_value_spec(pointer, fhir_path, compiled_sources)

			datatype = (row.get("datatype") or "").strip()

			max_raw = row.get("max")
			max_card = (max_raw or "").strip() if isinstance(max_raw, str) else str(max_raw or "")

			element = {
				"base_json_path": self._to_json_path(fhir_path),
				"value_spec": value_spec,
				"datatype": datatype,
				"regex": row.get("regex"),
				"min": cint(row.get("min", 0)),
				"max": max_card,
				"binding_strength": (row.get("binding_strength") or "").strip(),
				"is_choice_type": cint(row.get("is_choice_type")),
				"valueset_url": (row.get("valueset_url") or "").strip(),
				"profile": (row.get("profile") or "").strip(),
				"target_profiles": normalize_string_list(row.get("target_profiles")),
			}

			elements[fhir_path] = element

		return elements

	def build_value_spec(self, pointer, fhir_path, compiled_sources):
		kind = (pointer.get("kind") or "").strip()

		if kind == "fixed":
			if "value" not in pointer:
				raise FHIRMappingCompilationError(f"'{fhir_path}': fixed pointer missing 'value'")
			return {"kind": "fixed", "value": pointer.get("value")}

		if kind == "field":
			source_key = (pointer.get("source_key") or "").strip()
			fieldname = (pointer.get("fieldname") or "").strip()

			if not source_key:
				raise FHIRMappingCompilationError(f"'{fhir_path}': field pointer missing 'source_key'")
			if not fieldname:
				raise FHIRMappingCompilationError(f"'{fhir_path}': field pointer missing 'fieldname'")
			if source_key not in compiled_sources:
				raise FHIRMappingCompilationError(
					f"'{fhir_path}': unknown source_key '{source_key}'. "
					f"Available: {sorted(compiled_sources.keys())}"
				)

			return {"kind": "field", "source_key": source_key, "fieldname": fieldname}

		raise FHIRMappingCompilationError(f"'{fhir_path}': unsupported pointer kind '{kind}'")

	# =========================================================
	# Compile-time collapse: child-table row mappings
	# =========================================================
	def collapse_child_table_row_mappings(self, elements, compiled_sources):
		"""
		Collapse leaf mappings that read from a child table into a single container mapping,
		while carrying per-leaf constraints (min/max/datatype/binding_strength/valueset_url/regex).

		Also throws if both:
		  - container is explicitly mapped (e.g. Patient.telecom)
		  - AND one or more leaf mappings exist (e.g. Patient.telecom.system)
		"""
		if not elements:
			return elements

		groups = {}
		leaf_paths_by_container = {}
		containers_explicitly_mapped = set()

		# Identify explicitly mapped containers (base_json_path has no dot)
		for fhir_path, element in (elements or {}).items():
			base_json_path = ((element or {}).get("base_json_path") or "").strip()
			if base_json_path and "." not in base_json_path:
				# container candidate like "telecom"
				containers_explicitly_mapped.add(fhir_path)

		for fhir_path, element in (elements or {}).items():
			value_spec = (element or {}).get("value_spec") or {}
			if (value_spec.get("kind") or "").strip() != "field":
				continue

			source_key = (value_spec.get("source_key") or "").strip()
			fieldname = (value_spec.get("fieldname") or "").strip()
			if not source_key or not fieldname:
				continue

			base_json_path = (element.get("base_json_path") or "").strip()
			if "." not in base_json_path:
				continue

			# fieldname must be "table_field.row_field"
			if "." not in fieldname:
				continue

			table_fieldname = fieldname.split(".", 1)[0].strip()
			row_fieldname = fieldname.split(".", 1)[1].strip()
			if not table_fieldname or not row_fieldname:
				continue

			source_doctype = ((compiled_sources or {}).get(source_key) or {}).get("doctype")
			if not source_doctype:
				continue

			if not self._is_table_field(source_doctype, table_fieldname):
				continue

			container_name = base_json_path.split(".", 1)[0].strip()
			child_key = base_json_path.split(".", 1)[1].strip()
			if not container_name or not child_key:
				continue

			container_fhir_path = f"{self.resource_type}.{container_name}"
			group_key = (container_fhir_path, source_key, table_fieldname)

			if group_key not in groups:
				groups[group_key] = {
					"container_fhir_path": container_fhir_path,
					"container_name": container_name,
					"source_key": source_key,
					"table_fieldname": table_fieldname,
					"row_mapping": {},
					"row_constraints": {},
					"template_element": element,
				}

			# Map child_key -> row field
			groups[group_key]["row_mapping"][child_key] = row_fieldname

			# Carry constraints for per-row validation
			groups[group_key]["row_constraints"][child_key] = {
				"datatype": (element.get("datatype") or "").strip(),
				"regex": element.get("regex"),
				"min": cint(element.get("min", 0)),
				"max": (element.get("max") or "").strip()
				if isinstance(element.get("max") or "", str)
				else str(element.get("max") or ""),
				"binding_strength": (element.get("binding_strength") or "").strip(),
				"valueset_url": (element.get("valueset_url") or "").strip(),
				"profile": (element.get("profile") or "").strip(),
				"target_profiles": normalize_string_list(element.get("target_profiles")),
				"is_choice_type": cint(element.get("is_choice_type")),
			}

			leaf_paths_by_container.setdefault(container_fhir_path, []).append(fhir_path)

		# Conflict check: container explicitly mapped + leaf mappings present
		for container_fhir_path, leaf_paths in (leaf_paths_by_container or {}).items():
			if container_fhir_path in elements and container_fhir_path in containers_explicitly_mapped:
				raise FHIRMappingCompilationError(
					f"Conflicting mappings: '{container_fhir_path}' is mapped directly, "
					f"but leaf mappings also exist: {sorted(set(leaf_paths))}. "
					f"Remove either the container mapping or the leaf mappings."
				)

		# Create container elements
		for group_key, group in groups.items():
			container_fhir_path = group["container_fhir_path"]

			# If container exists (but wasn't explicitly mapped), don't override; still remove leaves below.
			if container_fhir_path not in elements:
				template = group.get("template_element") or {}

				container_element = {
					"base_json_path": group["container_name"],
					"value_spec": {
						"kind": "child_table_rows",
						"source_key": group["source_key"],
						"table_fieldname": group["table_fieldname"],
						"row_mapping": group["row_mapping"],
						"row_constraints": group["row_constraints"],
					},
					"datatype": "",  # intentionally blank (complex container)
					"regex": None,
					"min": 0,
					"max": "*",
					"binding_strength": "",
					"is_choice_type": 0,
					"valueset_url": "",
					"profile": (template.get("profile") or "").strip(),
					"target_profiles": normalize_string_list(template.get("target_profiles")),
				}

				elements[container_fhir_path] = container_element

		# Remove leaf elements only if the container exists (created or already present)
		for container_fhir_path, leaf_paths in (leaf_paths_by_container or {}).items():
			if container_fhir_path not in elements:
				continue
			for leaf_path in leaf_paths:
				elements.pop(leaf_path, None)

		return elements

	def collapse_object_group_mappings(self, elements):
		if not elements:
			return elements

		# Explicit containers: base_json_path has no dot (meaning the user mapped the container directly)
		explicit_containers = set()
		for fhir_path, element in (elements or {}).items():
			base_json_path = ((element or {}).get("base_json_path") or "").strip()
			if base_json_path and "." not in base_json_path:
				explicit_containers.add(fhir_path)

		# container_fhir_path -> group
		groups = {}

		for leaf_fhir_path, leaf_element in (elements or {}).items():
			base_json_path = ((leaf_element or {}).get("base_json_path") or "").strip()
			if "." not in base_json_path:
				continue

			value_spec = (leaf_element or {}).get("value_spec") or {}
			kind = (value_spec.get("kind") or "").strip()
			if kind not in ("field", "fixed"):
				continue

			container_name, child_key = base_json_path.split(".", 1)
			container_name = (container_name or "").strip()
			child_key = (child_key or "").strip()
			if not container_name or not child_key:
				continue

			container_fhir_path = f"{self.resource_type}.{container_name}"

			# Conflict: container explicitly mapped + leafs exist
			if container_fhir_path in explicit_containers:
				raise FHIRMappingCompilationError(
					f"Conflicting mappings: '{container_fhir_path}' is mapped directly, "
					f"but leaf mappings also exist (e.g. '{leaf_fhir_path}'). "
					f"Remove either the container mapping or the leaf mappings."
				)

			group = groups.setdefault(
				container_fhir_path,
				{
					"container_name": container_name,
					"embedded_children": {},
					"leaf_paths": [],
					"field_source_keys": set(),
					"has_repeating_child": False,
					"has_field_child": False,
					"all_children_fixed": True,
					"all_children_max_one": True,
				},
			)

			group["leaf_paths"].append(leaf_fhir_path)

			if kind == "field":
				group["has_field_child"] = True
				source_key = (value_spec.get("source_key") or "").strip()
				if source_key:
					group["field_source_keys"].add(source_key)
				group["all_children_fixed"] = False

			if kind != "fixed":
				group["all_children_fixed"] = False

			child_max = leaf_element.get("max")
			child_max = (child_max or "").strip() if isinstance(child_max, str) else str(child_max or "")

			if child_max == "*":
				group["has_repeating_child"] = True

			if child_max and child_max != "1":
				group["all_children_max_one"] = False

			group["embedded_children"][child_key] = {
				"leaf_fhir_path": leaf_fhir_path,
				"value_spec": value_spec,
				"datatype": (leaf_element.get("datatype") or "").strip(),
				"regex": leaf_element.get("regex"),
				"min": cint(leaf_element.get("min", 0)),
				"max": child_max,
				"binding_strength": (leaf_element.get("binding_strength") or "").strip(),
				"valueset_url": (leaf_element.get("valueset_url") or "").strip(),
				"profile": (leaf_element.get("profile") or "").strip(),
				"target_profiles": normalize_string_list(leaf_element.get("target_profiles")),
				"is_choice_type": cint(leaf_element.get("is_choice_type")),
			}

		# Provenance check: a single source_key across field children
		for container_fhir_path, group in groups.items():
			source_keys = group.get("field_source_keys") or set()
			if len(source_keys) > 1:
				raise FHIRMappingCompilationError(
					f"Cannot collapse '{container_fhir_path}' into object_group because its leaf fields "
					f"come from multiple sources: {sorted(source_keys)}. "
					"Use a child table row mapping or keep leaf mappings as-is."
				)

		# Collapse groups
		for container_fhir_path, group in groups.items():
			leaf_paths = group.get("leaf_paths") or []
			if len(leaf_paths) < 2:
				continue

			# If any child repeats (max="*"), object_group is the wrong tool.
			if group.get("has_repeating_child"):
				continue

			# Decide container repetition if available
			existing_container = elements.get(container_fhir_path)
			container_max = ""
			if existing_container:
				raw = existing_container.get("max")
				container_max = (raw or "").strip() if isinstance(raw, str) else str(raw or "")

			container_is_repeating = (container_max == "*") if container_max else True

			# Generic guard for repeating containers:
			# - OK if all children are fixed (harmless)
			# - OK if all children are max=1 and single provenance (already enforced) => "single logical object"
			# - Otherwise skip (ambiguous multi-row)
			if container_is_repeating and group.get("has_field_child"):
				if not (group.get("all_children_fixed") or group.get("all_children_max_one")):
					continue

			# wrap_in_array: use container max if available else True
			wrap_in_array = True
			if container_max:
				wrap_in_array = (container_max == "*")

			if container_fhir_path in elements:
				# If it exists, only acceptable if it's already object_group (rare). Otherwise error.
				existing_kind = ((elements[container_fhir_path].get("value_spec") or {}).get("kind") or "").strip()
				if existing_kind and existing_kind != "object_group":
					raise FHIRMappingCompilationError(
						f"'{container_fhir_path}' exists but is not an object_group; cannot collapse leafs {sorted(set(leaf_paths))}."
					)

			if container_fhir_path not in elements:
				elements[container_fhir_path] = {
					"base_json_path": group["container_name"],
					"value_spec": {
						"kind": "object_group",
						"children": group["embedded_children"],
						"wrap_in_array": wrap_in_array,
					},
					"datatype": "",
					"regex": None,
					"min": 0,
					"max": "*",  # safe default; wrap_in_array controls the JSON shape
					"binding_strength": "",
					"is_choice_type": 0,
					"valueset_url": "",
					"profile": "",
					"target_profiles": [],
				}
			else:
				# Update wrap_in_array if already object_group
				elements[container_fhir_path].setdefault("value_spec", {})
				elements[container_fhir_path]["value_spec"]["wrap_in_array"] = wrap_in_array
				elements[container_fhir_path]["value_spec"]["children"] = group["embedded_children"]

			# Remove leafs
			for leaf_path in leaf_paths:
				elements.pop(leaf_path, None)

		return elements

	def _is_table_field(self, doctype, fieldname):
		if not doctype or not fieldname:
			return False

		try:
			meta = frappe.get_meta(doctype)
		except Exception:
			return False

		field = meta.get_field(fieldname)
		if not field:
			return False

		return (field.fieldtype or "").strip().lower() == "table"

	def _safe_int(value, default=0):
		try:
			return int(value)
		except Exception:
			return default

	# =========================================================
	# Profiles + paths
	# =========================================================

	def collect_profile_urls(self):
		"""Collect profile URLs from the profiles child table."""
		urls = []
		for row in self.resource_map.get("profiles") or []:
			url = (row.get("url") or "").strip()
			if url and url not in urls:
				urls.append(url)
		return urls

	def _to_json_path(self, fhir_path):
		fhir_path = (fhir_path or "").strip()
		prefix = f"{self.resource_type}."
		if self.resource_type and fhir_path.startswith(prefix):
			return fhir_path[len(prefix) :]
		return fhir_path


# =========================================================
# Helper functions
# =========================================================


def parse_json_object(value):
	if not value:
		return {}
	if isinstance(value, dict):
		return value
	text = str(value).strip()
	if not text:
		return {}
	try:
		parsed = json.loads(text)
		return parsed if isinstance(parsed, dict) else {}
	except json.JSONDecodeError:
		raise FHIRMappingCompilationError("filters_json must be a JSON object.")


def parse_value_pointer(raw):
	if raw is None:
		return None

	if isinstance(raw, dict):
		pointer = raw
	else:
		text = str(raw).strip()
		if not text:
			return None
		try:
			pointer = json.loads(text)
		except json.JSONDecodeError:
			return None

	if not isinstance(pointer, dict):
		return None

	if not (pointer.get("kind") or "").strip():
		return None

	return pointer


def normalize_string_list(value):
	if value is None:
		return []

	if isinstance(value, list):
		return [str(v).strip() for v in value if str(v).strip()]

	if isinstance(value, str):
		text = value.strip()
		if not text:
			return []

		if text.startswith("[") and text.endswith("]"):
			try:
				parsed = json.loads(text)
				if isinstance(parsed, list):
					return [str(v).strip() for v in parsed if str(v).strip()]
			except json.JSONDecodeError:
				return []

		return [text]

	return []
