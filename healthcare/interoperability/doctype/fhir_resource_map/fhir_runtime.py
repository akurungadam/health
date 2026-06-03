# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
FHIR Runtime

Executes a compiled FHIR Resource Map (see ``fhir_compiler.py``) against a
primary Frappe document to produce a FHIR resource dict.

The runtime reads ONLY the compiled mapping passed to it - it never inspects the
FHIR Resource Map document.

Iteration 1 scope: single-document sources (primary / direct_link / document)
and nested objects built from dotted FHIR paths. Repeating backbone elements
backed by collection sources (child_table / reverse_link) are loaded but not yet
grouped - that is iteration 2.
"""

import frappe

PRIMITIVE_STRING_TYPES = {
	"uri",
	"url",
	"canonical",
	"code",
	"id",
	"oid",
	"uuid",
	"markdown",
	"base64binary",
}


class FHIRRuntime:
	"""Generates a FHIR resource from a compiled mapping."""

	def __init__(self, compiled):
		self.compiled = compiled or {}
		self.meta = self.compiled.get("meta", {})
		self.sources_def = self.compiled.get("sources", {})
		self.elements = self.compiled.get("elements", {})
		self.resource_type = self.meta.get("resource_type")
		self.source_docs = {}
		self.issues = []

	def generate(self, primary_id):
		self.source_docs = {}
		self.issues = []

		self._load_sources(primary_id)

		resource = {"resourceType": self.resource_type}

		for path, element in self.elements.items():
			value = self._resolve_element(element)
			if value is None:
				continue
			self._write_path(resource, path, value, element.get("is_array"))

		return self._prune(resource) or {"resourceType": self.resource_type}

	# =========================================================
	# Source loading
	# =========================================================

	def _load_sources(self, primary_id):
		primary_def = self._primary_source()
		if primary_def:
			self.source_docs["primary"] = self._load_primary(primary_def, primary_id)

		for key, source in self.sources_def.items():
			if source.get("is_primary"):
				continue
			self.source_docs[key] = self._load_source(source)

	def _primary_source(self):
		for source in self.sources_def.values():
			if source.get("is_primary"):
				return source
		return None

	def _load_primary(self, source, primary_id):
		if not primary_id:
			return None
		try:
			return frappe.get_cached_doc(source["doctype"], primary_id).as_dict()
		except frappe.DoesNotExistError:
			self.issues.append(f"Primary document not found: {source['doctype']}/{primary_id}")
			return None

	def _load_source(self, source):
		kind = source.get("kind")
		if kind == "direct_link":
			return self._load_direct_link(source)
		if kind == "child_table":
			return self._load_child_table(source)
		if kind == "reverse_link":
			return self._load_reverse_link(source)
		return self._load_document(source)

	def _load_direct_link(self, source):
		parent = self.source_docs.get(source.get("parent") or "primary")
		link_field = source.get("link_fieldname")
		if not parent or not link_field:
			return None

		linked_id = parent.get(link_field)
		if not linked_id:
			return None

		try:
			return frappe.get_cached_doc(source["doctype"], linked_id).as_dict()
		except frappe.DoesNotExistError:
			return None

	def _load_document(self, source):
		filters = source.get("filters") or {}
		if not filters:
			return None
		names = frappe.get_all(source["doctype"], filters=filters, pluck="name", limit=1)
		if not names:
			return None
		return frappe.get_cached_doc(source["doctype"], names[0]).as_dict()

	def _load_child_table(self, source):
		parent = self.source_docs.get(source.get("parent") or "primary")
		field = source.get("link_fieldname")
		if not parent or not field:
			return []

		rows = parent.get(field) or []
		return [row.as_dict() if hasattr(row, "as_dict") else row for row in rows]

	def _load_reverse_link(self, source):
		parent = self.source_docs.get(source.get("parent") or "primary")
		link_field = source.get("link_fieldname")
		if not parent or not link_field:
			return []

		parent_id = parent.get("name")
		if not parent_id:
			return []

		filters = {link_field: parent_id}
		filters.update(source.get("filters") or {})
		names = frappe.get_all(source["doctype"], filters=filters, pluck="name")
		return [frappe.get_cached_doc(source["doctype"], name).as_dict() for name in names]

	# =========================================================
	# Value resolution
	# =========================================================

	def _resolve_element(self, element):
		doc = self.source_docs.get(element.get("source"))

		# collection sources are not grouped yet (iteration 2)
		if isinstance(doc, list):
			return None

		value_spec = element.get("value_spec") or {}
		value = self._resolve_value_spec(value_spec, doc)

		if (value is None or value == "") and value_spec.get("default") is not None:
			value = value_spec["default"]

		return self._transform(element.get("datatype"), value)

	def _resolve_value_spec(self, value_spec, doc):
		kind = value_spec.get("kind")

		if kind == "fixed":
			return value_spec.get("value")
		if kind == "json":
			return value_spec.get("value")
		if kind == "field":
			return self._get_field(doc, value_spec.get("fieldname"))
		if kind == "expression":
			return self._eval_expression(value_spec.get("expression"), doc)
		return None

	def _get_field(self, doc, fieldname):
		if not doc or not fieldname:
			return None

		value = doc
		for part in str(fieldname).split("."):
			if not isinstance(value, dict):
				return None
			value = value.get(part)
			if value is None:
				return None
		return value

	def _eval_expression(self, expression, doc):
		if not expression:
			return None
		try:
			return frappe.safe_eval(expression, eval_locals={"doc": doc})
		except Exception as e:
			self.issues.append(f"Expression failed: {expression} - {e!s}")
			return None

	# =========================================================
	# Transformers
	# =========================================================

	def _transform(self, datatype, value):
		if value is None:
			return None

		datatype = (datatype or "").strip().lower()

		if datatype == "boolean":
			if isinstance(value, str):
				return value.strip().lower() in ("1", "true", "yes")
			return bool(value)
		if datatype in ("integer", "positiveint", "unsignedint"):
			try:
				return int(value)
			except (ValueError, TypeError):
				return None
		if datatype == "decimal":
			try:
				return float(value)
			except (ValueError, TypeError):
				return None
		if datatype == "date":
			return self._format_date(value)
		if datatype in ("datetime", "instant"):
			return self._format_datetime(value)
		if datatype == "string" or datatype in PRIMITIVE_STRING_TYPES:
			return str(value)

		# complex types / unknown datatypes pass through unchanged
		return value

	def _format_date(self, value):
		if hasattr(value, "strftime"):
			return value.strftime("%Y-%m-%d")
		return str(value)[:10]

	def _format_datetime(self, value):
		if hasattr(value, "isoformat"):
			return value.isoformat()
		return str(value)

	# =========================================================
	# Resource assembly
	# =========================================================

	def _write_path(self, resource, fhir_path, value, is_array):
		parts = self._relative_path(fhir_path).split(".")
		if not parts or parts == [""]:
			return

		current = resource
		for part in parts[:-1]:
			node = current.get(part)
			if not isinstance(node, dict):
				node = {}
				current[part] = node
			current = node

		leaf = parts[-1]
		if is_array:
			current.setdefault(leaf, [])
			if isinstance(value, list):
				current[leaf].extend(value)
			else:
				current[leaf].append(value)
		else:
			current[leaf] = value

	def _relative_path(self, fhir_path):
		prefix = f"{self.resource_type}."
		if self.resource_type and fhir_path.startswith(prefix):
			return fhir_path[len(prefix) :]
		return fhir_path

	def _prune(self, obj):
		if isinstance(obj, dict):
			pruned = {}
			for key, value in obj.items():
				cleaned = self._prune(value)
				if cleaned is not None:
					pruned[key] = cleaned
			return pruned or None
		if isinstance(obj, list):
			pruned = [self._prune(item) for item in obj]
			pruned = [item for item in pruned if item is not None]
			return pruned or None
		if obj == "" or obj is None:
			return None
		return obj
