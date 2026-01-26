import json

import frappe
from frappe.utils import cint, now_datetime


class FHIRMappingCompilationError(Exception):
	pass


class FHIRJsonHelpers:
	"""JSON parsing utilities for FHIR mappings."""

	@staticmethod
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

	@staticmethod
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

	@staticmethod
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

	@staticmethod
	def parse_extension_config(value):
		"""
		Parse extension_config JSON field.

		Expected format:
		{
			"url": "http://hl7.org/fhir/StructureDefinition/patient-religion",
			"value_datatype": "CodeableConcept",
			"is_modifier": false  // optional, defaults to false
		}

		Returns parsed dict or None if not an extension.
		"""
		if not value:
			return None

		if isinstance(value, dict):
			config = value
		else:
			text = str(value).strip()
			if not text:
				return None
			try:
				config = json.loads(text)
			except json.JSONDecodeError:
				return None

		if not isinstance(config, dict):
			return None

		# Must have at least url to be valid
		url = (config.get("url") or "").strip()
		if not url:
			return None

		return {
			"url": url,
			"value_datatype": (config.get("value_datatype") or "string").strip(),
			"is_modifier": bool(config.get("is_modifier", False)),
		}


class FHIRMappingCompiler:
	"""Compiles FHIR Resource Map into an executable mapping structure."""

	SUPPORTED_SOURCE_KINDS = {"direct_link", "reverse_link"}

	# Primitive FHIR types - arrays of these should be collected, not spread
	PRIMITIVE_TYPES = {
		"boolean",
		"integer",
		"integer64",
		"string",
		"decimal",
		"uri",
		"url",
		"canonical",
		"base64Binary",
		"instant",
		"date",
		"dateTime",
		"time",
		"code",
		"oid",
		"id",
		"markdown",
		"unsignedInt",
		"positiveInt",
		"uuid",
		"xhtml",
	}

	def __init__(self, resource_map):
		self.resource_map = resource_map
		self._sd_elements_map = {}

	@property
	def resource_type(self):
		return (self.resource_map.resource_type or "").strip()

	@property
	def primary_doctype(self):
		return (self.resource_map.primary_doctype or "").strip()

	@property
	def base_structure_definition(self):
		return (self.resource_map.base_structure_definition or "").strip()

	def compile(self):
		self._validate_required_fields()
		self._load_sd_elements()

		sources = self._compile_sources()
		self._validate_source_dependencies(sources)

		elements, element_order, warnings = self._compile_element_maps(sources)
		repeating_containers = self._compile_repeating_containers(elements)

		# Collect profile URLs from resource map
		profile_urls = self._collect_profile_urls()

		compiled = {
			"compiled_version": "fhir-map-compiled/v1",
			"meta": {
				"primary_doctype": self.primary_doctype,
				"base_structure_definition": self.base_structure_definition,
				"resource_type": self.resource_type,
				"compiled_at": str(now_datetime()),
				"profile_urls": profile_urls,
			},
			"sources": sources,
			"elements": elements,
			"element_order": element_order,
			"compile_warnings": warnings,
			"repeating_containers": repeating_containers,
		}

		self._apply_default_indexes(compiled)
		self._apply_is_array_flags(compiled)
		self._validate_output(compiled)

		return compiled

	def _validate_required_fields(self):
		if not self.primary_doctype:
			raise FHIRMappingCompilationError("primary_doctype is required.")
		if not self.resource_type:
			raise FHIRMappingCompilationError("resource_type is required.")

	def _collect_profile_urls(self):
		"""Collect profile URLs from the profiles child table."""
		urls = []
		for row in self.resource_map.get("profiles") or []:
			url = (row.get("url") or "").strip()
			if url and url not in urls:
				urls.append(url)
		return urls

	def _compile_sources(self):
		sources = {
			"primary": {
				"source_key": "primary",
				"kind": "primary",
				"doctype": self.primary_doctype,
			}
		}

		for row in self.resource_map.get("sources") or []:
			source = self._compile_single_source(row, sources)
			if source:
				sources[source["source_key"]] = source

		return sources

	def _compile_single_source(self, row, existing_sources):
		source_key = (row.get("source_key") or "").strip()
		kind = (row.get("kind") or "").strip()
		doctype = (row.get("source_doctype") or row.get("doctype") or "").strip()

		if not all([source_key, kind, doctype]):
			return None

		if source_key == "primary":
			raise FHIRMappingCompilationError("Do not add a source with key 'primary' in the sources table.")

		if kind not in self.SUPPORTED_SOURCE_KINDS:
			raise FHIRMappingCompilationError(
				f"Source '{source_key}': unsupported kind '{kind}'. "
				f"Supported: {sorted(self.SUPPORTED_SOURCE_KINDS)}"
			)

		if source_key in existing_sources:
			raise FHIRMappingCompilationError(f"Duplicate source_key '{source_key}'.")

		link_fieldname = (row.get("link_fieldname") or "").strip()
		if not link_fieldname:
			raise FHIRMappingCompilationError(
				f"Source '{source_key}': link_fieldname is required for '{kind}'."
			)

		spec = {
			"source_key": source_key,
			"kind": kind,
			"doctype": doctype,
			"link_fieldname": link_fieldname,
			"filters": FHIRJsonHelpers.parse_json_object(row.get("filters_json")) or {},
			"order_by": (row.get("order_by") or "").strip() or "creation desc",
		}

		# Optional fields
		for field, key in [
			("from_source_key", "from_source_key"),
			("lookup_fieldname", "lookup_fieldname"),
		]:
			value = (row.get(field) or "").strip()
			if value:
				spec[key] = value

		if row.get("limit"):
			spec["limit"] = int(row.get("limit"))

		return spec

	def _validate_source_dependencies(self, sources):
		for source_key, spec in sources.items():
			from_key = (spec.get("from_source_key") or "").strip()
			if from_key and from_key not in sources:
				raise FHIRMappingCompilationError(
					f"Source '{source_key}': from_source_key '{from_key}' does not exist. "
					f"Available sources: {sorted(sources.keys())}"
				)

		for source_key in sources:
			if source_key != "primary" and self._has_cycle(source_key, sources):
				raise FHIRMappingCompilationError(
					f"Source '{source_key}': circular dependency detected in from_source_key chain."
				)

	def _has_cycle(self, start_key, sources, visited=None):
		if visited is None:
			visited = set()

		if start_key in visited:
			return True

		visited.add(start_key)
		from_key = (sources.get(start_key, {}).get("from_source_key") or "").strip()

		if from_key and from_key != "primary":
			return self._has_cycle(from_key, sources, visited)

		return False

	def _load_sd_elements(self):
		if not self.base_structure_definition:
			self._sd_elements_map = {}
			return

		try:
			from healthcare.interoperability.doctype.fhir_resource_map.structure_def_loader import (
				FHIRStructureDefinitionLoader,
			)

			merged_rows = FHIRStructureDefinitionLoader(resource_map=self.resource_map).load_merged_elements()

			self._sd_elements_map = {
				(row.get("fhir_path") or "").strip(): row
				for row in merged_rows
				if (row.get("fhir_path") or "").strip()
			}
		except Exception:
			self._sd_elements_map = {}

	def _compile_element_maps(self, compiled_sources):
		elements = {}
		element_order = []
		warnings = []

		# Track extension indexes per parent path
		extension_indexes = {}

		for row in self.resource_map.get("element_maps") or []:
			result = self._compile_single_element(row, compiled_sources, warnings, extension_indexes)
			if result:
				fhir_path, element = result

				if fhir_path in elements:
					raise FHIRMappingCompilationError(
						f"Duplicate element mapping for fhir_path '{fhir_path}'."
					)
				elements[fhir_path] = element
				element_order.append(fhir_path)

		element_order.sort()
		return elements, element_order, warnings

	def _compile_single_element(self, row, compiled_sources, warnings, extension_indexes):
		fhir_path = (row.get("fhir_path") or "").strip()
		if not fhir_path:
			return None

		pointer = FHIRJsonHelpers.parse_value_pointer(row.get("value_pointer"))
		if not pointer:
			return None

		# Parse extension config
		extension_config = FHIRJsonHelpers.parse_extension_config(row.get("extension_config"))

		# Validate extension config if present
		if extension_config:
			self._validate_extension_config(fhir_path, extension_config, warnings)
		else:
			# Only validate path for non-extension elements
			self._validate_element_path(fhir_path, warnings)
			self._validate_choice_type(fhir_path, warnings)

		try:
			value_spec = self._build_value_spec(pointer, fhir_path, compiled_sources)
		except FHIRMappingCompilationError as exc:
			warnings.append(f"Skip '{fhir_path}': {exc}")
			return None

		sd_element = self._sd_elements_map.get(fhir_path, {})

		element = {
			"fhir_path": fhir_path,
			"op": "set",
			"base_json_path": self._to_json_path(fhir_path),
			"path": "",
			"value_spec": value_spec,
			"datatype": self._get_with_sd_fallback(row, sd_element, "datatype"),
			"regex": row.get("regex"),
			"min": cint(row.get("min") if row.get("min") is not None else sd_element.get("min", 0)),
			"max": (row.get("max") or sd_element.get("max") or "").strip()
			if isinstance(row.get("max") or sd_element.get("max") or "", str)
			else str(row.get("max") or sd_element.get("max") or ""),
			"valueset_url": self._get_with_sd_fallback(row, sd_element, "valueset_url"),
			"binding_strength": self._get_with_sd_fallback(row, sd_element, "binding_strength"),
			"is_choice_type": 1 if "[x]" in fhir_path else cint(row.get("is_choice_type")),
			"profile": (row.get("profile") or "").strip(),
			"target_profiles": FHIRJsonHelpers.normalize_string_list(row.get("target_profiles")),
		}

		# Add extension-specific fields if this is an extension
		if extension_config:
			element["is_extension"] = 1
			element["extension_url"] = extension_config["url"]
			element["value_datatype"] = extension_config["value_datatype"]
			element["is_modifier_extension"] = 1 if extension_config["is_modifier"] else 0

			# Override datatype to Extension
			element["datatype"] = "Extension"

			# Compute extension path with proper indexing
			element["base_json_path"] = self._compute_extension_base_path(
				fhir_path, extension_config, extension_indexes
			)

		return fhir_path, element

	def _validate_extension_config(self, fhir_path, config, warnings):
		"""Validate extension configuration."""
		url = config.get("url", "")

		# Warn if URL doesn't look like a valid extension URL
		if not url.startswith("http://") and not url.startswith("https://"):
			warnings.append(
				f"'{fhir_path}': extension URL '{url}' should be an absolute URL "
				f"(starting with http:// or https://)"
			)

		# Validate value_datatype is a known FHIR type
		value_datatype = config.get("value_datatype", "")
		known_value_types = {
			"boolean",
			"integer",
			"decimal",
			"string",
			"uri",
			"url",
			"canonical",
			"base64Binary",
			"instant",
			"date",
			"dateTime",
			"time",
			"code",
			"oid",
			"id",
			"markdown",
			"unsignedInt",
			"positiveInt",
			"uuid",
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
			"ContactDetail",
			"Contributor",
			"DataRequirement",
			"Expression",
			"ParameterDefinition",
			"RelatedArtifact",
			"TriggerDefinition",
			"UsageContext",
			"Dosage",
			"Meta",
		}

		if value_datatype and value_datatype not in known_value_types:
			warnings.append(
				f"'{fhir_path}': extension value_datatype '{value_datatype}' "
				f"is not a standard FHIR type. Proceeding anyway."
			)

	def _compute_extension_base_path(self, fhir_path, extension_config, extension_indexes):
		"""
		Compute the base JSON path for an extension.

		For "Patient.extension:religion" -> "extension"
		For "Patient.identifier.extension:verified" -> "identifier.extension"

		Handles multiple extensions on the same parent by tracking indexes.
		"""
		is_modifier = extension_config.get("is_modifier", False)
		ext_array_name = "modifierExtension" if is_modifier else "extension"

		# Parse fhir_path to find parent and extension slice name
		# Format: "Parent.path.extension:sliceName" or "Parent.extension:sliceName"

		parts = fhir_path.split(".")
		resource_type = parts[0] if parts else ""

		# Find the extension part (contains ":")
		ext_part_index = None
		for i, part in enumerate(parts):
			if ":" in part and ("extension" in part.lower() or "modifierextension" in part.lower()):
				ext_part_index = i
				break

		if ext_part_index is None:
			# No explicit extension notation, treat the whole path as extension target
			# e.g., "Patient.religion" as an extension
			parent_path = ".".join(parts[1:]) if len(parts) > 1 else ""
			parent_key = parent_path or "_root_"
		else:
			# Extract parent path (everything before extension:xxx)
			parent_parts = parts[1:ext_part_index]  # Skip resource type
			parent_path = ".".join(parent_parts) if parent_parts else ""
			parent_key = parent_path or "_root_"

		# Track extension index for this parent
		if parent_key not in extension_indexes:
			extension_indexes[parent_key] = {"extension": 0, "modifierExtension": 0}

		index = extension_indexes[parent_key][ext_array_name]
		extension_indexes[parent_key][ext_array_name] += 1

		# Build the base path
		if parent_path:
			return f"{parent_path}.{ext_array_name}[{index}]"
		else:
			return f"{ext_array_name}[{index}]"

	def _get_with_sd_fallback(self, row, sd_element, field):
		value = (row.get(field) or "").strip()
		if not value:
			value = (sd_element.get(field) or "").strip()
		return value

	def _validate_element_path(self, fhir_path, warnings):
		if not self._sd_elements_map:
			return

		if fhir_path in self._sd_elements_map:
			return

		# Check for valid concrete choice type (e.g., valueString for value[x])
		for sd_path in self._sd_elements_map:
			if "[x]" in sd_path:
				base = sd_path.replace("[x]", "")
				if fhir_path.startswith(base) and fhir_path != sd_path:
					return

		warnings.append(
			f"'{fhir_path}': path not found in structure definition. "
			f"This may be intentional for extensions or custom elements."
		)

	def _validate_choice_type(self, fhir_path, warnings):
		"""Warn only if the user explicitly mapped a path containing [x]."""
		if "[x]" in fhir_path:
			warnings.append(
				f"'{fhir_path}': Choice type paths should use concrete type names "
				f"(e.g., 'valueString' instead of 'value[x]'). "
				f"The [x] form may not generate valid FHIR."
			)

	def _build_value_spec(self, pointer, fhir_path, compiled_sources):
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

	def _to_json_path(self, fhir_path):
		fhir_path = (fhir_path or "").strip()
		prefix = f"{self.resource_type}."
		if self.resource_type and fhir_path.startswith(prefix):
			return fhir_path[len(prefix) :]
		return fhir_path

	def _compile_repeating_containers(self, elements):
		if not self._sd_elements_map or not elements:
			return {}

		repeating_paths = {
			path for path, el in self._sd_elements_map.items() if str(el.get("max") or "").strip() == "*"
		}

		if not repeating_paths:
			return {}

		result = {}
		for container_path in repeating_paths:
			prefix = f"{container_path}."
			for mapped_path in elements:
				if mapped_path == container_path or mapped_path.startswith(prefix):
					result[container_path] = 1
					break

		return result

	def _apply_default_indexes(self, compiled):
		path_builder = FHIRRepeatingPathBuilder()
		repeating_containers = compiled.get("repeating_containers") or {}

		for element in (compiled.get("elements") or {}).values():
			if not isinstance(element, dict):
				continue

			# Skip extensions - they already have their path computed
			if element.get("is_extension"):
				element["path"] = element.get("base_json_path", "")
				continue

			base_json_path = (element.get("base_json_path") or "").strip()
			element["path"] = (
				path_builder.build(
					resource_type=self.resource_type,
					base_json_path=base_json_path,
					repeating_containers=repeating_containers,
					default_index=0,
				)
				if base_json_path
				else ""
			)

	def _apply_is_array_flags(self, compiled):
		"""
		Apply is_array flag to elements based on their datatype and cardinality.

		is_array=True means the element is a primitive array (e.g., given, line)
		and list values should be COLLECTED into an array at that path.

		is_array=False (default) means list values should be SPREAD across
		parent container indexes (e.g., telecom[0], telecom[1]).

		Logic:
		- If element datatype is primitive AND max cardinality is "*" -> is_array=True
		- Otherwise -> is_array=False
		"""
		elements = compiled.get("elements") or {}

		for fhir_path, element in elements.items():
			if not isinstance(element, dict):
				continue

			# Get datatype and max cardinality
			datatype = (element.get("datatype") or "").strip()
			max_card = (element.get("max") or "").strip()

			# Determine if this is a primitive array
			is_primitive = self._is_primitive_type(datatype)
			is_repeating = max_card == "*"

			# Set is_array flag
			element["is_array"] = is_primitive and is_repeating

	def _is_primitive_type(self, datatype):
		"""
		Check if a datatype is a FHIR primitive type.

		Primitive types are simple value types (string, integer, etc.)
		as opposed to complex types (HumanName, Address, etc.)
		"""
		if not datatype:
			return False

		# Normalize: FHIR primitives are lowercase, complex types are PascalCase
		# But we check against our known set to be safe
		return datatype.lower() in self.PRIMITIVE_TYPES or datatype in self.PRIMITIVE_TYPES

	def _validate_output(self, compiled):
		sources = compiled.get("sources") or {}
		if not sources or "primary" not in sources:
			raise FHIRMappingCompilationError("primary source missing in compiled output.")

		if not frappe.in_test:
			elements = compiled.get("elements") or {}
			if not elements:
				raise FHIRMappingCompilationError("No compiled element mappings found.")


class FHIRRepeatingPathBuilder:
	"""Builds paths with array indexes for repeating containers."""

	def build(self, resource_type, base_json_path, repeating_containers, default_index=0):
		segments = [s for s in str(base_json_path or "").split(".") if s]
		if not segments:
			return base_json_path

		out = []
		prefix = ""

		for seg in segments:
			prefix = f"{prefix}.{seg}" if prefix else seg
			container_fhir_path = f"{resource_type}.{prefix}" if resource_type else prefix

			if (repeating_containers or {}).get(container_fhir_path):
				out.append(f"{seg}[{int(default_index)}]")
			else:
				out.append(seg)

		return ".".join(out)
