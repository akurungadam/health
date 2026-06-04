# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Warn-only validation of a compiled mapping against the merged StructureDefinition.

Validation never blocks saving - it only returns warnings. Required elements are
considered satisfied when the element, any descendant, or a slice under them is
mapped (in UI rows or custom_elements). Resolved choice expansions (foo[x] ->
fooString) are not flagged as unknown.
"""

import frappe
from frappe.utils import cint


class MappingValidator:
	"""Produces warnings for a compiled mapping against an SD element index."""

	def __init__(self, sd_index):
		self.sd_index = sd_index

	def validate(self, compiled):
		warnings = []
		self._required(compiled, warnings)
		self._unknown_mapped(compiled, warnings)
		self._complex_as_scalar(compiled, warnings)
		self._unknown_sources(compiled, warnings)
		self._source_doctypes(compiled, warnings)
		return warnings

	def _required(self, compiled, warnings):
		covered = self._covered_paths(compiled)
		for path, sd in self.sd_index.items():
			if cint(sd.get("min")) < 1 or "[x]" in path:
				continue
			if self._is_covered(path, covered) or self._gated_by_optional(path, covered):
				continue
			warnings.append(f"Required element '{path}' is not mapped.")

	def _gated_by_optional(self, path, covered):
		"""True if a required element sits under an optional (min=0) ancestor that
		is not mapped - then the requirement does not apply (e.g. Patient.link.type
		is only required when Patient.link is present)."""
		parts = path.split(".")
		for end in range(2, len(parts)):
			ancestor = ".".join(parts[:end])
			sd = self.sd_index.get(ancestor)
			if sd and cint(sd.get("min")) == 0 and not self._is_covered(ancestor, covered):
				return True
		return False

	def _unknown_mapped(self, compiled, warnings):
		if not self.sd_index:
			return
		for path in compiled["elements"]:
			if path in self.sd_index or "[x]" in path or self._is_choice_expansion(path):
				continue
			# Resource SDs don't enumerate the internals of complex datatypes
			# (e.g. CodeableConcept.coding.system), so drilling into a known
			# complex element is valid even though the deep path isn't listed.
			if self._extends_complex_element(path):
				continue
			warnings.append(f"Mapped element '{path}' is not in the merged StructureDefinition.")

	def _extends_complex_element(self, path):
		"""True if the nearest SD ancestor of ``path`` is a complex datatype."""
		parts = path.split(".")
		for end in range(len(parts) - 1, 1, -1):
			sd = self.sd_index.get(".".join(parts[:end]))
			if sd is None:
				continue
			datatype = (sd.get("datatype") or "").strip()
			# primitive datatypes are lower-cased; complex (or unknown) are not
			return not (datatype and datatype[0].islower())
		return False

	def _complex_as_scalar(self, compiled, warnings):
		"""Warn when a complex-datatype element is fed a bare scalar.

		The runtime passes complex/unknown datatypes through unchanged, so mapping
		e.g. CodeableConcept or HumanName to a plain field yields a string where a
		FHIR validator expects an object. References are excluded (the resolver
		builds their object), as are object-valued json/fixed specs and expressions.
		"""
		for path, element in compiled["elements"].items():
			datatype = (element.get("datatype") or "").strip() or self._sd_datatype(path)
			if self._is_complex_datatype(datatype) and self._is_scalar_value_spec(element.get("value_spec")):
				warnings.append(
					f"Element '{path}' has complex datatype '{datatype}' but is mapped to a scalar value; "
					f"author it as an object (value_spec kind 'json') or map its sub-elements."
				)

	def _sd_datatype(self, path):
		return (self.sd_index.get(path, {}).get("datatype") or "").strip()

	def _is_complex_datatype(self, datatype):
		"""Complex datatypes are capitalised (CodeableConcept, HumanName, ...);
		primitives are lower-cased. References build their own object, so skip them."""
		if not datatype or datatype.lower() == "reference":
			return False
		return not datatype[0].islower()

	def _is_scalar_value_spec(self, value_spec):
		"""True when the spec yields a plain scalar (a field, or a non-object fixed).

		A value ``map`` whose entries are objects (e.g. a local code translated
		straight to a CodeableConcept) makes the resolved value an object, so such
		a spec is not treated as scalar.
		"""
		value_spec = value_spec or {}
		if self._map_yields_object(value_spec):
			return False
		kind = value_spec.get("kind")
		if kind == "field":
			return True
		if kind == "fixed":
			return not isinstance(value_spec.get("value"), dict | list)
		return False

	def _map_yields_object(self, value_spec):
		mapping = value_spec.get("map")
		return isinstance(mapping, dict) and any(isinstance(value, dict | list) for value in mapping.values())

	def _unknown_sources(self, compiled, warnings):
		sources = compiled["sources"]
		for path, element in compiled["elements"].items():
			source_key = element.get("source")
			if source_key and source_key not in sources:
				warnings.append(f"Element '{path}' references unknown source '{source_key}'.")

	def _source_doctypes(self, compiled, warnings):
		for key, source in compiled["sources"].items():
			doctype = (source.get("doctype") or "").strip()
			if not doctype:
				warnings.append(f"Source '{key}' has no doctype.")
			elif not frappe.db.exists("DocType", doctype):
				warnings.append(f"Source '{key}' references non-existent doctype '{doctype}'.")

	# =========================================================
	# Coverage / choice helpers
	# =========================================================

	def _covered_paths(self, compiled):
		"""All FHIR paths populated by elements, slices and their patterns/objects."""
		covered = set()
		for path, element in compiled["elements"].items():
			covered.add(path)
			covered |= self._object_paths(path, element.get("value_spec"))

		for compiled_slice in compiled.get("slices", []):
			base = compiled_slice["path"]
			covered.add(base)
			covered |= self._flatten(base, compiled_slice.get("pattern") or {})
			for sub in compiled_slice.get("elements", []):
				sub_path = f"{base}.{sub['path']}"
				covered.add(sub_path)
				covered |= self._object_paths(sub_path, sub.get("value_spec"))
		return covered

	def _object_paths(self, path, value_spec):
		"""Paths populated by a json/fixed object value (so its keys count as mapped)."""
		value_spec = value_spec or {}
		if value_spec.get("kind") in ("json", "fixed") and isinstance(value_spec.get("value"), dict | list):
			return self._flatten(path, value_spec["value"])
		return set()

	def _flatten(self, base, value):
		paths = set()
		if isinstance(value, dict):
			for key, child in value.items():
				child_path = f"{base}.{key}"
				paths.add(child_path)
				paths |= self._flatten(child_path, child)
		elif isinstance(value, list):
			for item in value:
				paths |= self._flatten(base, item)
		return paths

	def _is_covered(self, path, covered_paths):
		"""Satisfied if the path - or any descendant of it - is mapped."""
		if path in covered_paths:
			return True
		prefix = f"{path}."
		return any(covered.startswith(prefix) for covered in covered_paths)

	def _is_choice_expansion(self, path):
		"""A concrete choice (e.g. Patient.deceasedBoolean) of an SD foo[x] element."""
		if "." not in path:
			return False

		parent, leaf = path.rsplit(".", 1)
		for sd_path in self.sd_index:
			if "[x]" not in sd_path:
				continue
			sd_parent, sd_leaf = sd_path.rsplit(".", 1)
			base = sd_leaf[:-3]
			if (
				sd_parent == parent
				and base
				and leaf.lower().startswith(base.lower())
				and len(leaf) > len(base)
			):
				return True
		return False
