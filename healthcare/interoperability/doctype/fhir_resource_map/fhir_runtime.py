# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
FHIR Runtime

Executes a compiled FHIR Resource Map (see ``fhir_compiler.py``) against a
primary Frappe document to produce a FHIR resource dict, reading ONLY the
compiled mapping. Supports single-document sources, nested objects and primitive
arrays, collection-backed repeating backbones (source-driven grouping),
references, extensions and slices. Repeating complex backbones sourced from a
single document are wrapped into single-element arrays via ``array_paths``.
"""

import copy

from healthcare.interoperability.doctype.fhir_resource_map.fhir_source_loader import SourceLoader
from healthcare.interoperability.doctype.fhir_resource_map.fhir_value_resolver import ValueResolver


class FHIRRuntime:
	"""Generates a FHIR resource from a compiled mapping."""

	def __init__(self, compiled):
		self.compiled = compiled or {}
		self.meta = self.compiled.get("meta", {})
		self.sources_def = self.compiled.get("sources", {})
		self.elements = self.compiled.get("elements", {})
		self.extensions = self.compiled.get("extensions", [])
		self.slices = self.compiled.get("slices", [])
		self.array_paths = set(self.compiled.get("array_paths", []))
		self.resource_type = self.meta.get("resource_type")
		self.resolver = ValueResolver()
		self.source_docs = {}
		self.issues = []

	def generate(self, primary_id):
		self.source_docs = {}
		self.issues = []
		self.resolver.issues = []

		self._load_sources(primary_id)

		resource = {"resourceType": self.resource_type}
		for path, value, is_array in self._collect_writes():
			if value is None:
				continue
			parts = self._relative_path(path).split(".")
			self._insert(resource, self.resource_type, parts, value, is_array)

		return self._prune(resource) or {"resourceType": self.resource_type}

	def _load_sources(self, primary_id):
		loader = SourceLoader(self.sources_def)
		self.source_docs = loader.load(primary_id)
		self.issues = loader.issues

	# =========================================================
	# Writes (scalar + collection + slice + extension)
	# =========================================================

	def _collect_writes(self):
		return [
			*self._scalar_writes(),
			*self._collection_writes(),
			*self._slice_writes(),
			*self._extension_writes(),
		]

	def _scalar_writes(self):
		writes = []
		for path, element in self.elements.items():
			if self._is_collection_element(element):
				continue

			doc = self.source_docs.get(element.get("source"))
			if isinstance(doc, list):
				continue

			value = self.resolver.resolve(element, doc)
			if value is not None:
				writes.append((path, value, bool(element.get("is_array"))))
		return writes

	def _collection_writes(self):
		writes = []
		for key, source in self.sources_def.items():
			if not source.get("is_collection"):
				continue

			backbone = source.get("fhir_path")
			rows = self.source_docs.get(key)
			if not backbone or not isinstance(rows, list):
				continue

			bound = self._elements_for_source(key)
			items = [item for row in rows if (item := self._build_item(bound, backbone, row))]
			if items:
				writes.append((backbone, items, False))
		return writes

	def _build_item(self, bound_elements, backbone, row):
		item = {}
		prefix = f"{backbone}."
		for path, element in bound_elements:
			if not path.startswith(prefix):
				continue
			value = self.resolver.resolve(element, row)
			if value is not None:
				parts = path[len(prefix) :].split(".")
				self._insert(item, backbone, parts, value, bool(element.get("is_array")))
		return item

	def _slice_writes(self):
		grouped = {}
		for compiled_slice in self.slices:
			path = compiled_slice.get("path")
			if not path:
				continue
			items = self._build_slice_items(compiled_slice)
			if items:
				grouped.setdefault(path, []).extend(items)

		return [(path, items, False) for path, items in grouped.items()]

	def _build_slice_items(self, compiled_slice):
		doc = self.source_docs.get(compiled_slice.get("source") or "primary")
		rows = doc if isinstance(doc, list) else [doc]
		return [item for row in rows if (item := self._build_slice_item(compiled_slice, row))]

	def _build_slice_item(self, compiled_slice, doc):
		item = copy.deepcopy(compiled_slice.get("pattern") or {})
		for sub in compiled_slice.get("elements", []):
			value = self.resolver.resolve(sub, doc)
			if value is not None:
				self._insert(
					item, compiled_slice["path"], sub["path"].split("."), value, bool(sub.get("is_array"))
				)
		return item or None

	def _extension_writes(self):
		grouped = {}
		for extension in self.extensions:
			host = extension.get("host") or self.resource_type
			field = "modifierExtension" if extension.get("is_modifier") else "extension"
			items = self._build_extension_items(extension)
			if items:
				grouped.setdefault((host, field), []).extend(items)

		return [(f"{host}.{field}", items, False) for (host, field), items in grouped.items()]

	def _build_extension_items(self, extension):
		source = extension.get("source") or "primary"
		doc = self.source_docs.get(source)
		rows = doc if isinstance(doc, list) else [doc]

		value_type = extension.get("value_type") or "valueString"
		datatype = self._extension_datatype(value_type)
		value_spec = extension.get("value_spec") or {}

		items = []
		for row in rows:
			value = self.resolver.resolve_value_spec(value_spec, row)
			if (value is None or value == "") and value_spec.get("default") is not None:
				value = value_spec["default"]
			value = self.resolver.transform(datatype, value)
			if value is not None:
				items.append({"url": extension.get("url"), value_type: value})
		return items

	def _extension_datatype(self, value_type):
		if not value_type or not value_type.startswith("value"):
			return "string"
		return value_type[len("value") :].lower()

	def _is_collection_element(self, element):
		source = self.sources_def.get(element.get("source"), {})
		return bool(source.get("is_collection"))

	def _elements_for_source(self, key):
		return [(path, element) for path, element in self.elements.items() if element.get("source") == key]

	# =========================================================
	# Assembly
	# =========================================================

	def _insert(self, node, base_path, parts, value, is_array):
		"""Insert ``value`` at ``parts`` under ``node`` (whose absolute path is ``base_path``).

		Intermediate segments listed in ``array_paths`` are materialised as
		single-element arrays so repeating complex backbones render correctly.
		"""
		absolute = base_path
		for part in parts[:-1]:
			absolute = f"{absolute}.{part}"
			if absolute in self.array_paths:
				node[part] = self._as_object_list(node.get(part))
				node = node[part][0]
			else:
				if not isinstance(node.get(part), dict):
					node[part] = {}
				node = node[part]

		leaf = parts[-1]
		if is_array:
			node.setdefault(leaf, [])
			node[leaf].extend(value if isinstance(value, list) else [value])
		elif isinstance(value, list) and isinstance(node.get(leaf), list):
			# combine arrays feeding the same path (e.g. a collection plus slices)
			node[leaf].extend(value)
		else:
			node[leaf] = value

	def _as_object_list(self, child):
		if isinstance(child, list):
			if not child or not isinstance(child[0], dict):
				child.insert(0, {})
			return child
		if isinstance(child, dict):
			return [child]
		return [{}]

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
