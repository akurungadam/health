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
			max_card = (
				(row.get("max") or "").strip()
				if isinstance(row.get("max") or "", str)
				else str(row.get("max") or "")
			)

			element = {
				# "fhir_path": fhir_path,
				"base_json_path": self._to_json_path(fhir_path),
				"value_spec": value_spec,
				"datatype": datatype,
				"regex": row.get("regex"),
				"min": cint(row.get("min", 0)),
				"max": max_card,
				"valueset_url": (row.get("valueset_url") or "").strip(),
				"binding_strength": (row.get("binding_strength") or "").strip(),
				"is_choice_type": 1 if "[x]" in fhir_path else cint(row.get("is_choice_type")),
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
