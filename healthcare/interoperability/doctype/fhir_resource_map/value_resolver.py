"""
FHIR Value Resolver

Resolves values from Frappe documents based on compiled mappings.
Outputs a flat dict: {element_path: resolved_value}

The resource builder is responsible for constructing nested FHIR JSON from this flat output.
"""

import frappe


class FHIRValueResolver:
	def __init__(self, compiled_map, primary_name):
		self.compiled_map = compiled_map or {}
		self.primary_name = primary_name

		self.sources = self.compiled_map.get("sources") or {}
		self.elements = self.compiled_map.get("elements") or {}
		self.element_order = self.compiled_map.get("element_order") or []

		self.source_data = {}
		self.resolved_values = {}

	def resolve(self):
		"""
		Main entry point.
		Returns flat dict: {element_path: resolved_value}
		"""
		self._load_sources()
		self._resolve_elements()
		return self.resolved_values

	# =========================================================
	# Source Loading
	# =========================================================

	def _load_sources(self):
		"""Load all source documents in dependency order."""
		# Pass 1: primary sources (no dependencies)
		for key, config in self.sources.items():
			if self._get_kind(config) == "primary":
				self.source_data[key] = self._load_primary(config)

		# Pass 2: linked sources (depend on primary)
		for key, config in self.sources.items():
			kind = self._get_kind(config)
			if kind == "direct_link":
				self.source_data[key] = self._load_direct_link(config)
			elif kind == "reverse_link":
				self.source_data[key] = self._load_reverse_link(config)

	def _load_primary(self, config):
		doctype = self._get_str(config, "doctype")
		if not doctype:
			return None

		try:
			return frappe.get_doc(doctype, self.primary_name).as_dict()
		except frappe.DoesNotExistError:
			return None

	def _load_direct_link(self, config):
		doctype = self._get_str(config, "doctype")
		link_fieldname = self._get_str(config, "link_fieldname")
		from_source = self._get_str(config, "from_source") or "primary"

		if not doctype or not link_fieldname:
			return None

		parent_doc = self.source_data.get(from_source)
		if not parent_doc:
			return None

		linked_name = parent_doc.get(link_fieldname)
		if not linked_name:
			return None

		# Optional: lookup by different field
		lookup_field = self._get_str(config, "lookup_fieldname")
		if lookup_field:
			linked_name = frappe.db.get_value(doctype, {lookup_field: linked_name}, "name")
			if not linked_name:
				return None

		try:
			return frappe.get_doc(doctype, linked_name).as_dict()
		except frappe.DoesNotExistError:
			return None

	def _load_reverse_link(self, config):
		doctype = self._get_str(config, "doctype")
		link_fieldname = self._get_str(config, "link_fieldname")
		from_source = self._get_str(config, "from_source") or "primary"

		if not doctype or not link_fieldname:
			return []

		parent_doc = self.source_data.get(from_source)
		if not parent_doc:
			return []

		parent_name = parent_doc.get("name")
		if not parent_name:
			return []

		# Build filters
		filters = {link_fieldname: parent_name}
		extra_filters = config.get("filters")
		if extra_filters:
			filters.update(extra_filters)

		order_by = self._get_str(config, "order_by") or "creation desc"
		limit = config.get("limit")

		names = frappe.get_all(
			doctype,
			filters=filters,
			order_by=order_by,
			pluck="name",
			limit=limit,
		)

		docs = []
		for name in names:
			try:
				docs.append(frappe.get_doc(doctype, name).as_dict())
			except frappe.DoesNotExistError:
				continue

		return docs

	# =========================================================
	# Element Resolution
	# =========================================================

	def _resolve_elements(self):
		"""Resolve all element values into flat dict."""
		order = self.element_order or list(self.elements.keys())

		for element_path in order:
			element = self.elements.get(element_path)
			if not element:
				continue

			value = self._resolve_element(element)
			if value is not None:
				self.resolved_values[element_path] = value

	def _resolve_element(self, element):
		"""Resolve a single element's value."""
		value_spec = element.get("value_spec") or {}
		kind = self._get_str(value_spec, "kind")

		if kind == "fixed":
			return self._resolve_fixed(value_spec, element)

		if kind == "field":
			return self._resolve_field(value_spec, element)

		return None

	def _resolve_fixed(self, value_spec, element):
		"""Resolve a fixed/constant value."""
		value = value_spec.get("value")
		return self._coerce(value, element.get("datatype"))

	def _resolve_field(self, value_spec, element):
		"""Resolve a value from a document field."""
		source_key = self._get_str(value_spec, "source_key")
		fieldname = self._get_str(value_spec, "fieldname")

		if not source_key or not fieldname:
			return None

		source = self.source_data.get(source_key)
		if source is None:
			return None

		datatype = element.get("datatype")

		# Reverse link: list of documents
		if isinstance(source, list):
			return self._resolve_from_list(source, fieldname, datatype)

		# Direct/primary: single document
		return self._resolve_from_doc(source, fieldname, datatype)

	def _resolve_from_doc(self, doc, fieldname, datatype):
		"""Extract and coerce value from a single document."""
		value = self._read_field(doc, fieldname)
		if value is None:
			return None

		# If field itself is a list (child table), return coerced list
		if isinstance(value, list):
			result = []
			for item in value:
				coerced = self._coerce(item, datatype)
				if coerced is not None:
					result.append(coerced)
			return result if result else None

		return self._coerce(value, datatype)

	def _resolve_from_list(self, docs, fieldname, datatype):
		"""Extract and coerce values from a list of documents."""
		result = []

		for doc in docs:
			value = self._read_field(doc, fieldname)
			if value is None:
				continue

			if isinstance(value, list):
				for item in value:
					coerced = self._coerce(item, datatype)
					if coerced is not None:
						result.append(coerced)
			else:
				coerced = self._coerce(value, datatype)
				if coerced is not None:
					result.append(coerced)

		return result if result else None

	# =========================================================
	# Field Reading (dot notation + child table support)
	# =========================================================

	def _read_field(self, data, fieldname):
		"""
		Read a field using dot notation.
		Handles nested dicts and child tables (list of dicts).
		"""
		if not data or not fieldname:
			return None

		parts = fieldname.split(".")
		current = data

		for i, part in enumerate(parts):
			if current is None:
				return None

			if isinstance(current, dict):
				current = current.get(part)

			elif isinstance(current, list):
				# Child table: collect values from remaining path across all rows
				remaining = ".".join(parts[i:])
				values = []
				for row in current:
					if isinstance(row, dict):
						val = self._read_field(row, remaining)
						if val is not None:
							if isinstance(val, list):
								values.extend(val)
							else:
								values.append(val)
				return values if values else None

			else:
				return None

		return current

	# =========================================================
	# Type Coercion
	# =========================================================

	def _coerce(self, value, datatype):
		"""Coerce a value to the expected FHIR datatype."""
		if value is None:
			return None

		# Preserve complex types as-is
		if isinstance(value, (list, dict)):
			return value

		if not datatype:
			return value

		primary_type = self._primary_datatype(datatype)

		try:
			if primary_type == "boolean":
				return self._to_bool(value)

			if primary_type == "integer":
				return int(value)

			if primary_type == "decimal":
				return float(value)

			if primary_type == "code":
				return str(value).strip().lower()

			if primary_type in ("string", "id", "uri", "url", "canonical", "markdown"):
				return str(value)

			if primary_type in ("date", "dateTime", "time", "instant"):
				return str(value)

			# Complex type convenience wrappers
			if primary_type == "Reference":
				return {"display": str(value)}

			if primary_type == "CodeableConcept":
				return {"text": str(value)}

			return value

		except (ValueError, TypeError):
			return value

	def _to_bool(self, value):
		"""Convert value to boolean."""
		if isinstance(value, bool):
			return value
		if isinstance(value, str):
			return value.strip().lower() in ("true", "1", "yes")
		return bool(value)

	def _primary_datatype(self, datatype):
		"""Get first datatype from comma-separated list."""
		if not datatype:
			return ""
		parts = str(datatype).split(",")
		return parts[0].strip() if parts else ""

	# =========================================================
	# Utilities
	# =========================================================

	def _get_str(self, obj, key):
		"""Get a string value, stripped and normalized."""
		val = obj.get(key) if obj else None
		return val.strip() if isinstance(val, str) else ""

	def _get_kind(self, config):
		"""Get the kind from a source config."""
		return self._get_str(config, "kind")

	# =========================================================
	# Validation
	# =========================================================

	def validate_required(self):
		"""
		Validate that required elements have values.
		Call after resolve().
		Returns list of error dicts.
		"""
		errors = []

		for element_path, element in self.elements.items():
			min_card = element.get("min", 0)
			if not min_card or int(min_card) <= 0:
				continue

			value = self.resolved_values.get(element_path)

			if value is None:
				errors.append(
					{
						"type": "missing_required",
						"path": element_path,
						"message": f"Required element '{element_path}' has no value",
					}
				)
			elif isinstance(value, list) and len(value) == 0:
				errors.append(
					{
						"type": "missing_required",
						"path": element_path,
						"message": f"Required element '{element_path}' is empty",
					}
				)

		return errors

	def get_source(self, key):
		"""Get a loaded source document by key."""
		return self.source_data.get(key)

	def get_value(self, element_path):
		"""Get a resolved value by element path."""
		return self.resolved_values.get(element_path)
