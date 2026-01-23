# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import hashlib
import json
import re
from datetime import date, datetime

import frappe
from frappe.model.document import Document
from frappe.utils import cint, now_datetime


class FHIRMappingCompilationError(Exception):
	pass


# =========================================================
# Common Utilities
# =========================================================


class FHIRUtils:
	"""Shared utility methods used across FHIR classes."""

	FHIR_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-\.]{1,64}$")

	@staticmethod
	def get_dotted_value(data, fieldname):
		"""
		Traverse nested dict/list using dot notation.
		Returns full list when a child table (list) is encountered.
		"""
		if data is None or not fieldname:
			return None

		parts = fieldname.split(".")
		current = data

		for part in parts:
			if current is None:
				return None

			if isinstance(current, dict):
				current = current.get(part)
			elif isinstance(current, list):
				return current
			else:
				current = getattr(current, part, None)

		return current

	@staticmethod
	def is_empty(value):
		"""Check if value is None or empty list."""
		if value is None:
			return True
		if isinstance(value, list) and len(value) == 0:
			return True
		return False

	@staticmethod
	def parse_path(path):
		"""
		Parse FHIR path into segments.
		e.g., "identifier[0].value" -> ["identifier", 0, "value"]
		"""
		if not path:
			return []

		segments = []
		parts = path.split(".")

		for part in parts:
			match = re.match(r"(\w+)\[(\d+)\]", part)
			if match:
				segments.append(match.group(1))
				segments.append(int(match.group(2)))
			else:
				segments.append(part)

		return segments

	@staticmethod
	def extract_resource_type(profile_url):
		"""Extract resource type from profile URL."""
		if not profile_url:
			return None
		parts = profile_url.rstrip("/").split("/")
		return parts[-1] if parts else None

	@staticmethod
	def to_fhir_id(value):
		r"""
		Convert a value to a valid FHIR ID.
		FHIR IDs must match: [A-Za-z0-9\-\.]{1,64}
		"""
		if not value:
			return None

		value_str = str(value).strip()

		# If already valid, return as-is
		if FHIRUtils.FHIR_ID_PATTERN.match(value_str) and len(value_str) <= 64:
			return value_str

		# Replace spaces and invalid characters with hyphens
		cleaned = re.sub(r"[^A-Za-z0-9\-\.]", "-", value_str)

		# Remove consecutive hyphens
		cleaned = re.sub(r"-+", "-", cleaned)

		# Remove leading/trailing hyphens
		cleaned = cleaned.strip("-")

		# Truncate to 64 characters
		if len(cleaned) > 64:
			cleaned = cleaned[:64].rstrip("-")

		return cleaned if cleaned else None


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
		except Exception:
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
			except Exception:
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
				except Exception:
					return []

			return [text]

		return []


class FHIRValueTransformer:
	"""Transforms values from Frappe format to FHIR format."""

	DATE_FORMATS = [
		"%Y-%m-%d",  # ISO format (FHIR standard)
		"%d-%m-%Y",  # DD-MM-YYYY
		"%d/%m/%Y",  # DD/MM/YYYY
		"%m/%d/%Y",  # MM/DD/YYYY (US)
		"%Y/%m/%d",  # YYYY/MM/DD
		"%d.%m.%Y",  # DD.MM.YYYY (European)
	]

	@staticmethod
	def transform_date(value):
		"""Convert various date formats to FHIR date format (YYYY-MM-DD)."""
		if not value:
			return None

		# Already a date object
		if isinstance(value, date):
			return value.strftime("%Y-%m-%d")

		# Already a datetime object
		if isinstance(value, datetime):
			return value.strftime("%Y-%m-%d")

		# String value
		value_str = str(value).strip()
		if not value_str:
			return None

		# Already in correct format
		if re.match(r"^\d{4}-\d{2}-\d{2}$", value_str):
			return value_str

		# Try parsing with various formats
		for fmt in FHIRValueTransformer.DATE_FORMATS:
			try:
				parsed = datetime.strptime(value_str, fmt)
				return parsed.strftime("%Y-%m-%d")
			except ValueError:
				continue

		# Return as-is if all parsing fails
		return value_str

	@staticmethod
	def transform_boolean(value):
		"""Convert various boolean representations to Python boolean."""
		if value is None:
			return None

		if isinstance(value, bool):
			return value

		if isinstance(value, (int, float)):
			return bool(value)

		value_str = str(value).strip().lower()

		truthy = {"true", "yes", "1", "on", "y", "t", "enabled", "active"}
		falsy = {"false", "no", "0", "off", "n", "f", "disabled", "inactive"}

		if value_str in truthy:
			return True
		if value_str in falsy:
			return False

		return bool(value)

	DEFAULT_GENDER_MAPPING = {
		"male": "male",
		"female": "female",
		"other": "other",
		"unknown": "unknown",
		"m": "male",
		"f": "female",
		"o": "other",
		"u": "unknown",
		"Male": "male",
		"Female": "female",
		"Other": "other",
		"Unknown": "unknown",
		"MALE": "male",
		"FEMALE": "female",
		"boy": "male",
		"girl": "female",
		"man": "male",
		"woman": "female",
	}

	@staticmethod
	def transform_gender(value):
		"""Transform gender value to FHIR administrative-gender code."""
		if not value:
			return None

		value_str = str(value).strip()

		# Check mapping
		if value_str in FHIRValueTransformer.DEFAULT_GENDER_MAPPING:
			return FHIRValueTransformer.DEFAULT_GENDER_MAPPING[value_str]

		# Fallback: lowercase
		return value_str.lower()


# =========================================================
# Doctype: FHIR Resource Map
# =========================================================


class FHIRResourceMap(Document):
	def validate(self):
		compiled = self.compile_mapping()

		compiled_json = json.dumps(
			compiled,
			sort_keys=True,
			separators=(",", ":"),
			ensure_ascii=False,
			indent=1,
		)

		self.compiled_mapping = compiled_json
		self.compiled_hash = hashlib.sha256(compiled_json.encode("utf-8")).hexdigest()
		self.compiled_at = now_datetime()

	@frappe.whitelist()
	def compile_mapping(self):
		return FHIRMappingCompiler(resource_map=self).compile()

	def _load_compiled(self):
		if self.compiled_mapping:
			if isinstance(self.compiled_mapping, str):
				return json.loads(self.compiled_mapping)
			return self.compiled_mapping
		return self.compile_mapping()

	@frappe.whitelist()
	def load_structure_definition_elements(self):
		"""
		Return merged SD element rows (base + profiles most-restrictive-wins).
		Same merge used by compiler (repeating_containers).
		"""
		return FHIRStructureDefinitionLoader(resource_map=self).load_merged_elements()


# =========================================================
# Mapping Compiler
# =========================================================


class FHIRMappingCompiler:
	"""Compiles FHIR Resource Map into executable mapping structure."""

	def __init__(self, resource_map):
		self.resource_map = resource_map

	def compile(self):
		meta = self._compile_meta()
		sources = self._compile_sources()

		compiled = {
			"compiled_version": "fhir-map-compiled/v1",
			"meta": meta,
			"sources": sources,
		}

		element_state = self._compile_element_maps(compiled_sources=sources)
		compiled["elements"] = element_state["elements"]
		compiled["element_order"] = element_state["element_order"]
		compiled["compile_warnings"] = element_state["compile_warnings"]
		compiled["repeating_containers"] = self._compile_repeating_containers(elements=compiled["elements"])

		self._apply_default_indexes(compiled)
		self._validate(compiled)

		return compiled

	def _compile_meta(self):
		return {
			"primary_doctype": (self.resource_map.primary_doctype or "").strip(),
			"base_structure_definition": (self.resource_map.base_structure_definition or "").strip(),
			"resource_type": (self.resource_map.resource_type or "").strip(),
			"compiled_at": str(now_datetime()),
		}

	def _compile_sources(self):
		primary_doctype = (self.resource_map.primary_doctype or "").strip()
		if not primary_doctype:
			raise FHIRMappingCompilationError("primary_doctype is required.")

		compiled_sources = {
			"primary": {
				"source_key": "primary",
				"kind": "primary",
				"doctype": primary_doctype,
			}
		}

		for row in self.resource_map.get("sources") or []:
			source = self._compile_single_source(row, compiled_sources)
			if source:
				compiled_sources[source["source_key"]] = source

		return compiled_sources

	def _compile_single_source(self, row, existing_sources):
		source_key = (row.get("source_key") or "").strip()
		kind = (row.get("kind") or "").strip()
		doctype = (row.get("source_doctype") or row.get("doctype") or "").strip()

		if not source_key or not kind or not doctype:
			return None

		if source_key == "primary":
			raise FHIRMappingCompilationError("Do not add a source with key 'primary' in the sources table.")

		if kind not in {"direct_link", "reverse_link"}:
			raise FHIRMappingCompilationError(
				f"Source '{source_key}': unsupported kind '{kind}'. Supported: ['direct_link','reverse_link']"
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
		from_source_key = (row.get("from_source_key") or "").strip()
		if from_source_key:
			spec["from_source_key"] = from_source_key

		if row.get("limit"):
			spec["limit"] = int(row.get("limit"))

		lookup_fieldname = (row.get("lookup_fieldname") or "").strip()
		if lookup_fieldname:
			spec["lookup_fieldname"] = lookup_fieldname

		return spec

	def _compile_element_maps(self, compiled_sources):
		elements = {}
		element_order = []
		compile_warnings = []

		for row in self.resource_map.get("element_maps") or []:
			result = self._compile_single_element(row, compiled_sources, compile_warnings)
			if result:
				fhir_path, element = result
				if fhir_path in elements:
					raise FHIRMappingCompilationError(
						f"Duplicate element mapping for fhir_path '{fhir_path}'."
					)
				elements[fhir_path] = element
				element_order.append(fhir_path)

		element_order.sort()

		return {
			"elements": elements,
			"element_order": element_order,
			"compile_warnings": compile_warnings,
		}

	def _compile_single_element(self, row, compiled_sources, compile_warnings):
		fhir_path = (row.get("fhir_path") or "").strip()
		if not fhir_path:
			return None

		pointer = FHIRJsonHelpers.parse_value_pointer(row.get("value_pointer"))
		if not pointer:
			return None

		try:
			value_spec = self._build_value_spec(pointer, fhir_path, compiled_sources)
		except Exception as exc:
			compile_warnings.append(f"Skip '{fhir_path}': {exc}")
			return None

		base_json_path = self._to_json_path(fhir_path)

		element = {
			"fhir_path": fhir_path,
			"op": "set",
			"base_json_path": base_json_path,
			"path": "",
			"value_spec": value_spec,
			"datatype": (row.get("datatype") or "").strip(),
			"regex": row.get("regex"),
			"min": cint(row.get("min")),
			"max": str(row.get("max") or "").strip(),
			"valueset_url": (row.get("valueset_url") or "").strip(),
			"binding_strength": (row.get("binding_strength") or "").strip(),
			"is_choice_type": 1 if ("[x]" in fhir_path) else cint(row.get("is_choice_type")),
			"profile": (row.get("profile") or "").strip(),
			"target_profiles": FHIRJsonHelpers.normalize_string_list(row.get("target_profiles")),
		}

		return fhir_path, element

	def _build_value_spec(self, pointer, fhir_path, compiled_sources):
		kind = (pointer.get("kind") or "").strip()

		if kind == "fixed":
			if "value" not in pointer:
				raise FHIRMappingCompilationError(f"'{fhir_path}': fixed pointer missing 'value'")
			return {"kind": "fixed", "value": pointer.get("value")}

		if kind == "field":
			source_key = (pointer.get("source_key") or "").strip()
			if not source_key:
				raise FHIRMappingCompilationError(f"'{fhir_path}': field pointer missing 'source_key'")

			fieldname = (pointer.get("fieldname") or "").strip()
			if not fieldname:
				raise FHIRMappingCompilationError(f"'{fhir_path}': field pointer missing 'fieldname'")

			if source_key not in compiled_sources:
				raise FHIRMappingCompilationError(
					f"'{fhir_path}': unknown source_key '{source_key}'. Available: {sorted(compiled_sources.keys())}"
				)

			return {"kind": "field", "source_key": source_key, "fieldname": fieldname}

		raise FHIRMappingCompilationError(f"'{fhir_path}': unsupported pointer kind '{kind}'")

	def _to_json_path(self, fhir_path):
		fhir_path = (fhir_path or "").strip()
		resource_type = (self.resource_map.resource_type or "").strip()

		prefix = resource_type + "."
		if resource_type and fhir_path.startswith(prefix):
			return fhir_path[len(prefix) :].strip()

		return fhir_path

	def _compile_repeating_containers(self, elements):
		resource_type = (self.resource_map.resource_type or "").strip()
		if not resource_type:
			raise FHIRMappingCompilationError("resource_type is required to compute repeating_containers.")

		if not (self.resource_map.base_structure_definition or "").strip():
			return {}

		if not isinstance(elements, dict) or not elements:
			return {}

		mapped_paths = [str(p).strip() for p in elements.keys() if str(p).strip()]
		if not mapped_paths:
			return {}

		merged_rows = FHIRStructureDefinitionLoader(resource_map=self.resource_map).load_merged_elements()

		repeating_sd = []
		for row in merged_rows:
			fhir_path = (row.get("fhir_path") or "").strip()
			max_value = str(row.get("max") or "").strip()
			if fhir_path and max_value == "*":
				repeating_sd.append(fhir_path)

		if not repeating_sd:
			return {}

		repeating = {}
		for container_path in repeating_sd:
			prefix = container_path + "."
			for mapped_path in mapped_paths:
				if mapped_path == container_path or mapped_path.startswith(prefix):
					repeating[container_path] = 1
					break

		return repeating

	def _apply_default_indexes(self, compiled):
		meta = compiled.get("meta") or {}
		resource_type = (meta.get("resource_type") or "").strip()
		repeating_containers = compiled.get("repeating_containers") or {}
		elements = compiled.get("elements") or {}

		path_builder = FHIRRepeatingPathBuilder()

		for element in elements.values():
			if not isinstance(element, dict):
				continue

			base_json_path = (element.get("base_json_path") or "").strip()
			if not base_json_path:
				element["path"] = ""
				continue

			element["path"] = path_builder.build(
				resource_type=resource_type,
				base_json_path=base_json_path,
				repeating_containers=repeating_containers,
				default_index=0,
			)

	def _validate(self, compiled):
		meta = compiled.get("meta") or {}
		if not (meta.get("resource_type") or "").strip():
			raise FHIRMappingCompilationError("resource_type is required.")

		sources = compiled.get("sources") or {}
		if not isinstance(sources, dict) or not sources:
			raise FHIRMappingCompilationError("sources are missing from compiled output.")

		if "primary" not in sources:
			raise FHIRMappingCompilationError("primary source missing in compiled output.")

		if not frappe.in_test:
			elements = compiled.get("elements") or {}
			if not isinstance(elements, dict) or not elements:
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


# =========================================================
# Structure Definition Loader
# =========================================================


class FHIRStructureDefinitionLoader:
	"""Loads and merges structure definition elements."""

	def __init__(self, resource_map):
		self.resource_map = resource_map

	def load_merged_elements(self):
		if not (self.resource_map.base_structure_definition or "").strip():
			return []

		base_sd = frappe.get_cached_doc(
			"FHIR Structure Definition", self.resource_map.base_structure_definition
		)
		base_rows = base_sd.get("element_paths") or []
		resource_type = (getattr(base_sd, "fhir_sd", None) or "").strip()

		merger = FHIRStructureDefinitionMerger(resource_type=resource_type)
		merged = merger.build_base_map(base_rows)

		profile_rows = list(self.resource_map.get("profiles") or [])
		profile_rows.sort(
			key=lambda row: (0 if cint(getattr(row, "is_primary", 0)) else 1, cint(getattr(row, "idx", 0)))
		)

		for profile_row in profile_rows:
			sd_name = (getattr(profile_row, "fhir_structure_definition", None) or "").strip()
			if not sd_name:
				continue

			profile_url = (getattr(profile_row, "url", None) or "").strip() or (
				getattr(profile_row, "fhir_profile", None) or ""
			).strip()

			profile_sd = frappe.get_cached_doc("FHIR Structure Definition", sd_name)
			profile_elements = profile_sd.get("element_paths") or []

			merger.overlay_profile_rows(
				merged=merged,
				profile_url=profile_url,
				profile_elements=profile_elements,
			)

		return merger.to_sorted_rows(merged)


class FHIRStructureDefinitionMerger:
	"""Merges base and profile structure definitions with most-restrictive-wins logic."""

	STRENGTH_RANK = {"example": 1, "preferred": 2, "extensible": 3, "required": 4}

	def __init__(self, resource_type):
		self.resource_type = (resource_type or "").strip()

	def build_base_map(self, base_rows):
		merged = {}
		for element_row in base_rows or []:
			row = self._build_element_row(element_row)
			if not row:
				continue
			if self.resource_type and row.get("fhir_path") == self.resource_type:
				continue
			merged[row["fhir_path"]] = row
		return merged

	def overlay_profile_rows(self, merged, profile_url, profile_elements):
		for element_row in profile_elements or []:
			overlay = self._build_element_row(element_row)
			if not overlay:
				continue
			if self.resource_type and overlay.get("fhir_path") == self.resource_type:
				continue

			path = overlay.get("fhir_path")
			if not path:
				continue

			if path not in merged:
				overlay["profile"] = profile_url
				merged[path] = overlay
				continue

			if self._apply_most_restrictive(merged[path], overlay):
				merged[path]["profile"] = profile_url

	def to_sorted_rows(self, merged):
		return [merged[key] for key in sorted((merged or {}).keys())]

	def _build_element_row(self, element_row):
		fhir_path = (element_row.get("path") or "").strip()
		if not fhir_path:
			return None

		min_cardinality = cint(element_row.get("min"))
		return {
			"fhir_path": fhir_path,
			"datatype": (element_row.get("datatype") or "").strip(),
			"min": min_cardinality,
			"max": str(element_row.get("max") or "").strip(),
			"short": (element_row.get("short") or "").strip(),
			"definition": (element_row.get("definition") or "").strip(),
			"valueset_url": (element_row.get("valueset_url") or "").strip(),
			"binding_strength": (element_row.get("binding_strength") or "").strip(),
			"target_profiles": element_row.get("target_profiles"),
			"is_required": 1 if min_cardinality >= 1 else 0,
			"is_choice_type": 1 if ("[x]" in fhir_path) else 0,
			"profile": "",
		}

	def _apply_most_restrictive(self, base, overlay):
		changed = False
		changed |= self._apply_min(base, overlay)
		changed |= self._apply_max(base, overlay)
		changed |= self._apply_binding_strength(base, overlay)
		changed |= self._apply_valueset(base, overlay)
		changed |= self._apply_datatype(base, overlay)
		changed |= self._apply_target_profiles(base, overlay)
		self._fill_metadata(base, overlay)
		return bool(changed)

	def _apply_min(self, base, overlay):
		if cint(overlay.get("min")) > cint(base.get("min")):
			base["min"] = cint(overlay.get("min"))
			return True
		return False

	def _apply_max(self, base, overlay):
		base_max = (base.get("max") or "").strip()
		overlay_max = (overlay.get("max") or "").strip()
		if not overlay_max:
			return False

		if base_max == "*" and overlay_max != "*":
			base["max"] = overlay_max
			return True

		if (
			overlay_max != "*"
			and base_max != "*"
			and overlay_max.isdigit()
			and base_max.isdigit()
			and int(overlay_max) < int(base_max)
		):
			base["max"] = overlay_max
			return True

		return False

	def _apply_binding_strength(self, base, overlay):
		overlay_rank = self.STRENGTH_RANK.get((overlay.get("binding_strength") or "").lower(), 0)
		base_rank = self.STRENGTH_RANK.get((base.get("binding_strength") or "").lower(), 0)

		if overlay_rank > base_rank and overlay.get("binding_strength"):
			base["binding_strength"] = overlay.get("binding_strength")
			return True
		return False

	def _apply_valueset(self, base, overlay):
		if overlay.get("valueset_url") and overlay.get("valueset_url") != base.get("valueset_url"):
			base["valueset_url"] = overlay.get("valueset_url")
			return True
		return False

	def _apply_datatype(self, base, overlay):
		if overlay.get("datatype") and overlay.get("datatype") != base.get("datatype"):
			base["datatype"] = overlay.get("datatype")
			return True
		return False

	def _apply_target_profiles(self, base, overlay):
		if overlay.get("target_profiles") and overlay.get("target_profiles") != base.get("target_profiles"):
			base["target_profiles"] = overlay.get("target_profiles")
			return True
		return False

	def _fill_metadata(self, base, overlay):
		if overlay.get("short") and not base.get("short"):
			base["short"] = overlay.get("short")
		if overlay.get("definition") and not base.get("definition"):
			base["definition"] = overlay.get("definition")


# =========================================================
# Value Resolver
# =========================================================


class FHIRValueResolver:
	"""Resolves values from Frappe documents based on compiled mapping."""

	def __init__(self, compiled_map, docname):
		self.compiled_map = compiled_map
		self.docname = docname
		self.resolved_sources = {}
		self.resolved_values = {}

	def resolve(self):
		self._resolve_sources()
		self._resolve_element_values()
		return self.resolved_values

	def _resolve_sources(self):
		sources = self.compiled_map.get("sources", {})

		# First pass: resolve primary
		for source_key, source_config in sources.items():
			if source_config.get("kind") == "primary":
				self._resolve_primary_source(source_key, source_config)

		# Second pass: resolve linked sources
		for source_key, source_config in sources.items():
			kind = source_config.get("kind")
			if kind == "direct_link":
				self._resolve_direct_link_source(source_key, source_config)
			elif kind == "reverse_link":
				self._resolve_reverse_link_source(source_key, source_config)

	def _resolve_primary_source(self, source_key, source_config):
		doctype = source_config.get("doctype")
		self.resolved_sources[source_key] = frappe.get_doc(doctype, self.docname).as_dict()

	def _resolve_direct_link_source(self, source_key, source_config):
		primary_doc = self.resolved_sources.get("primary")
		if not primary_doc:
			self.resolved_sources[source_key] = None
			return

		link_fieldname = source_config.get("link_fieldname")
		linked_name = primary_doc.get(link_fieldname)

		if linked_name:
			doctype = source_config.get("doctype")
			self.resolved_sources[source_key] = frappe.get_doc(doctype, linked_name).as_dict()
		else:
			self.resolved_sources[source_key] = None

	def _resolve_reverse_link_source(self, source_key, source_config):
		primary_doc = self.resolved_sources.get("primary")
		if not primary_doc:
			self.resolved_sources[source_key] = []
			return

		doctype = source_config.get("doctype")
		link_fieldname = source_config.get("link_fieldname")
		config_filters = source_config.get("filters") or {}
		order_by = source_config.get("order_by", "creation desc")

		filters = {link_fieldname: primary_doc.get("name")}
		filters.update(config_filters)

		results = frappe.get_all(doctype, filters=filters, order_by=order_by, pluck="name")

		docs = []
		for name in results:
			doc = frappe.get_doc(doctype, name).as_dict()
			docs.append(doc)

		self.resolved_sources[source_key] = docs

	def _resolve_element_values(self):
		elements = self.compiled_map.get("elements", {})
		element_order = self.compiled_map.get("element_order", list(elements.keys()))

		for element_path in element_order:
			element = elements.get(element_path)
			if not element:
				continue

			value_spec = element.get("value_spec", {})
			kind = value_spec.get("kind")

			if kind == "fixed":
				self.resolved_values[element_path] = value_spec.get("value")
			elif kind == "field":
				self._resolve_field_value(element_path, value_spec)

	def _resolve_field_value(self, element_path, value_spec):
		source_key = value_spec.get("source_key")
		fieldname = value_spec.get("fieldname")
		source_data = self.resolved_sources.get(source_key)

		if source_data is None:
			self.resolved_values[element_path] = None
		elif isinstance(source_data, list):
			self.resolved_values[element_path] = source_data
		else:
			self.resolved_values[element_path] = FHIRUtils.get_dotted_value(source_data, fieldname)


# =========================================================
# Resource Generator
# =========================================================


class FHIRResourceGenerator:
	"""Generates FHIR resource JSON from compiled mapping and resolved values."""

	PRIMITIVE_TYPES = [
		"string",
		"boolean",
		"date",
		"dateTime",
		"time",
		"instant",
		"integer",
		"decimal",
		"uri",
		"url",
		"canonical",
		"base64Binary",
		"code",
		"id",
		"markdown",
		"oid",
		"positiveInt",
		"unsignedInt",
		"uuid",
	]

	def __init__(self, compiled_map, resolved_values):
		self.compiled_map = compiled_map
		self.resolved_values = resolved_values
		self.resource = {}

	def generate(self):
		resource_type = self.compiled_map.get("meta", {}).get("resource_type")
		self.resource = {"resourceType": resource_type}

		element_order = self.compiled_map.get("element_order", [])
		elements = self.compiled_map.get("elements", {})

		for fhir_path in element_order:
			element = elements.get(fhir_path)
			if not element:
				continue

			resolved_value = self.resolved_values.get(fhir_path)
			if FHIRUtils.is_empty(resolved_value):
				continue

			path = element.get("path")
			datatype = element.get("datatype")
			max_cardinality = element.get("max", "1")
			value_spec = element.get("value_spec", {})

			transformed = self._transform_value(resolved_value, datatype, element, value_spec)
			if FHIRUtils.is_empty(transformed):
				continue

			self._set_nested_value(path, transformed, max_cardinality)

		return self.resource

	def _transform_value(self, value, datatype, element, value_spec):
		# Fixed values should not be transformed into complex types
		if value_spec.get("kind") == "fixed":
			if datatype == "code":
				return self._transform_code(value, element)
			if datatype == "date":
				return FHIRValueTransformer.transform_date(value)
			if datatype == "boolean":
				return FHIRValueTransformer.transform_boolean(value)
			return value

		if datatype == "Reference":
			return self._build_reference(value, element)
		elif datatype == "Narrative":
			return self._build_narrative(value)
		elif datatype == "ContactPoint":
			return self._build_contact_point(value, element)
		elif datatype == "code":
			return self._transform_code(value, element)
		elif datatype == "date":
			return FHIRValueTransformer.transform_date(value)
		elif datatype == "boolean":
			return FHIRValueTransformer.transform_boolean(value)
		elif datatype in self.PRIMITIVE_TYPES:
			return value
		else:
			return value

	# ----- Reference -----

	def _build_reference(self, value, element):
		if isinstance(value, list):
			references = []
			seen = set()
			for item in value:
				ref, ref_key = self._build_single_reference(item, element)
				if ref and ref_key:
					if ref_key not in seen:
						seen.add(ref_key)
						references.append(ref)
				elif ref:
					references.append(ref)
			return references
		else:
			ref, _ = self._build_single_reference(value, element)
			return ref

	def _build_single_reference(self, data, element):
		if isinstance(data, dict):
			target_profiles = element.get("target_profiles", [])
			value_spec = element.get("value_spec", {})
			fieldname = value_spec.get("fieldname", "")

			resource_type = None
			reference_id = None

			# Find matching resource type by checking which field exists in data
			for profile in target_profiles:
				rt = FHIRUtils.extract_resource_type(profile)
				if rt:
					field_name = rt.lower()
					if field_name in data and data.get(field_name):
						resource_type = rt
						reference_id = data.get(field_name)
						break

			# Fallback to first profile and name field
			if not resource_type and target_profiles:
				resource_type = FHIRUtils.extract_resource_type(target_profiles[0])
				reference_id = data.get("name")

			display_value = FHIRUtils.get_dotted_value(data, fieldname)

			ref_obj = {}
			if resource_type and reference_id:
				fhir_id = FHIRUtils.to_fhir_id(reference_id)
				ref_obj["reference"] = f"{resource_type}/{fhir_id}"
			if display_value:
				ref_obj["display"] = display_value

			return (ref_obj if ref_obj else None, reference_id)
		else:
			return ({"display": str(data)} if data else None, None)

	# ----- Narrative -----

	def _build_narrative(self, value):
		if isinstance(value, dict):
			return value
		text = str(value) if value else ""
		return {
			"status": "generated",
			"div": f'<div xmlns="http://www.w3.org/1999/xhtml">{text}</div>',
		}

	# ----- ContactPoint -----

	def _build_contact_point(self, value, element):
		if isinstance(value, list):
			contact_points = []
			for item in value:
				cp = self._build_single_contact_point(item, element)
				if cp:
					contact_points.append(cp)
			return contact_points
		else:
			return self._build_single_contact_point(value, element)

	def _build_single_contact_point(self, data, element):
		if isinstance(data, dict):
			cp = {}

			# Check for explicit system
			if data.get("system"):
				cp["system"] = data.get("system")
				cp["value"] = data.get("value")
			# Infer system from available fields
			elif data.get("email") or data.get("email_address"):
				cp["system"] = "email"
				cp["value"] = data.get("email") or data.get("email_address")
			elif (
				data.get("phone")
				or data.get("mobile")
				or data.get("phone_number")
				or data.get("mobile_number")
			):
				cp["system"] = "phone"
				cp["value"] = (
					data.get("phone")
					or data.get("mobile")
					or data.get("phone_number")
					or data.get("mobile_number")
				)
			elif data.get("fax"):
				cp["system"] = "fax"
				cp["value"] = data.get("fax")
			elif data.get("value"):
				# Try to infer from value format
				value = str(data.get("value", "")).strip()
				if "@" in value:
					cp["system"] = "email"
				elif value.replace("+", "").replace("-", "").replace(" ", "").isdigit():
					cp["system"] = "phone"
				cp["value"] = value

			if data.get("use"):
				cp["use"] = data.get("use")

			return cp if cp.get("value") else None
		else:
			# Simple string value - try to infer type
			value = str(data).strip() if data else ""
			if not value:
				return None

			cp = {"value": value}

			if "@" in value:
				cp["system"] = "email"
			elif value.replace("+", "").replace("-", "").replace(" ", "").isdigit():
				cp["system"] = "phone"

			return cp

	# ----- Code -----

	def _transform_code(self, value, element):
		if value is None:
			return None

		binding_strength = element.get("binding_strength")
		valueset_url = element.get("valueset_url", "")

		# Check if this is gender valueset
		if "administrative-gender" in valueset_url:
			return FHIRValueTransformer.transform_gender(value)

		# Default: lowercase for required bindings
		if binding_strength == "required" and isinstance(value, str):
			return value.lower()

		return value

	# ----- Path Setting -----

	def _set_nested_value(self, path, value, max_cardinality):
		# Remove array index from path if value is a list (spread across array)
		base_path = re.sub(r"\[\d+\]$", "", path)
		segments = FHIRUtils.parse_path(base_path)

		if not segments:
			return

		# If value is a list and max cardinality is *, set as array at base path
		if isinstance(value, list) and max_cardinality == "*":
			self._set_value_at_path(segments, value)
		else:
			segments = FHIRUtils.parse_path(path)
			self._set_value_at_path(segments, value)

	def _set_value_at_path(self, segments, value):
		current = self.resource

		for i, segment in enumerate(segments[:-1]):
			next_segment = segments[i + 1]

			if isinstance(segment, str):
				if segment not in current:
					if isinstance(next_segment, int):
						current[segment] = []
					else:
						current[segment] = {}
				current = current[segment]

			elif isinstance(segment, int):
				while len(current) <= segment:
					current.append({})
				current = current[segment]

		last_segment = segments[-1]

		if not current.get("last_segment"):
			if isinstance(last_segment, str):
				current[last_segment] = value
			elif isinstance(last_segment, int):
				while len(current) <= last_segment:
					current.append({})
				current[last_segment] = value


# =========================================================
# Mapping Validator
# =========================================================


class FHIRMappingValidator:
	"""Validates compiled FHIR mapping against structure definition."""

	REFERENCE_TYPES = ["Reference"]
	CONTACT_POINT_TYPES = ["ContactPoint"]
	NARRATIVE_TYPES = ["Narrative"]
	CODE_TYPES = ["code", "coding", "CodeableConcept"]

	# Complex types that are typically backbone elements
	BACKBONE_DATATYPES = ["BackboneElement", "Element", ""]

	def __init__(self, compiled_map, sd_elements):
		self.compiled_map = compiled_map
		self.sd_elements = sd_elements
		self.errors = []
		self.warnings = []
		self._sd_elements_map = {}
		self._backbone_elements = {}
		self._build_sd_index()

	def _build_sd_index(self):
		"""Build indexes for quick lookups."""
		for element in self.sd_elements:
			fhir_path = element.get("fhir_path", "")
			if fhir_path:
				self._sd_elements_map[fhir_path] = element

		# Identify backbone elements (elements that have child elements with required fields)
		self._identify_backbone_elements()

	def _identify_backbone_elements(self):
		"""
		Identify backbone elements by finding parent paths that have child elements.
		A backbone element is one that:
		1. Has child elements (other elements start with its path + ".")
		2. Has max cardinality of "*" or ">1" (repeating)
		3. Is not a primitive type
		"""
		all_paths = set(self._sd_elements_map.keys())

		for fhir_path, element in self._sd_elements_map.items():
			datatype = element.get("datatype", "")

			# Skip primitive types
			if datatype and datatype[0].islower():
				continue

			# Find children of this element
			prefix = fhir_path + "."
			children = [p for p in all_paths if p.startswith(prefix) and "." not in p[len(prefix) :]]

			if not children:
				continue

			# Find required children (min >= 1)
			required_children = []
			for child_path in children:
				child_element = self._sd_elements_map.get(child_path, {})
				if child_element.get("min", 0) >= 1:
					# Extract just the child field name
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

		self._validate_required_elements()
		self._validate_mapped_elements()
		self._validate_sources()
		self._validate_backbone_elements()

		return {
			"is_valid": len(self.errors) == 0,
			"errors": self.errors,
			"warnings": self.warnings,
			"error_count": len(self.errors),
			"warning_count": len(self.warnings),
		}

	def _validate_required_elements(self):
		"""Check if all required (min >= 1) elements are mapped."""
		elements = self.compiled_map.get("elements", {})

		for sd_element in self.sd_elements:
			fhir_path = sd_element.get("fhir_path", "")
			min_card = sd_element.get("min", 0)

			if min_card < 1:
				continue

			# Skip if this is a child of a backbone element (validated separately)
			if self._is_backbone_child(fhir_path):
				continue

			if fhir_path not in elements:
				self.errors.append(
					{
						"type": "required_missing",
						"fhir_path": fhir_path,
						"message": f"Required element '{fhir_path}' (min={min_card}) is not mapped",
					}
				)
				continue

			element = elements[fhir_path]
			value_spec = element.get("value_spec", {})

			if not value_spec or not value_spec.get("kind"):
				self.errors.append(
					{
						"type": "required_no_mapping",
						"fhir_path": fhir_path,
						"message": f"Required element '{fhir_path}' has no valid mapping",
					}
				)

	def _is_backbone_child(self, fhir_path):
		"""Check if this path is a direct child of a backbone element."""
		for backbone_path in self._backbone_elements.keys():
			prefix = backbone_path + "."
			if fhir_path.startswith(prefix):
				# Check if it's a direct child (no more dots after prefix)
				remaining = fhir_path[len(prefix) :]
				if "." not in remaining:
					return True
		return False

	def _validate_mapped_elements(self):
		"""Validate each mapped element based on its datatype."""
		elements = self.compiled_map.get("elements", {})

		for fhir_path, element in elements.items():
			datatype = element.get("datatype", "")
			value_spec = element.get("value_spec", {})

			if not value_spec or not value_spec.get("kind"):
				continue

			if datatype in self.REFERENCE_TYPES:
				self._validate_reference_element(fhir_path, element, value_spec)
			elif datatype in self.CONTACT_POINT_TYPES:
				self._validate_contact_point_element(fhir_path, element, value_spec)
			elif datatype in self.NARRATIVE_TYPES:
				self._validate_narrative_element(fhir_path, element, value_spec)
			elif datatype in self.CODE_TYPES:
				self._validate_code_element(fhir_path, element, value_spec)

	def _validate_reference_element(self, fhir_path, element, value_spec):
		"""Validate Reference datatype mappings."""
		kind = value_spec.get("kind")
		target_profiles = element.get("target_profiles", [])

		if kind == "fixed":
			value = value_spec.get("value")
			if isinstance(value, str):
				self.errors.append(
					{
						"type": "reference_fixed_string",
						"fhir_path": fhir_path,
						"message": f"Reference '{fhir_path}' cannot be a fixed string. Must be a Reference object with 'reference' and/or 'display' fields.",
					}
				)
			elif isinstance(value, dict):
				if not value.get("reference") and not value.get("display"):
					self.warnings.append(
						{
							"type": "reference_empty_object",
							"fhir_path": fhir_path,
							"message": f"Reference '{fhir_path}' fixed value should have 'reference' or 'display' field.",
						}
					)

		if kind == "field":
			if not target_profiles:
				self.warnings.append(
					{
						"type": "reference_no_target_profiles",
						"fhir_path": fhir_path,
						"message": f"Reference '{fhir_path}' has no target_profiles defined. Resource type may not be determined correctly.",
					}
				)

	def _validate_contact_point_element(self, fhir_path, element, value_spec):
		"""Validate ContactPoint datatype mappings."""
		elements = self.compiled_map.get("elements", {})

		# Check if this is the main ContactPoint element (not a sub-element)
		if not fhir_path.endswith(".system") and not fhir_path.endswith(".value"):
			system_path = f"{fhir_path}.system"
			value_path = f"{fhir_path}.value"

			has_system = system_path in elements and elements[system_path].get("value_spec", {}).get("kind")
			has_value = value_path in elements and elements[value_path].get("value_spec", {}).get("kind")

			if not has_system and has_value:
				self.warnings.append(
					{
						"type": "contactpoint_missing_system",
						"fhir_path": fhir_path,
						"message": f"ContactPoint '{fhir_path}' has value mapped but no system. FHIR requires system when value is present.",
					}
				)

	def _validate_narrative_element(self, fhir_path, element, value_spec):
		"""Validate Narrative datatype mappings."""
		kind = value_spec.get("kind")

		if kind == "field":
			self.warnings.append(
				{
					"type": "narrative_auto_generated",
					"fhir_path": fhir_path,
					"message": f"Narrative '{fhir_path}' will be auto-generated. Ensure the mapped field contains appropriate text content.",
				}
			)

	def _validate_code_element(self, fhir_path, element, value_spec):
		"""Validate code/coding datatype mappings."""
		binding_strength = element.get("binding_strength", "")
		valueset_url = element.get("valueset_url", "")

		if binding_strength == "required" and not valueset_url:
			self.warnings.append(
				{
					"type": "code_no_valueset",
					"fhir_path": fhir_path,
					"message": f"Code element '{fhir_path}' has required binding but no valueset_url. Values may not be validated.",
				}
			)

		if binding_strength == "required":
			kind = value_spec.get("kind")
			if kind == "field":
				self.warnings.append(
					{
						"type": "code_runtime_validation",
						"fhir_path": fhir_path,
						"message": f"Code element '{fhir_path}' with required binding needs runtime validation against valueset.",
					}
				)

	def _validate_sources(self):
		"""Validate that sources reference valid doctypes and fields."""
		sources = self.compiled_map.get("sources", {})

		for source_key, source_config in sources.items():
			doctype = source_config.get("doctype", "")

			if not doctype:
				self.errors.append(
					{
						"type": "source_no_doctype",
						"source_key": source_key,
						"message": f"Source '{source_key}' has no doctype defined.",
					}
				)
				continue

			# Check if doctype exists
			if not frappe.db.exists("DocType", doctype):
				self.errors.append(
					{
						"type": "source_invalid_doctype",
						"source_key": source_key,
						"message": f"Source '{source_key}' references non-existent doctype '{doctype}'.",
					}
				)
				continue

			# Validate link fields for direct_link and reverse_link
			kind = source_config.get("kind", "")
			if kind in ["direct_link", "reverse_link"]:
				link_fieldname = source_config.get("link_fieldname", "")

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
		"""Check if a field exists in the doctype."""
		# For reverse_link, the field is on the linked doctype
		# For direct_link, the field is on the primary doctype
		if kind == "direct_link":
			primary_doctype = self.compiled_map.get("meta", {}).get("primary_doctype", "")
			check_doctype = primary_doctype
		else:
			check_doctype = doctype

		if not check_doctype:
			return

		meta = frappe.get_meta(check_doctype)
		field_exists = any(df.fieldname == fieldname for df in meta.fields)

		# Also check for name field
		if fieldname == "name":
			field_exists = True

		if not field_exists:
			self.warnings.append(
				{
					"type": "source_field_not_found",
					"source_key": source_key,
					"message": f"Source '{source_key}': field '{fieldname}' not found in '{check_doctype}'. It may be a custom field or child table field.",
				}
			)

	def _validate_backbone_elements(self):
		"""Validate backbone elements have all required sub-elements."""
		elements = self.compiled_map.get("elements", {})

		for backbone_path, backbone_info in self._backbone_elements.items():
			# Check if any element under this backbone is mapped
			backbone_mapped = any(
				fp == backbone_path or fp.startswith(f"{backbone_path}.") for fp in elements.keys()
			)

			if not backbone_mapped:
				continue

			# Check required children
			required_children = backbone_info.get("required_children", [])

			for child_name in required_children:
				child_path = f"{backbone_path}.{child_name}"

				if child_path not in elements:
					self.errors.append(
						{
							"type": "backbone_missing_required",
							"fhir_path": child_path,
							"message": f"Backbone element '{backbone_path}' is mapped but required child '{child_name}' is missing.",
						}
					)
				else:
					# Check if the child has a valid mapping
					child_element = elements.get(child_path, {})
					child_value_spec = child_element.get("value_spec", {})

					if not child_value_spec or not child_value_spec.get("kind"):
						self.errors.append(
							{
								"type": "backbone_child_no_mapping",
								"fhir_path": child_path,
								"message": f"Required child '{child_name}' of backbone '{backbone_path}' has no valid mapping.",
							}
						)


# =========================================================
# API
# =========================================================


@frappe.whitelist()
def validate_fhir_mapping(fhir_resource_map):
	"""Validate a FHIR Resource Map's compiled mapping against its structure definition."""
	fhir_resource_map = (fhir_resource_map or "").strip()
	if not fhir_resource_map:
		frappe.throw("fhir_resource_map is required")

	resource_map = frappe.get_doc("FHIR Resource Map", fhir_resource_map)

	# Get compiled mapping
	compiled_map = resource_map.compiled_mapping
	if isinstance(compiled_map, str):
		compiled_map = frappe.parse_json(compiled_map)

	if not compiled_map:
		return {
			"is_valid": False,
			"errors": [
				{"type": "no_compiled_map", "message": "No compiled mapping found. Save the document first."}
			],
			"warnings": [],
			"error_count": 1,
			"warning_count": 0,
		}

	# Get structure definition elements
	sd_elements = resource_map.load_structure_definition_elements()

	# Validate
	validator = FHIRMappingValidator(compiled_map, sd_elements)
	return validator.validate()


@frappe.whitelist()
def load_structure_definition_elements(fhir_resource_map):
	fhir_resource_map = (fhir_resource_map or "").strip()
	if not fhir_resource_map:
		frappe.throw("fhir_resource_map is required")

	doc = frappe.get_doc("FHIR Resource Map", fhir_resource_map)
	return doc.load_structure_definition_elements()


@frappe.whitelist()
def resolve_fhir_values(fhir_resource_map, primary_name):
	resource_map = frappe.get_doc("FHIR Resource Map", fhir_resource_map)
	compiled_map = resource_map.compiled_mapping
	if isinstance(compiled_map, str):
		compiled_map = frappe.parse_json(compiled_map)

	resolver = FHIRValueResolver(compiled_map, primary_name)
	return resolver.resolve()


@frappe.whitelist()
def build_fhir_resource(fhir_resource_map, primary_name):
	resource_map = frappe.get_doc("FHIR Resource Map", fhir_resource_map)
	compiled_map = resource_map.compiled_mapping
	if isinstance(compiled_map, str):
		compiled_map = frappe.parse_json(compiled_map)

	resolver = FHIRValueResolver(compiled_map, primary_name)
	resolved_values = resolver.resolve()

	generator = FHIRResourceGenerator(compiled_map, resolved_values)
	return generator.generate()
