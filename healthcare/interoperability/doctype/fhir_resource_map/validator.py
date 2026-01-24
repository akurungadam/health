import frappe
from frappe.utils import cint


class FHIRMappingValidator:
	"""
	Validates compiled mapping against merged SD.

	Enforcing validations:
	- Required elements (SD min >= 1) must be mapped (unless choice base path)
	- Choice types: if SD has foo[x], enforce exactly one concrete fooBar mapping (and required when min>=1)
	- Mapped elements must exist in merged SD (default: ERROR)
	- Required bindings should have valueset_url (warning)
	- Sources reference valid doctypes and link fields
	- Backbone elements: if any child mapped, required children must be mapped
	- Cardinality alignment (best-effort warnings):
	  - SD max != "*" but fieldname looks repeating (dot path) -> warning
	  - SD max == "*" but fieldname looks scalar -> warning
	"""

	CODE_TYPES = ["code", "Coding", "CodeableConcept"]

	COMPLEX_TYPES_WITH_BUILDERS = [
		"HumanName",
		"Address",
		"ContactPoint",
		"Identifier",
		"Reference",
		"CodeableConcept",
		"Quantity",
		"Period",
		"Narrative",
		"Coding",
	]

	def __init__(self, compiled_map, sd_elements):
		self.compiled_map = compiled_map
		self.sd_elements = sd_elements
		self.errors = []
		self.warnings = []
		self._sd_elements_map = {}
		self._backbone_elements = {}
		self._complex_type_paths = {}
		self._mapped_paths = set()
		self._build_sd_index()

	def _build_sd_index(self):
		elements = self.compiled_map.get("elements", {}) or {}
		self._mapped_paths = set(elements.keys())

		for element in self.sd_elements:
			fhir_path = (element.get("fhir_path") or "").strip()
			if not fhir_path:
				continue

			self._sd_elements_map[fhir_path] = element

			datatype = (element.get("datatype") or "").strip()
			if datatype in self.COMPLEX_TYPES_WITH_BUILDERS:
				self._complex_type_paths[fhir_path] = datatype

		self._identify_backbone_elements()

	def _identify_backbone_elements(self):
		all_paths = set(self._sd_elements_map.keys())

		for fhir_path, element in self._sd_elements_map.items():
			datatype = (element.get("datatype") or "").strip()

			# primitives are never backbone
			if datatype and datatype[0].islower():
				continue

			# complex types with builders: children handled elsewhere
			if datatype in self.COMPLEX_TYPES_WITH_BUILDERS:
				continue

			prefix = fhir_path + "."
			children = [p for p in all_paths if p.startswith(prefix) and "." not in p[len(prefix) :]]
			if not children:
				continue

			required_children = []
			for child_path in children:
				child_element = self._sd_elements_map.get(child_path, {}) or {}
				if cint(child_element.get("min")) >= 1:
					child_name = child_path[len(prefix) :]
					required_children.append(child_name)

			if required_children:
				self._backbone_elements[fhir_path] = {
					"required_children": required_children,
					"all_children": [p[len(prefix) :] for p in children],
				}

	def validate(self):
		self.errors = []
		self.warnings = []

		self._validate_unknown_mapped_elements()  # enforcing
		self._validate_choice_types()  # enforcing
		self._validate_required_elements()
		self._validate_required_bindings()
		self._validate_sources()
		self._validate_backbone_elements()
		self._validate_cardinality_alignment()

		return {
			"is_valid": len(self.errors) == 0,
			"errors": self.errors,
			"warnings": self.warnings,
			"error_count": len(self.errors),
			"warning_count": len(self.warnings),
		}

	# =========================================================
	# Enforcing: mapped elements must exist in merged SD
	# =========================================================

	def _validate_unknown_mapped_elements(self):
		for mapped_path in self._mapped_paths:
			if mapped_path in self._sd_elements_map:
				continue

			# Choice types: allow mappings like Patient.deceasedBoolean when SD contains Patient.deceased[x]
			if self._is_choice_expansion_path(mapped_path):
				continue

			self.errors.append(
				{
					"type": "mapped_not_in_sd",
					"fhir_path": mapped_path,
					"message": f"Mapped element '{mapped_path}' not found in merged StructureDefinition (typo/stale mapping).",
				}
			)

	def _is_choice_expansion_path(self, mapped_path):
		"""
		Returns True if mapped_path looks like a valid concrete choice expansion
		of an SD element ending with [x], e.g.:
		mapped: Patient.deceasedBoolean
		sd:     Patient.deceased[x]
		"""
		base_choice_path = self._to_choice_base_path(mapped_path)
		if not base_choice_path:
			return False

		return base_choice_path in self._sd_elements_map

	def _to_choice_base_path(self, mapped_path):
		"""
		Convert concrete choice expansion into [x] base path.
		Example:
		Patient.deceasedBoolean -> Patient.deceased[x]
		Patient.multipleBirthInteger -> Patient.multipleBirth[x]
		Returns None if it doesn't look like a choice expansion.
		"""
		if not mapped_path or "." not in mapped_path:
			return None

		leaf = mapped_path.split(".")[-1]
		parent = ".".join(mapped_path.split(".")[:-1])

		# Common FHIR choice suffixes (match your UI list)
		# Add/remove based on what you allow users to pick.
		choice_suffixes = (
			"Boolean",
			"Integer",
			"Decimal",
			"String",
			"Date",
			"DateTime",
			"Time",
			"Uri",
			"Url",
			"Canonical",
			"Code",
			"Id",
			"Markdown",
			"Base64Binary",
			"Oid",
			"Uuid",
			"PositiveInt",
			"UnsignedInt",
			"Instant",
			# Complex choices (if you allow them in UI)
			"Address",
			"Age",
			"Annotation",
			"Attachment",
			"CodeableConcept",
			"Coding",
			"ContactPoint",
			"Count",
			"Distance",
			"Duration",
			"HumanName",
			"Identifier",
			"Money",
			"Period",
			"Quantity",
			"Range",
			"Ratio",
			"Reference",
			"SampledData",
			"Signature",
			"Timing",
			"Meta",
		)

		matched_suffix = None
		for suffix in choice_suffixes:
			if leaf.endswith(suffix) and len(leaf) > len(suffix):
				matched_suffix = suffix
				break

		if not matched_suffix:
			return None

		base_leaf = leaf[: -len(matched_suffix)]
		return f"{parent}.{base_leaf}[x]"

	# =========================================================
	# Enforcing: choice types
	# =========================================================

	def _validate_choice_types(self):
		"""
		If SD has foo[x]:
		- if min>=1 -> at least one concrete choice must be mapped (fooString/fooQuantity/...)
		- never allow multiple concrete choices mapped under same base
		"""
		choice_bases = {}
		for sd_path, sd_row in self._sd_elements_map.items():
			if "[x]" not in sd_path:
				continue
			base = sd_path.replace("[x]", "")
			choice_bases[base] = {
				"sd_path": sd_path,
				"min": cint(sd_row.get("min")),
			}

		if not choice_bases:
			return

		for base, info in choice_bases.items():
			# any mapped path starting with base counts as a concrete choice
			# NOTE: we do not count the base foo[x] itself (rarely mapped directly)
			concrete = [p for p in self._mapped_paths if p.startswith(base) and "[x]" not in p]

			# If someone mapped foo[x] directly, it doesn't help; still enforce a concrete.
			concrete = [p for p in concrete if p != info["sd_path"]]

			if info["min"] >= 1 and not concrete:
				self.errors.append(
					{
						"type": "choice_required_missing",
						"fhir_path": info["sd_path"],
						"message": f"Choice element '{info['sd_path']}' is required (min=1) but no concrete choice is mapped (e.g., '{base}String').",
					}
				)
				continue

			if len(concrete) > 1:
				self.errors.append(
					{
						"type": "choice_multiple_mapped",
						"fhir_path": info["sd_path"],
						"message": f"Choice element '{info['sd_path']}' has multiple mapped choices: {sorted(concrete)}. Map only one.",
					}
				)

	# =========================================================
	# Required elements
	# =========================================================

	def _validate_required_elements(self):
		"""Check that all required (min >= 1) elements are mapped."""
		elements = self.compiled_map.get("elements", {}) or {}

		for sd_element in self.sd_elements:
			fhir_path = (sd_element.get("fhir_path") or "").strip()
			min_card = cint(sd_element.get("min"))

			if not fhir_path or min_card < 1:
				continue

			# Choice base paths are handled by _validate_choice_types()
			if "[x]" in fhir_path:
				continue

			if fhir_path in self._mapped_paths:
				element = elements.get(fhir_path) or {}
				value_spec = element.get("value_spec") or {}
				kind = (value_spec.get("kind") or "").strip()

				if not kind:
					self.errors.append(
						{
							"type": "required_no_mapping",
							"fhir_path": fhir_path,
							"message": f"Required element '{fhir_path}' has no valid value_spec.kind",
						}
					)
			else:
				self.errors.append(
					{
						"type": "required_missing",
						"fhir_path": fhir_path,
						"message": f"Required element '{fhir_path}' (min={min_card}) is not mapped",
					}
				)

	# =========================================================
	# Required bindings
	# =========================================================

	def _validate_required_bindings(self):
		"""Warn when code elements have required binding but no valueset."""
		elements = self.compiled_map.get("elements", {}) or {}

		for fhir_path, element in elements.items():
			datatype = (element.get("datatype") or "").strip()
			if datatype not in self.CODE_TYPES:
				continue

			binding_strength = (element.get("binding_strength") or "").strip().lower()
			valueset_url = (element.get("valueset_url") or "").strip()

			if binding_strength == "required" and not valueset_url:
				self.warnings.append(
					{
						"type": "code_no_valueset",
						"fhir_path": fhir_path,
						"message": f"'{fhir_path}' has required binding but no valueset_url.",
					}
				)

	# =========================================================
	# Sources
	# =========================================================

	def _validate_sources(self):
		"""Validate that sources reference valid doctypes and fields."""
		sources = self.compiled_map.get("sources", {}) or {}

		for source_key, source_config in sources.items():
			doctype = (source_config.get("doctype") or "").strip()

			if not doctype:
				self.errors.append(
					{
						"type": "source_no_doctype",
						"source_key": source_key,
						"message": f"Source '{source_key}' has no doctype defined.",
					}
				)
				continue

			if not frappe.db.exists("DocType", doctype):
				self.errors.append(
					{
						"type": "source_invalid_doctype",
						"source_key": source_key,
						"message": f"Source '{source_key}' references non-existent doctype '{doctype}'.",
					}
				)
				continue

			kind = (source_config.get("kind") or "").strip()
			if kind in ["direct_link", "reverse_link"]:
				link_fieldname = (source_config.get("link_fieldname") or "").strip()

				if not link_fieldname:
					self.errors.append(
						{
							"type": "source_no_link_field",
							"source_key": source_key,
							"message": f"Source '{source_key}' ({kind}) has no link_fieldname defined.",
						}
					)
				else:
					self._validate_field_exists(source_key, doctype, link_fieldname, kind)

	def _validate_field_exists(self, source_key, doctype, fieldname, kind):
		"""Check if a field exists in the doctype (best-effort)."""
		if kind == "direct_link":
			primary_doctype = (self.compiled_map.get("meta", {}) or {}).get("primary_doctype", "")
			check_doctype = (primary_doctype or "").strip()
		else:
			check_doctype = (doctype or "").strip()

		if not check_doctype:
			return

		try:
			meta = frappe.get_meta(check_doctype)
			field_exists = fieldname == "name" or any(df.fieldname == fieldname for df in meta.fields)

			if not field_exists:
				self.warnings.append(
					{
						"type": "source_field_not_found",
						"source_key": source_key,
						"message": f"Source '{source_key}': field '{fieldname}' not found in '{check_doctype}'. May be custom field or child table.",
					}
				)
		except Exception:
			pass

	# =========================================================
	# Backbone elements
	# =========================================================

	def _validate_backbone_elements(self):
		"""Validate backbone elements have all required sub-elements."""
		elements = self.compiled_map.get("elements", {}) or {}

		for backbone_path, backbone_info in self._backbone_elements.items():
			backbone_mapped = any(
				fp == backbone_path or fp.startswith(backbone_path + ".") for fp in self._mapped_paths
			)
			if not backbone_mapped:
				continue

			for child_name in backbone_info.get("required_children", []):
				child_path = f"{backbone_path}.{child_name}"

				if child_path not in elements:
					self.errors.append(
						{
							"type": "backbone_missing_required",
							"fhir_path": child_path,
							"message": f"Backbone '{backbone_path}' is mapped but required child '{child_name}' is missing.",
						}
					)
					continue

				child_element = elements.get(child_path) or {}
				child_value_spec = child_element.get("value_spec") or {}
				kind = (child_value_spec.get("kind") or "").strip()

				if not kind:
					self.errors.append(
						{
							"type": "backbone_child_no_mapping",
							"fhir_path": child_path,
							"message": f"Required child '{child_name}' of backbone '{backbone_path}' has no valid mapping.",
						}
					)

	# =========================================================
	# Cardinality alignment (best-effort)
	# =========================================================

	def _validate_cardinality_alignment(self):
		"""
		Heuristic checks only. We can't know runtime values here, but we can catch obvious mismatches.
		"""
		elements = self.compiled_map.get("elements", {}) or {}

		for fhir_path in self._mapped_paths:
			sd_row = self._sd_elements_map.get(fhir_path) or {}
			max_card = str(sd_row.get("max") or "").strip() or "1"

			element = elements.get(fhir_path) or {}
			value_spec = element.get("value_spec") or {}
			if (value_spec.get("kind") or "").strip() != "field":
				continue

			fieldname = (value_spec.get("fieldname") or "").strip()
			if not fieldname:
				continue

			looks_repeating = "." in fieldname

			if max_card != "*" and looks_repeating:
				self.warnings.append(
					{
						"type": "cardinality_maybe_list_into_single",
						"fhir_path": fhir_path,
						"message": f"'{fhir_path}' has SD max={max_card} but mapped field '{fieldname}' looks repeating (dot path). Double-check list->single mismatch.",
					}
				)

			if max_card == "*" and not looks_repeating:
				self.warnings.append(
					{
						"type": "cardinality_scalar_into_repeat",
						"fhir_path": fhir_path,
						"message": f"'{fhir_path}' is repeating (max='*') but mapped field '{fieldname}' looks scalar. If you expect multiple rows, map a list/child-table source.",
					}
				)
