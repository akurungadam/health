# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Source loading for the FHIR runtime.

Loads the source documents named in a compiled mapping. Single-document sources
(primary / direct_link / document) return a dict; collection sources
(child_table / reverse_link) return a list of dicts. Dependent sources read
their already-loaded parent from the in-progress docs map.
"""

import frappe


class SourceLoader:
	"""Loads compiled-mapping sources into a {key: doc-or-rows} map."""

	def __init__(self, sources_def):
		self.sources_def = sources_def
		self.issues = []

	def load(self, primary_id):
		docs = {}
		primary = self._primary_source()
		if primary:
			docs["primary"] = self._load_primary(primary, primary_id)

		for key, source in self.sources_def.items():
			if not source.get("is_primary"):
				docs[key] = self._load(source, docs)
		return docs

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

	def _load(self, source, docs):
		kind = source.get("kind")
		if kind == "direct_link":
			return self._direct_link(source, docs)
		if kind == "child_table":
			return self._child_table(source, docs)
		if kind == "reverse_link":
			return self._reverse_link(source, docs)
		if kind == "dynamic_link":
			return self._dynamic_link(source, docs)
		return self._document(source)

	def _direct_link(self, source, docs):
		parent = docs.get(source.get("parent") or "primary")
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

	def _document(self, source):
		filters = source.get("filters") or {}
		if not filters:
			return None
		names = frappe.get_all(source["doctype"], filters=filters, pluck="name", limit=1)
		return frappe.get_cached_doc(source["doctype"], names[0]).as_dict() if names else None

	def _child_table(self, source, docs):
		parent = docs.get(source.get("parent") or "primary")
		field = source.get("link_fieldname")
		if not parent or not field:
			return []

		rows = parent.get(field) or []
		# child rows from as_dict() are already (frappe._)dicts; only Documents need as_dict()
		return [row if isinstance(row, dict) else row.as_dict() for row in rows]

	def _reverse_link(self, source, docs):
		parent = docs.get(source.get("parent") or "primary")
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

	def _dynamic_link(self, source, docs):
		"""Children linked to the parent via Frappe's standard Dynamic Link table
		(e.g. Address/Contact linked to Patient through their ``links`` table)."""
		parent = docs.get(source.get("parent") or "primary")
		if not parent:
			return []

		parent_doctype = parent.get("doctype")
		parent_id = parent.get("name")
		if not parent_doctype or not parent_id:
			return []

		names = frappe.get_all(
			"Dynamic Link",
			filters={
				"link_doctype": parent_doctype,
				"link_name": parent_id,
				"parenttype": source["doctype"],
			},
			pluck="parent",
		)
		unique_names = list(dict.fromkeys(names))
		return [frappe.get_cached_doc(source["doctype"], name).as_dict() for name in unique_names]
