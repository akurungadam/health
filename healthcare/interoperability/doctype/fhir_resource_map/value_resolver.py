"""
FHIR Value Resolver (Ship-ready, Generic)

- Infers all source data from compiled sources + primary_name.
- Resolves values based on compiled element mappings.
- Supports:
  - primary / direct_link / reverse_link sources
  - nested field access with dot notation
  - child tables (list[dict]) returning list of values across all rows
  - spreading list values into indexed repeating paths (foo[0].bar -> foo[0], foo[1], ...)
  - safe merging for container object paths (foo[0]) when values are dicts
- No typing annotations.
"""

import re

import frappe


class FHIRValueResolver:
	def __init__(self, compiled_map, primary_name):
		self.compiled_map = compiled_map or {}
		self.primary_name = primary_name

		self.elements = self.compiled_map.get("elements", {}) or {}
		self.element_order = self.compiled_map.get("element_order", []) or []
		self.sources = self.compiled_map.get("sources", {}) or {}
		self.meta = self.compiled_map.get("meta", {}) or {}
		self.repeating_containers = self.compiled_map.get("repeating_containers", {}) or {}

		self.source_data = {}
		self._resolve_sources()

	def resolve(self):
		resource = {"resourceType": self.meta.get("resource_type", "Unknown")}

		for element_path in self.element_order:
			element = self.elements.get(element_path)
			if not element:
				continue

			json_path = (element.get("path") or "").strip()
			if not json_path:
				continue

			# Guard: mapping a whole child table object directly into foo[0] is usually wrong.
			# Example: Patient.telecom -> telecom[0] from child table field.
			# We skip container writes when the resolved value is list-like.
			resolved_value = self._resolve_element_value(element)
			if resolved_value is None:
				continue

			if self._should_skip_container_write(element, resolved_value):
				continue

			self._set_value(resource, json_path, resolved_value)

		return resource

	# =========================================================
	# Sources
	# =========================================================

	def _resolve_sources(self):
		# Pass 1: primary
		for source_key, source_config in self.sources.items():
			if (source_config.get("kind") or "").strip() == "primary":
				self.source_data[source_key] = self._load_primary(source_config)

		# Pass 2: links
		for source_key, source_config in self.sources.items():
			kind = (source_config.get("kind") or "").strip()
			if kind == "direct_link":
				self.source_data[source_key] = self._load_direct_link(source_config)
			elif kind == "reverse_link":
				self.source_data[source_key] = self._load_reverse_link(source_config)

	def _load_primary(self, source_config):
		doctype = (source_config.get("doctype") or "").strip()
		if not doctype:
			frappe.throw("Primary source is missing doctype.")
		doc = frappe.get_doc(doctype, self.primary_name)
		return doc.as_dict()

	def _load_direct_link(self, source_config):
		doctype = (source_config.get("doctype") or "").strip()
		link_fieldname = (source_config.get("link_fieldname") or "").strip()
		if not doctype or not link_fieldname:
			return None

		primary = self._get_primary_doc()
		linked_name = primary.get(link_fieldname)
		if not linked_name:
			return None

		try:
			doc = frappe.get_doc(doctype, linked_name)
			return doc.as_dict()
		except Exception:
			return None

	def _load_reverse_link(self, source_config):
		doctype = (source_config.get("doctype") or "").strip()
		link_fieldname = (source_config.get("link_fieldname") or "").strip()
		order_by = (source_config.get("order_by") or "").strip()

		if not doctype or not link_fieldname:
			return []

		names = (
			frappe.get_all(
				doctype,
				filters={link_fieldname: self.primary_name},
				pluck="name",
				order_by=order_by or None,
			)
			or []
		)

		out = []
		for name in names:
			try:
				doc = frappe.get_doc(doctype, name)
				out.append(doc.as_dict())
			except Exception:
				continue

		return out

	def _get_primary_source_key(self):
		for source_key, source_config in self.sources.items():
			if (source_config.get("kind") or "").strip() == "primary":
				return source_key
		return "primary"

	def _get_primary_doc(self):
		primary_key = self._get_primary_source_key()
		doc = self.source_data.get(primary_key)
		return doc if isinstance(doc, dict) else {}

	# =========================================================
	# Element value resolution
	# =========================================================

	def _resolve_element_value(self, element):
		value_spec = element.get("value_spec", {}) or {}
		kind = (value_spec.get("kind") or "").strip()

		if kind == "fixed":
			return self._coerce(value_spec.get("value"), element.get("datatype"))

		if kind == "field":
			return self._resolve_field(value_spec, element)

		return None

	def _resolve_field(self, value_spec, element):
		source_key = (value_spec.get("source_key") or "").strip()
		fieldname = (value_spec.get("fieldname") or "").strip()
		if not source_key or not fieldname:
			return None

		doc_data = self.source_data.get(source_key)

		# reverse_link: list of docs -> returns list of coerced values
		if isinstance(doc_data, list):
			out = []
			for row in doc_data:
				val = self._read_field(row, fieldname)
				if val is None:
					continue
				out.extend(self._coerce_many(val, element.get("datatype")))
			return out if out else None

		# direct/primary: dict
		if not isinstance(doc_data, dict):
			return None

		val = self._read_field(doc_data, fieldname)
		if val is None:
			return None

		out = self._coerce_many(val, element.get("datatype"))
		if not out:
			return None
		return out if isinstance(val, list) else out[0]

	def _coerce_many(self, val, datatype):
		if val is None:
			return []
		if isinstance(val, list):
			out = []
			for item in val:
				c = self._coerce(item, datatype)
				if c is not None:
					out.append(c)
			return out
		c = self._coerce(val, datatype)
		return [c] if c is not None else []

	def _coerce(self, value, datatype):
		if value is None:
			return None

		# Never stringify list/dict — preserve as-is
		if isinstance(value, (list, dict)):
			return value

		if not datatype:
			return value

		primary_type = self._first_datatype(datatype)

		try:
			if primary_type == "boolean":
				if isinstance(value, bool):
					return value
				if isinstance(value, str):
					return value.strip().lower() in ("true", "1", "yes")
				return bool(value)

			if primary_type == "integer":
				return int(value)

			if primary_type == "decimal":
				return float(value)

			if primary_type == "code":
				return str(value).strip().lower()

			if primary_type in ("string", "id", "uri", "url", "canonical"):
				return str(value)

			if primary_type in ("date", "dateTime", "time", "instant"):
				return str(value)

			# Complex-ish convenience wrapping (generic)
			if primary_type == "Reference":
				return {"display": str(value)}
			if primary_type == "CodeableConcept":
				return {"text": str(value)}

			return value

		except Exception:
			return value

	def _first_datatype(self, datatype):
		parts = [p.strip() for p in str(datatype).split(",") if p.strip()]
		return parts[0] if parts else ""

	# =========================================================
	# Field reading with child-table support
	# =========================================================

	def _read_field(self, data, fieldname):
		"""
		Dot-notation reader.
		If a list[dict] is encountered, returns list of values across all rows.
		"""
		if data is None:
			return None

		parts = (fieldname or "").split(".")
		if not parts:
			return None

		current = data

		for idx, part in enumerate(parts):
			if isinstance(current, dict):
				current = current.get(part)
				if current is None:
					return None
				continue

			if isinstance(current, list):
				remaining = ".".join(parts[idx:])
				values = []
				for row in current:
					if not isinstance(row, dict):
						continue
					val = self._read_field(row, remaining)
					if val is None:
						continue
					if isinstance(val, list):
						values.extend([x for x in val if x is not None])
					else:
						values.append(val)
				return values if values else None

			return None

		return current

	# =========================================================
	# Path writing (supports indexed arrays + spreading)
	# =========================================================

	def _set_value(self, obj, path, value):
		if not path:
			return

		first_index = self._get_first_index(path)

		# Spread list values into indexed repeating paths (foo[0].bar)
		if isinstance(value, list) and first_index is not None:
			for idx, item in enumerate(value):
				item_path = self._replace_first_index(path, idx)
				self._set_value(obj, item_path, item)
			return

		# If target is a container path like foo[0] and value is dict, merge
		if self._is_container_path(path) and isinstance(value, dict):
			existing = self._get_value(obj, path)
			if isinstance(existing, dict):
				merged = {}
				merged.update(existing)
				merged.update(value)
				value = merged

		parts = self._parse_path(path)
		current = obj

		for key, index in parts[:-1]:
			if key not in current:
				current[key] = [] if index is not None else {}

			if index is not None:
				if not isinstance(current[key], list):
					current[key] = []
				while len(current[key]) <= index:
					current[key].append({})
				if not isinstance(current[key][index], dict):
					current[key][index] = {}
				current = current[key][index]
			else:
				if not isinstance(current[key], dict):
					current[key] = {}
				current = current[key]

		final_key, final_index = parts[-1]

		if final_index is not None:
			if final_key not in current or not isinstance(current[final_key], list):
				current[final_key] = []
			while len(current[final_key]) <= final_index:
				current[final_key].append({})

			if isinstance(value, dict) and isinstance(current[final_key][final_index], dict):
				current[final_key][final_index].update(value)
			else:
				current[final_key][final_index] = value
		else:
			current[final_key] = value

	def _get_value(self, obj, path):
		parts = self._parse_path(path)
		current = obj
		for key, index in parts:
			if not isinstance(current, dict):
				return None
			if key not in current:
				return None
			current = current[key]
			if index is not None:
				if not isinstance(current, list) or len(current) <= index:
					return None
				current = current[index]
		return current

	def _parse_path(self, path):
		parts = []
		for segment in (path or "").split("."):
			match = re.match(r"(\w+)\[(\d+)\]", segment)
			if match:
				parts.append((match.group(1), int(match.group(2))))
			else:
				parts.append((segment, None))
		return parts

	def _get_first_index(self, path):
		match = re.search(r"\[(\d+)\]", path or "")
		return int(match.group(1)) if match else None

	def _replace_first_index(self, path, index):
		return re.sub(r"\[\d+\]", f"[{index}]", path, count=1)

	def _is_container_path(self, path):
		# container paths end with "]" and contain no "."
		# e.g. "telecom[0]" or "identifier[0]"
		return path.endswith("]") and "." not in path

	# =========================================================
	# Safety: skip bad container writes from child tables
	# =========================================================

	def _should_skip_container_write(self, element, resolved_value):
		"""
		If an element maps a container path like foo[0] from a field spec and the resolved
		value is list-like, it's almost always a child table mis-map. We skip it.
		Leaf mappings (foo[0].bar) will still populate correctly.
		"""
		path = (element.get("path") or "").strip()
		if not self._is_container_path(path):
			return False

		value_spec = element.get("value_spec", {}) or {}
		kind = (value_spec.get("kind") or "").strip()
		if kind != "field":
			return False

		return isinstance(resolved_value, list)

	# =========================================================
	# Validation (generic, respects internal sources)
	# =========================================================

	def validate_required_fields(self):
		errors = []

		for element_path, element in (self.elements or {}).items():
			min_cardinality = element.get("min", 0)
			if not min_cardinality or int(min_cardinality) <= 0:
				continue

			value_spec = element.get("value_spec", {}) or {}
			kind = (value_spec.get("kind") or "").strip()

			# fixed values are always "present" if non-null
			if kind == "fixed":
				if value_spec.get("value") is None:
					errors.append(self._err_required(element_path, "Fixed value is null."))
				continue

			if kind != "field":
				continue

			source_key = value_spec.get("source_key")
			fieldname = value_spec.get("fieldname")

			if source_key not in self.source_data:
				errors.append(self._err_required(element_path, f"Missing source '{source_key}'."))
				continue

			doc_data = self.source_data.get(source_key)

			if isinstance(doc_data, list):
				found = False
				for row in doc_data:
					val = self._read_field(row, fieldname)
					if val is not None and (not isinstance(val, list) or len(val) > 0):
						found = True
						break
				if not found:
					errors.append(
						self._err_required(
							element_path,
							f"Missing field '{fieldname}' in reverse_link source '{source_key}'.",
						)
					)
			else:
				val = self._read_field(doc_data or {}, fieldname)
				if val is None or (isinstance(val, list) and not val):
					errors.append(
						self._err_required(
							element_path, f"Missing field '{fieldname}' in source '{source_key}'."
						)
					)

		return errors

	def _err_required(self, element_path, reason):
		return {
			"type": "missing_required_value",
			"fhir_path": element_path,
			"message": f"Required element '{element_path}' could not be resolved: {reason}",
		}
