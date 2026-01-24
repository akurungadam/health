"""
FHIR Resource Generator

Takes a compiled mapping and resolved resource, produces a valid FHIR resource.
Performs runtime lookups against FHIR Datatype and FHIR Structure Definition DocTypes.

No type annotations per user preference.
"""

import json
import re
from copy import deepcopy

import frappe


class DefinitionLoader:
	"""
	Loads datatype and backbone definitions from Frappe DocTypes.
	Caches results to avoid repeated DB hits.
	"""

	def __init__(self):
		self.datatype_cache = {}
		self.backbone_cache = {}

	def get_datatype(self, name):
		"""
		Load definition from FHIR Datatype DocType.
		Returns dict with is_primitive, regex, elements, or None if not found.
		"""
		if not name:
			return None

		name = name.strip()
		if name in self.datatype_cache:
			return self.datatype_cache[name]

		if not frappe.db.exists("FHIR Datatype", name):
			self.datatype_cache[name] = None
			return None

		doc = frappe.get_doc("FHIR Datatype", name)
		defn = {
			"name": doc.datatype,
			"is_primitive": doc.is_primitive,
			"regex": doc.regex or None,
			"elements": {},
		}

		for el in doc.elements or []:
			defn["elements"][el.element_name] = {
				"datatype": el.datatype or "",
				"min": el.min or 0,
				"max": el.max or "*",
				"is_choice_type": el.is_choice_type or 0,
				"regex": el.regex or None,
				"valueset_url": el.valueset_url or "",
				"binding_strength": el.binding_strength or "",
				"target_profiles": self._parse_json_safe(el.target_profiles),
			}

		self.datatype_cache[name] = defn
		return defn

	def get_backbone(self, sd_name, backbone_path):
		"""
		Load BackboneElement structure from FHIR Structure Definition.

		Args:
			sd_name: Name of the FHIR Structure Definition doc (e.g., "Patient-4.0.1")
			backbone_path: Full FHIR path (e.g., "Patient.contact")

		Returns dict with elements for direct children of the backbone.
		"""
		if not sd_name or not backbone_path:
			return None

		cache_key = f"{sd_name}:{backbone_path}"
		if cache_key in self.backbone_cache:
			return self.backbone_cache[cache_key]

		if not frappe.db.exists("FHIR Structure Definition", sd_name):
			self.backbone_cache[cache_key] = None
			return None

		doc = frappe.get_doc("FHIR Structure Definition", sd_name)

		elements = {}
		prefix = backbone_path + "."

		for el in doc.element_paths or []:
			path = el.path or ""
			if path.startswith(prefix):
				relative = path[len(prefix) :]
				# Only direct children (no dots in relative path)
				if "." not in relative and relative:
					elements[relative] = {
						"datatype": el.datatype or "",
						"min": el.min or 0,
						"max": el.max or "*",
						"is_choice_type": el.is_choice_type or 0,
						"regex": el.regex or None,
						"valueset_url": el.valueset_url or "",
						"binding_strength": el.binding_strength or "",
						"target_profiles": self._parse_json_safe(el.target_profiles),
					}

		defn = {
			"name": backbone_path,
			"is_primitive": False,
			"is_backbone": True,
			"elements": elements,
		}

		self.backbone_cache[cache_key] = defn
		return defn

	def is_primitive(self, name):
		"""Check if a datatype is primitive."""
		defn = self.get_datatype(name)
		return defn.get("is_primitive", False) if defn else False

	def _parse_json_safe(self, value):
		"""Safely parse JSON string, return empty list on failure."""
		if not value:
			return []
		if isinstance(value, list):
			return value
		try:
			parsed = json.loads(value)
			return parsed if isinstance(parsed, list) else []
		except Exception:
			return []


class FHIRResourceGenerator:
	"""
	Generates valid FHIR resources from compiled mappings and resolved values.
	"""

	# Primitive wrapping rules for complex types
	WRAP_RULES = {
		"Reference": lambda v: {"reference": str(v)} if "/" in str(v) else {"display": str(v)},
		"CodeableConcept": lambda v: {"text": str(v)},
		"Coding": lambda v: {"code": str(v)},
		"Identifier": lambda v: {"value": str(v)},
		"HumanName": lambda v: {"text": str(v)},
		"Address": lambda v: {"text": str(v)},
		"ContactPoint": lambda v: {"value": str(v)},
		"Quantity": lambda v: {"value": v} if _is_numeric(v) else {"unit": str(v)},
		"Period": lambda v: {"start": str(v)},
		"Range": lambda v: {"low": {"value": v}} if _is_numeric(v) else {},
		"Ratio": lambda v: {},
		"Attachment": lambda v: {"url": str(v)} if str(v).startswith("http") else {"data": str(v)},
		"Annotation": lambda v: {"text": str(v)},
		"Signature": lambda v: {"data": str(v)},
		"Age": lambda v: {"value": v} if _is_numeric(v) else {},
		"Distance": lambda v: {"value": v} if _is_numeric(v) else {},
		"Duration": lambda v: {"value": v} if _is_numeric(v) else {},
		"Count": lambda v: {"value": int(v)} if _is_numeric(v) else {},
		"Money": lambda v: {"value": float(v)} if _is_numeric(v) else {},
		"Timing": lambda v: {},
		"SampledData": lambda v: {"data": str(v)},
	}

	def __init__(self, compiled_map, resolved_resource):
		"""
		Initialize generator.

		Args:
			compiled_map: The compiled mapping JSON (dict)
			resolved_resource: Output from FHIRValueResolver (dict)
		"""
		self.compiled = compiled_map or {}
		self.resolved = deepcopy(resolved_resource) if resolved_resource else {}
		self.loader = DefinitionLoader()
		self.errors = []
		self.warnings = []

		# Extract metadata
		self.meta = self.compiled.get("meta", {})
		self.resource_type = self.meta.get("resource_type", "Unknown")
		self.base_sd = self.meta.get("base_structure_definition", "")
		self.elements = self.compiled.get("elements", {})
		self.element_order = self.compiled.get("element_order", [])

	def generate(self, strict=False):
		"""
		Generate a valid FHIR resource.

		Args:
			strict: If True, raise exception on errors. If False, return errors in result.

		Returns:
			dict with keys: resource, valid, errors, warnings
		"""
		resource = self.resolved

		# 1. Ensure resourceType
		resource["resourceType"] = self.resource_type

		# 2. Process each mapped element
		for fhir_path in self.element_order:
			element_def = self.elements.get(fhir_path)
			if not element_def:
				continue

			json_path = (element_def.get("path") or "").strip()
			if not json_path:
				continue

			datatype = (element_def.get("datatype") or "").strip()
			value = self._get_at_path(resource, json_path)

			if value is None:
				self._handle_missing(element_def, fhir_path, json_path)
				continue

			processed = self._process_value(value, datatype, element_def, fhir_path, json_path)
			if processed is not None:
				self._set_at_path(resource, json_path, processed)

		# 3. Add meta
		self._add_meta(resource)

		# 4. Clean empty containers
		self._clean_empty(resource)

		# 5. Reorder keys for readability
		resource = self._reorder_keys(resource)

		# 6. Handle strict mode
		if strict and self.errors:
			error_msg = "\n".join([e.get("message", str(e)) for e in self.errors])
			frappe.throw(f"FHIR Resource Generation Failed:\n{error_msg}")

		return {
			"resource": resource,
			"valid": len(self.errors) == 0,
			"errors": self.errors,
			"warnings": self.warnings,
		}

	# =========================================================================
	# Value Processing
	# =========================================================================

	def _process_value(self, value, datatype, element_def, fhir_path, json_path):
		"""
		Process a value based on its datatype.
		Dispatches to primitive or complex processing.
		"""
		if value is None:
			return None

		# Handle arrays
		if isinstance(value, list):
			return [
				self._process_value(item, datatype, element_def, fhir_path, f"{json_path}[{i}]")
				for i, item in enumerate(value)
				if item is not None
			]

		# Get primary datatype (first if comma-separated)
		primary_datatype = datatype.split(",")[0].strip() if datatype else ""

		if not primary_datatype:
			return value

		# 1. Try loading from FHIR Datatype
		datatype_def = self.loader.get_datatype(primary_datatype)

		if datatype_def:
			if datatype_def.get("is_primitive"):
				return self._process_primitive(value, datatype_def, element_def, json_path)
			else:
				return self._process_complex(value, datatype_def, element_def, json_path)

		# 2. BackboneElement — load from Structure Definition
		if primary_datatype == "BackboneElement":
			backbone_def = self.loader.get_backbone(self.base_sd, fhir_path)
			if backbone_def:
				return self._process_complex(value, backbone_def, element_def, json_path)
			return value if isinstance(value, dict) else {}

		# 3. Element (abstract base) — skip validation
		if primary_datatype in ("Element", "Resource", "DomainResource"):
			return value

		# 4. Unknown datatype
		self.warnings.append(
			{
				"severity": "warning",
				"type": "unknown-datatype",
				"path": json_path,
				"datatype": primary_datatype,
				"message": f"Unknown datatype '{primary_datatype}' at {json_path}, value passed through",
			}
		)
		return value

	def _process_primitive(self, value, datatype_def, element_def, json_path):
		"""Process a primitive value: coerce and validate."""
		name = datatype_def.get("name", "")

		# Coerce to correct type
		coerced = self._coerce_primitive(value, name)

		# Validate regex
		regex = element_def.get("regex") or datatype_def.get("regex")
		if regex and coerced is not None:
			try:
				if not re.match(regex, str(coerced)):
					self.errors.append(
						{
							"severity": "error",
							"type": "pattern",
							"path": json_path,
							"value": coerced,
							"regex": regex,
							"message": f"Value '{coerced}' at {json_path} does not match pattern: {regex}",
						}
					)
			except re.error:
				pass  # Invalid regex, skip validation

		# Validate valueset (required binding only)
		binding = (element_def.get("binding_strength") or "").strip().lower()
		valueset = (element_def.get("valueset_url") or "").strip()

		if binding == "required" and valueset and coerced is not None:
			if not self._validate_code(coerced, valueset):
				self.errors.append(
					{
						"severity": "error",
						"type": "code-invalid",
						"path": json_path,
						"value": coerced,
						"valueset": valueset,
						"message": f"Code '{coerced}' at {json_path} not in required valueset: {valueset}",
					}
				)

		return coerced

	def _process_complex(self, value, datatype_def, element_def, json_path):
		"""Process a complex type value: wrap, validate structure, recurse."""
		datatype_name = datatype_def.get("name", "")

		# Wrap primitive into complex structure if needed
		if not isinstance(value, dict):
			value = self._wrap_primitive(value, datatype_name)

		sub_elements = datatype_def.get("elements", {})

		# Validate required sub-elements
		for el_name, el_def in sub_elements.items():
			min_card = el_def.get("min", 0)
			if min_card and int(min_card) > 0:
				if el_name not in value or value[el_name] is None:
					# Check for choice type alternatives
					if not el_def.get("is_choice_type"):
						self.errors.append(
							{
								"severity": "error",
								"type": "required",
								"path": f"{json_path}.{el_name}",
								"datatype": datatype_name,
								"message": f"{datatype_name} requires element '{el_name}' at {json_path}",
							}
						)

		# Recursively process existing sub-elements
		for key in list(value.keys()):
			# Skip FHIR primitive extensions
			if key.startswith("_"):
				continue

			sub_value = value[key]
			if sub_value is None:
				continue

			if key not in sub_elements:
				self.warnings.append(
					{
						"severity": "warning",
						"type": "unknown-element",
						"path": f"{json_path}.{key}",
						"message": f"Unknown element '{key}' in {datatype_name} at {json_path}",
					}
				)
				continue

			sub_def = sub_elements[key]
			sub_datatype = sub_def.get("datatype", "")
			sub_path = f"{json_path}.{key}"

			value[key] = self._process_value(sub_value, sub_datatype, sub_def, sub_path, sub_path)

		return value

	# =========================================================================
	# Primitive Coercion
	# =========================================================================

	def _coerce_primitive(self, value, datatype_name):
		"""Coerce a value to the correct primitive type."""
		if value is None:
			return None

		try:
			if datatype_name == "boolean":
				if isinstance(value, bool):
					return value
				if isinstance(value, str):
					return value.strip().lower() in ("true", "1", "yes")
				return bool(value)

			if datatype_name in ("integer", "positiveInt", "unsignedInt"):
				return int(value)

			if datatype_name == "decimal":
				return float(value)

			if datatype_name == "date":
				return self._format_date(value)

			if datatype_name == "dateTime":
				return self._format_datetime(value)

			if datatype_name == "instant":
				return self._format_instant(value)

			if datatype_name == "time":
				return self._format_time(value)

			if datatype_name == "code":
				return str(value).strip()

			if datatype_name == "base64Binary":
				return self._ensure_base64(value)

			# string, uri, url, canonical, id, oid, uuid, markdown, xhtml
			return str(value)

		except (ValueError, TypeError):
			self.warnings.append(
				{
					"severity": "warning",
					"type": "coercion-failed",
					"datatype": datatype_name,
					"value": str(value),
					"message": f"Could not coerce '{value}' to {datatype_name}",
				}
			)
			return str(value)

	def _wrap_primitive(self, value, datatype_name):
		"""Wrap a primitive value into a complex type structure."""
		if datatype_name in self.WRAP_RULES:
			try:
				return self.WRAP_RULES[datatype_name](value)
			except Exception:
				pass

		# Generic fallback
		self.warnings.append(
			{
				"severity": "warning",
				"type": "wrap-fallback",
				"datatype": datatype_name,
				"value": str(value),
				"message": f"No wrap rule for {datatype_name}, using generic wrapper",
			}
		)
		return {"value": value}

	# =========================================================================
	# Date/Time Formatting
	# =========================================================================

	def _format_date(self, value):
		"""Format value as FHIR date (YYYY-MM-DD or partial)."""
		if not value:
			return None

		s = str(value).strip()

		# Already in correct format
		if re.match(r"^\d{4}(-\d{2}(-\d{2})?)?$", s):
			return s

		# Try parsing common formats
		import datetime

		for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]:
			try:
				dt = datetime.datetime.strptime(s[:10], fmt)
				return dt.strftime("%Y-%m-%d")
			except ValueError:
				continue

		# Return as-is if can't parse
		return s

	def _format_datetime(self, value):
		"""Format value as FHIR dateTime."""
		if not value:
			return None

		s = str(value).strip()

		# Already has T separator, likely correct format
		if "T" in s:
			return s

		# Try to parse and format
		import datetime

		for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"]:
			try:
				dt = datetime.datetime.strptime(s[:26], fmt)
				return dt.strftime("%Y-%m-%dT%H:%M:%S")
			except ValueError:
				continue

		return s

	def _format_instant(self, value):
		"""Format value as FHIR instant (with timezone)."""
		if not value:
			return None

		s = str(value).strip()

		# Add Z if no timezone
		if "T" in s and not ("+" in s or "-" in s[10:] or s.endswith("Z")):
			return s + "Z"

		if "T" not in s:
			return self._format_datetime(value) + "Z"

		return s

	def _format_time(self, value):
		"""Format value as FHIR time (hh:mm:ss)."""
		if not value:
			return None

		s = str(value).strip()

		# Extract time portion if datetime
		if "T" in s:
			s = s.split("T")[1].split("+")[0].split("Z")[0]

		if " " in s:
			s = s.split(" ")[-1]

		return s

	def _ensure_base64(self, value):
		"""Ensure value is base64 encoded."""
		import base64

		if not value:
			return None

		s = str(value)

		# Check if already base64
		try:
			base64.b64decode(s, validate=True)
			return s
		except Exception:
			pass

		# Encode as base64
		try:
			return base64.b64encode(s.encode()).decode()
		except Exception:
			return s

	# =========================================================================
	# Validation
	# =========================================================================

	def _validate_code(self, code, valueset_url):
		"""
		Validate a code against a valueset.
		Returns True if valid or if valueset lookup not implemented.
		"""
		# TODO: Implement valueset validation lookup
		# For now, return True to avoid false negatives
		# Could query FHIR Valueset DocType or external terminology service
		return True

	def _handle_missing(self, element_def, fhir_path, json_path):
		"""Handle a missing required element."""
		min_card = element_def.get("min", 0)
		if min_card and int(min_card) > 0:
			self.errors.append(
				{
					"severity": "error",
					"type": "required",
					"path": json_path,
					"fhir_path": fhir_path,
					"message": f"Required element missing: {fhir_path}",
				}
			)

	# =========================================================================
	# Meta
	# =========================================================================

	def _add_meta(self, resource):
		"""Add FHIR meta element to resource."""
		meta = resource.get("meta", {})

		# Profile URLs
		profile_urls = self.meta.get("profile_urls") or []
		if profile_urls:
			meta["profile"] = profile_urls

		# lastUpdated
		meta["lastUpdated"] = frappe.utils.now_datetime().isoformat() + "Z"

		resource["meta"] = meta

	# =========================================================================
	# Path Utilities
	# =========================================================================

	def _get_at_path(self, obj, path):
		"""Get value at a JSON path like 'identifier[0].value'."""
		if not path or not obj:
			return None

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

	def _set_at_path(self, obj, path, value):
		"""Set value at a JSON path like 'identifier[0].value'."""
		if not path:
			return

		parts = self._parse_path(path)
		current = obj

		for i, (key, index) in enumerate(parts[:-1]):
			if key not in current:
				# Determine if next level needs array or object
				next_key, next_index = parts[i + 1]
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

		# Set final value
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

	def _parse_path(self, path):
		"""Parse path like 'identifier[0].value' into [(key, index), ...]."""
		parts = []
		for segment in (path or "").split("."):
			match = re.match(r"(\w+)\[(\d+)\]", segment)
			if match:
				parts.append((match.group(1), int(match.group(2))))
			else:
				parts.append((segment, None))
		return parts

	# =========================================================================
	# Cleanup
	# =========================================================================

	def _clean_empty(self, obj):
		"""Remove empty dicts, lists, and None values recursively."""
		if isinstance(obj, dict):
			keys_to_remove = []
			for key, value in obj.items():
				cleaned = self._clean_empty(value)
				if cleaned is None or cleaned == {} or cleaned == []:
					keys_to_remove.append(key)
				else:
					obj[key] = cleaned

			for key in keys_to_remove:
				del obj[key]

			return obj if obj else None

		if isinstance(obj, list):
			cleaned_list = []
			for item in obj:
				cleaned = self._clean_empty(item)
				if cleaned is not None and cleaned != {} and cleaned != []:
					cleaned_list.append(cleaned)
			return cleaned_list if cleaned_list else None

		return obj

	def _reorder_keys(self, resource):
		"""Reorder resource keys for FHIR convention (resourceType first, etc.)."""
		if not isinstance(resource, dict):
			return resource

		priority_keys = ["resourceType", "id", "meta", "implicitRules", "language", "text"]
		ordered = {}

		# Add priority keys first
		for key in priority_keys:
			if key in resource:
				ordered[key] = resource[key]

		# Add remaining keys
		for key in resource:
			if key not in ordered:
				ordered[key] = resource[key]

		return ordered


# =========================================================================
# Helper Functions
# =========================================================================


def _is_numeric(value):
	"""Check if a value is numeric."""
	if isinstance(value, (int, float)):
		return True
	if isinstance(value, str):
		try:
			float(value)
			return True
		except ValueError:
			return False
	return False
