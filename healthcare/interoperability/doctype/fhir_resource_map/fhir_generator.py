import frappe
import json
from frappe.utils import cint


class FHIRResourceGenerationError(Exception):
	pass


class FHIRResourceGenerator:
	"""
	Takes:
	- compiled_map (compiler output)
	- resolved_values (resolver output, flat dict keyed by fhir_path)
	And produces a valid-ish FHIR JSON dict for that resource.

	Assumptions:
	- compiled_map["meta"]["resource_type"] exists
	- compiled_map["elements"] contains element specs keyed by fhir_path
	- resolved_values keys are fhir_path (same keys as compiled_map element_order or elements keys)
	"""

	def __init__(self, compiled_map, resolved_values):
		self.compiled_map = compiled_map or {}
		self.resolved_values = resolved_values or {}

		self.meta = self.compiled_map.get("meta") or {}
		self.resource_type = (self.meta.get("resource_type") or "").strip()

		self.elements = self.compiled_map.get("elements") or {}
		self.element_order = self.compiled_map.get("element_order") or []

	def build(self):
		self._validate_inputs()

		resource = {"resourceType": self.resource_type}

		order = self.element_order or list(self.elements.keys())
		for fhir_path in order:
			element = self.elements.get(fhir_path) or {}
			if not element:
				continue

			value = self._build_element_value(fhir_path, element)
			if value is None:
				self._enforce_required_element(fhir_path, element)
				continue

			json_path = (element.get("base_json_path") or "").strip()
			if not json_path:
				continue

			self._assign(resource, json_path, value, element)

		return resource

	# =========================================================
	# Build element values
	# =========================================================

	def _build_element_value(self, fhir_path, element):
		# Fast path: resolved already has the value at container key
		if fhir_path in self.resolved_values:
			return self.resolved_values.get(fhir_path)

		value_spec = element.get("value_spec") or {}
		kind = (value_spec.get("kind") or "").strip()

		if kind == "object_group":
			return self._build_object_group_value(fhir_path, element, value_spec)

		if kind == "child_table_rows":
			return self._build_child_table_rows_value(fhir_path, element, value_spec)

		# Leaf: if user still passed leaf paths (older resolver), use that
		if fhir_path in self.resolved_values:
			return self.resolved_values.get(fhir_path)

		return None

	def _build_object_group_value(self, fhir_path, element, value_spec):
		# If resolver already produced container list, it would have returned earlier.
		# Here we build it from embedded children leaf paths (if present).
		children = value_spec.get("children") or {}
		if not children:
			return None

		wrap_in_array = value_spec.get("wrap_in_array", True)

		obj = {}
		for child_key, child_spec in children.items():
			leaf_fhir_path = (child_spec.get("leaf_fhir_path") or "").strip()
			if not leaf_fhir_path:
				continue

			child_value = self.resolved_values.get(leaf_fhir_path)
			if child_value is None:
				self._enforce_required_leaf(leaf_fhir_path, child_spec)
				continue

			obj[child_key] = child_value

		if not obj:
			return None

		return [obj] if wrap_in_array else obj

	def _build_child_table_rows_value(self, fhir_path, element, value_spec):
		# If resolver already produced list-of-rows, it would have returned earlier.
		# Generator can’t reconstruct rows from leaf lists safely, so only validate if present.
		rows = self.resolved_values.get(fhir_path)
		if rows is None:
			return None

		if not isinstance(rows, list):
			raise FHIRResourceGenerationError(f"'{fhir_path}': expected list for child_table_rows, got {type(rows)}")

		row_constraints = value_spec.get("row_constraints") or {}
		for idx, row in enumerate(rows):
			if not isinstance(row, dict):
				raise FHIRResourceGenerationError(f"'{fhir_path}[{idx}]': expected dict row, got {type(row)}")
			self._enforce_required_row_children(fhir_path, idx, row, row_constraints)

		return rows

	# =========================================================
	# Required checks
	# =========================================================

	def _enforce_required_element(self, fhir_path, element):
		min_card = cint(element.get("min", 0))
		if min_card > 0:
			raise FHIRResourceGenerationError(f"Missing required element '{fhir_path}' (min={min_card}).")

	def _enforce_required_leaf(self, leaf_fhir_path, leaf_spec):
		min_card = cint(leaf_spec.get("min", 0))
		if min_card > 0:
			raise FHIRResourceGenerationError(f"Missing required element '{leaf_fhir_path}' (min={min_card}).")

	def _enforce_required_row_children(self, container_fhir_path, row_index, row, row_constraints):
		for child_key, constraint in (row_constraints or {}).items():
			min_card = cint((constraint or {}).get("min", 0))
			if min_card <= 0:
				continue

			if row.get(child_key) is None:
				raise FHIRResourceGenerationError(
					f"'{container_fhir_path}[{row_index}]': missing required '{child_key}' (min={min_card})."
				)

	# =========================================================
	# Assignment helpers (FHIR JSON writing)
	# =========================================================

	def _assign(self, resource, json_path, value, element):
		# json_path can be nested: "communication.language"
		parts = json_path.split(".")
		current = resource

		for i, part in enumerate(parts):
			is_last = i == len(parts) - 1

			if is_last:
				current[part] = self._wrap_if_repeating(value, element)
				return

			if part not in current or not isinstance(current.get(part), dict):
				current[part] = {}
			current = current[part]

	def _wrap_if_repeating(self, value, element):
		max_card = element.get("max")
		max_card = (max_card or "").strip() if isinstance(max_card, str) else str(max_card or "")

		if max_card == "*":
			if value is None:
				return None

			if not isinstance(value, list):
				value = [value]

			# ✅ dedupe repeating arrays here
			return self._dedupe_list(value)

		return value


	# =========================================================
	# Validation
	# =========================================================

	def _validate_inputs(self):
		if not self.compiled_map:
			raise FHIRResourceGenerationError("compiled_map is required.")
		if not self.resource_type:
			raise FHIRResourceGenerationError("compiled_map.meta.resource_type is required.")
		if not isinstance(self.resolved_values, dict):
			raise FHIRResourceGenerationError("resolved_values must be a dict.")

	def _dedupe_list(self, items):
		"""Remove duplicates while preserving order."""
		if not isinstance(items, list):
			return items

		seen = set()
		out = []

		for item in items:
			key = self._dedupe_key(item)
			if key in seen:
				continue
			seen.add(key)
			out.append(item)

		return out

	def _dedupe_key(self, value):
		"""Stable key for list items (dict/list/primitives)."""
		if isinstance(value, (dict, list)):
			try:
				return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
			except Exception:
				return str(value)
		return str(value)


@frappe.whitelist()
def generate_fhir_resource(compiled_mapping_json=None, resolved_values_json=None, resource_map_name=None, primary_name=None):
	"""
	Whitelisted API to generate a FHIR resource JSON.

	Supported inputs:
	1) resource_map_name + primary_name
	   - loads FHIR Resource Map, reads compiled_mapping field
	   - runs FHIRValueResolver(compiled, primary_name)
	   - runs FHIRResourceGenerator(compiled, resolved)

	2) compiled_mapping_json + resolved_values_json
	   - builds resource directly without DB lookups for sources
	"""
	if resource_map_name and primary_name:
		resource_map = frappe.get_doc("FHIR Resource Map", resource_map_name)

		compiled_text = (resource_map.compiled_mapping or "").strip()
		if not compiled_text:
			frappe.throw("FHIR Resource Map has no compiled_mapping. Save/validate it first.")

		try:
			compiled = json.loads(compiled_text)
		except Exception:
			frappe.throw("Invalid compiled_mapping JSON on FHIR Resource Map.")

		# local import to avoid import cycles
		from healthcare.interoperability.doctype.fhir_resource_map.fhir_value_resolver import FHIRValueResolver

		resolved = FHIRValueResolver(compiled, primary_name).resolve()

		generator = FHIRResourceGenerator(compiled, resolved)
		return generator.build()

	if compiled_mapping_json and resolved_values_json:
		compiled = _parse_json_dict(compiled_mapping_json, "compiled_mapping_json")
		resolved = _parse_json_dict(resolved_values_json, "resolved_values_json")

		generator = FHIRResourceGenerator(compiled, resolved)
		return generator.build()

	frappe.throw("Pass (resource_map_name + primary_name) OR (compiled_mapping_json + resolved_values_json).")


def _parse_json_dict(value, label):
	if value is None:
		return {}
	if isinstance(value, dict):
		return value

	text = str(value).strip()
	if not text:
		return {}

	try:
		parsed = json.loads(text)
	except Exception:
		frappe.throw(f"{label} must be valid JSON.")

	if not isinstance(parsed, dict):
		frappe.throw(f"{label} must be a JSON object.")

	return parsed
