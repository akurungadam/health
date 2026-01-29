# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt


# Datatype helpers: schema-driven primitives + schema-driven complex datatypes + schema-driven Extension.
# - Primitives validate against FHIR Datatype.regex (if present)
# - Complex datatypes allow only fields present in FHIR Datatype.elements
# - Complex datatypes preserve lists (including lists of dicts) instead of collapsing to strings
# - Extension enforces allowed value keys from FHIR Datatype.elements (value[x] => allow any value*)
#
# NOTE: This file expects FHIR Datatype child table rows to have:
# - element_name (e.g. "Address.city", "Extension.value[x]")
# - min, max, is_choice_type (optional)

# Schema-driven FHIR datatype serializers (primitive + complex) using "FHIR Datatype" and "FHIR Datatype Element"
import re
from decimal import Decimal

import frappe


def safe_attr_name(fieldname):
	# Avoid python reserved-ish names in input dicts (type/class/from)
	if fieldname in ("type", "class", "from"):
		return fieldname + "_"
	return fieldname


class FHIRExtension:
	DATATYPE_NAME = "Extension"

	def __init__(self, value=None, datatype_doc=None):
		self.url = None
		self.value = None  # {"valueString": "..."} etc.
		self._datatype_doc = datatype_doc
		self._allowed_value_keys = None

		self._load_schema()
		if value is not None:
			self.load(value)

	def _load_schema(self):
		doc = self._datatype_doc or frappe.get_cached_doc("FHIR Datatype", self.DATATYPE_NAME)

		allowed = set()
		has_value_x = 0
		prefix = "Extension."

		for row in doc.get("elements") or []:
			path = (row.get("element_name") or "").strip()
			if not path.startswith(prefix):
				continue

			field = (path[len(prefix) :] or "").strip()
			if not field:
				continue

			if field == "value[x]":
				has_value_x = 1
				continue

			if field.startswith("value"):
				allowed.add(field)

		self._allowed_value_keys = None if has_value_x else allowed

	def load(self, value):
		if isinstance(value, FHIRExtension):
			self.url = value.url
			self.value = value.value
			return

		if isinstance(value, dict):
			self.url = (value.get("url") or "").strip() or None

			# normalized form: {"value": {"valueString": "x"}}
			if isinstance(value.get("value"), dict):
				self.value = value.get("value")
				return

			# FHIR JSON form: {"valueString": "x"}
			for k, v in value.items():
				if not (k.startswith("value") and k != "value"):
					continue

				if self._allowed_value_keys is not None and k not in self._allowed_value_keys:
					# schema enumerates allowed value keys; drop invalid ones
					continue

				self.value = {k: v}
				return

		raise ValueError("Invalid FHIR Extension")

	def to_json(self):
		if not self.url:
			return None
		out = {"url": self.url}
		if isinstance(self.value, dict) and self.value:
			out.update(self.value)
		return out


class FHIRDatatypeBase:
	def __init__(self):
		self.id = None
		self.extension = []
		self.modifierExtension = []

	def add_extension(self, extension):
		ext = FHIRExtension(extension).to_json()
		if ext:
			self.extension.append(ext)

	def add_modifier_extension(self, extension):
		ext = FHIRExtension(extension).to_json()
		if ext:
			self.modifierExtension.append(ext)

	def _json_metadata(self):
		out = {}
		if self.id:
			out["id"] = self.id
		if self.extension:
			out["extension"] = list(self.extension)
		if self.modifierExtension:
			out["modifierExtension"] = list(self.modifierExtension)
		return out

	def _is_empty(self, value):
		if value is None:
			return True
		if value == "":
			return True
		if isinstance(value, list) and not value:
			return True
		if isinstance(value, dict) and not value:
			return True
		return False


class FHIRPrimitiveDatatype(FHIRDatatypeBase):
	"""
	Schema-driven primitive serializer:
	- Reads regex from `FHIR Datatype.regex` (your schema)
	- Does basic JSON-type coercion for boolean/integer/decimal
	- Emits underscore metadata only when needed
	"""

	def __init__(self, primitive_name, value=None, strict=True, datatype_doc=None):
		super().__init__()
		self.primitive_name = (primitive_name or "").strip()
		self.value = value
		self.strict = 1 if strict else 0

		if not self.primitive_name:
			frappe.throw("primitive_name is required")

		self._datatype_doc = datatype_doc or frappe.get_cached_doc("FHIR Datatype", self.primitive_name)

		self._constraints = self._load_constraints(self._datatype_doc)

	def _fail_or_return(self, message, fallback=None):
		if self.strict:
			frappe.throw(message)
		return fallback

	def _load_constraints(self, datatype_doc):
		# Your actual doctype schema includes only `regex` for now.
		# We still keep hooks for future knobs, but they default safely.
		raw_regex = (datatype_doc.get("regex") or "").strip() or None

		regex_compiled = None
		if raw_regex:
			try:
				regex_compiled = re.compile(raw_regex)
			except Exception:
				# bad config must not break runtime
				regex_compiled = None
				raw_regex = None

		return {
			"regex_pattern": raw_regex,
			"regex_compiled": regex_compiled,
			"normalize_trim": 1,
			"normalize_lowercase": 0,
		}

	def _normalize_text(self, value):
		if value is None:
			return None
		text = str(value)
		if self._constraints.get("normalize_trim"):
			text = text.strip()
		if self._constraints.get("normalize_lowercase"):
			text = text.lower()
		return text

	def _validate_regex(self, text):
		compiled = self._constraints.get("regex_compiled")
		if not compiled:
			return text
		text = "" if text is None else str(text)
		if compiled.fullmatch(text):
			return text
		return self._fail_or_return(
			f"Invalid value for {self.primitive_name}: {text}",
			None,
		)

	def to_json_value(self):
		if self.value is None or self.value == "":
			return None

		primitive = self.primitive_name

		# boolean -> JSON bool
		if primitive == "boolean":
			if isinstance(self.value, bool):
				return self.value

			text = (self._normalize_text(self.value) or "").lower()
			if text in ("true", "1", "yes", "y", "t"):
				return True
			if text in ("false", "0", "no", "n", "f"):
				return False

			return self._fail_or_return(f"Invalid boolean value: {self.value}", None)

		# integer family -> JSON int
		if primitive in ("integer", "unsignedInt", "positiveInt"):
			if isinstance(self.value, bool):
				return self._fail_or_return("Invalid integer: boolean not allowed", None)

			text = self._normalize_text(self.value)
			try:
				num = int(text)
			except Exception:
				return self._fail_or_return(f"Invalid integer value: {self.value}", None)

			if primitive == "unsignedInt" and num < 0:
				return self._fail_or_return("unsignedInt must be >= 0", None)
			if primitive == "positiveInt" and num < 1:
				return self._fail_or_return("positiveInt must be >= 1", None)

			# regex applies to string representation (if present)
			if self._constraints.get("regex_compiled"):
				self._validate_regex(str(num))

			return num

		# decimal -> JSON number (float)
		if primitive == "decimal":
			if isinstance(self.value, bool):
				return self._fail_or_return("Invalid decimal: boolean not allowed", None)

			text = self._normalize_text(self.value)
			try:
				num = float(Decimal(text))
			except Exception:
				return self._fail_or_return(f"Invalid decimal value: {self.value}", None)

			if self._constraints.get("regex_compiled"):
				self._validate_regex(str(self.value).strip())

			return num

		# everything else treated as string-ish
		text = self._normalize_text(self.value)
		if not text:
			return None

		text = self._validate_regex(text)
		return text

	def to_json_pair(self, json_key):
		"""
		FHIR primitive JSON shape:
		{ "<key>": <scalar>, "_<key>": { "id": ..., "extension": [...], "modifierExtension": [...] } }

		- underscore key emitted only if metadata exists
		- metadata-only is allowed (value missing)
		"""
		out = {}

		value = self.to_json_value()
		if value is not None and value != "":
			out[json_key] = value

		meta = self._json_metadata()
		if meta:
			out["_" + json_key] = meta

		return out


class FHIRComplexDatatype(FHIRDatatypeBase):
	"""
	Schema-driven complex datatype serializer.

	Reads from:
	- FHIR Datatype (name = DATATYPE_NAME)
	- child table: elements (FHIR Datatype Element)
	  fields used: element_name, min, max, is_choice_type, valueset_url, binding_strength

	Features:
	- Drops unknown keys
	- Normalizes string values (trim)
	- Handles repeating fields
	- Enforces `min` (required) when `strict=True`
	- Valueset validation scaffold (off by default)
	"""

	DATATYPE_NAME = None
	SCALAR_FALLBACK_FIELD = None

	_CLASS_CACHE = {}

	def __init__(
		self, value=None, datatype_doc=None, strict=True, validate_valuesets=False, valueset_resolver=None
	):
		super().__init__()
		self.strict = 1 if strict else 0
		self.validate_valuesets = 1 if validate_valuesets else 0
		self.valueset_resolver = valueset_resolver

		self._datatype_doc = datatype_doc
		self._schema = None
		self._values = {}

		self._load_schema()
		if value is not None:
			self.load(value)

	def _fail_or_return(self, message, fallback=None):
		if self.strict:
			frappe.throw(message)
		return fallback

	# ---------- factory ----------

	@classmethod
	def guess_scalar_fallback_field(cls, datatype_name):
		datatype_name = (datatype_name or "").strip()

		if datatype_name in ("Address", "HumanName", "CodeableConcept"):
			return "text"
		if datatype_name in ("Identifier", "ContactPoint"):
			return "value"
		if datatype_name == "Reference":
			return "reference"
		if datatype_name == "Attachment":
			return "url"
		if datatype_name == "Coding":
			return "code"

		return None

	@classmethod
	def for_name(cls, datatype_name, scalar_fallback_field=None):
		datatype_name = (datatype_name or "").strip()
		if not datatype_name:
			frappe.throw("datatype_name is required")

		if scalar_fallback_field is None:
			scalar_fallback_field = cls.guess_scalar_fallback_field(datatype_name)

		cache_key = (datatype_name, scalar_fallback_field or "")
		if cache_key in cls._CLASS_CACHE:
			return cls._CLASS_CACHE[cache_key]

		datatype_doc = frappe.get_cached_doc("FHIR Datatype", datatype_name)
		if int(datatype_doc.get("is_primitive") or 0):
			frappe.throw(f"Datatype is primitive, not complex: {datatype_name}")

		class DynamicFHIRComplexDatatype(FHIRComplexDatatype):
			DATATYPE_NAME = datatype_name
			SCALAR_FALLBACK_FIELD = scalar_fallback_field

		DynamicFHIRComplexDatatype.__name__ = f"FHIR{datatype_name}"

		cls._CLASS_CACHE[cache_key] = DynamicFHIRComplexDatatype
		return DynamicFHIRComplexDatatype

	@classmethod
	def build(
		cls,
		datatype_name,
		value=None,
		datatype_doc=None,
		scalar_fallback_field=None,
		strict=True,
		validate_valuesets=False,
		valueset_resolver=None,
	):
		DatatypeClass = cls.for_name(datatype_name, scalar_fallback_field=scalar_fallback_field)
		return DatatypeClass(
			value=value,
			datatype_doc=datatype_doc,
			strict=strict,
			validate_valuesets=validate_valuesets,
			valueset_resolver=valueset_resolver,
		)

	# ---------- schema ----------

	def _load_schema(self):
		if not self.DATATYPE_NAME:
			frappe.throw("DATATYPE_NAME must be set")

		if not self._datatype_doc:
			self._datatype_doc = frappe.get_cached_doc("FHIR Datatype", self.DATATYPE_NAME)

		self._schema = self._build_schema(self._datatype_doc)

	def _build_schema(self, datatype_doc):
		fields = {}
		prefix = self.DATATYPE_NAME + "."

		for row in datatype_doc.get("elements") or []:
			path = (row.get("element_name") or "").strip()
			if not path.startswith(prefix):
				continue

			suffix = path[len(prefix) :]
			fieldname = (suffix.split(".", 1)[0] or "").strip()
			if not fieldname:
				continue

			try:
				min_value = int(row.get("min") or 0)
			except Exception:
				min_value = 0

			max_value = str(row.get("max") or "1").strip()
			is_repeating = max_value == "*"
			if not is_repeating:
				try:
					is_repeating = int(max_value) > 1
				except Exception:
					is_repeating = False

			fields[fieldname] = {
				"fieldname": fieldname,
				"attr_name": safe_attr_name(fieldname),
				"min": min_value,
				"max": max_value,
				"is_repeating": is_repeating,
				"is_choice_type": int(row.get("is_choice_type") or 0),
				"valueset_url": (row.get("valueset_url") or "").strip() or None,
				"binding_strength": (row.get("binding_strength") or "").strip() or None,
				"datatype": (row.get("datatype") or "").strip() or None,
			}

		target_field = self.SCALAR_FALLBACK_FIELD
		target_attr = None
		if target_field and target_field in fields:
			target_attr = fields[target_field]["attr_name"]
		elif "text" in fields and not fields["text"]["is_repeating"]:
			target_attr = fields["text"]["attr_name"]
		elif "url" in fields and not fields["url"]["is_repeating"]:
			target_attr = fields["url"]["attr_name"]
		else:
			for meta in fields.values():
				if not meta["is_repeating"]:
					target_attr = meta["attr_name"]
					break

		return {"fields": fields, "scalar_target_attr": target_attr}

	# ---------- loading ----------

	def load(self, value):
		if isinstance(value, self.__class__):
			self.id = value.id
			self.extension = list(value.extension or [])
			self.modifierExtension = list(value.modifierExtension or [])
			self._values = dict(value._values or {})
			return

		if isinstance(value, dict):
			self._load_from_dict(value)
			return

		# scalar fallback
		target_attr = self._schema.get("scalar_target_attr")
		if target_attr:
			self._set_attr_value(target_attr, value)

	def _load_from_dict(self, payload):
		if payload.get("id"):
			self.id = payload.get("id")

		for ext in payload.get("extension") or []:
			self.add_extension(ext)
		for ext in payload.get("modifierExtension") or []:
			self.add_modifier_extension(ext)

		for fieldname, meta in self._schema["fields"].items():
			attr = meta["attr_name"]

			raw = None
			if fieldname in payload:
				raw = payload.get(fieldname)
			elif attr in payload:
				raw = payload.get(attr)

			if raw is None:
				continue

			self._set_attr_value(attr, raw)

	def _meta_for_attr(self, attr):
		for meta in self._schema["fields"].values():
			if meta["attr_name"] == attr:
				return meta
		return None

	def _set_attr_value(self, attr, raw):
		meta = self._meta_for_attr(attr)
		if not meta:
			return

		if meta["is_repeating"]:
			items = raw if isinstance(raw, list) else [raw]
			normalized = []
			for item in items:
				item = self._normalize_value(item)
				if not self._is_empty(item):
					normalized.append(item)
			if normalized:
				self._values[attr] = normalized
		else:
			item = self._normalize_value(raw)
			if not self._is_empty(item):
				self._values[attr] = item

	def _normalize_value(self, value):
		if isinstance(value, dict):
			return self._strip_empty_dict(value)
		if isinstance(value, list):
			text = " ".join([str(x) for x in value if x is not None]).strip()
			return text or None
		if value is None:
			return None
		text = str(value).strip()
		return text or None

	def _strip_empty_dict(self, d):
		out = {}
		for k, v in (d or {}).items():
			if isinstance(v, dict):
				v = self._strip_empty_dict(v)
			elif isinstance(v, list):
				new_list = []
				for item in v:
					if isinstance(item, dict):
						item = self._strip_empty_dict(item)
					if not self._is_empty(item):
						new_list.append(item)
				v = new_list

			if self._is_empty(v):
				continue
			out[k] = v
		return out

	# ---------- validation ----------

	def _enforce_min_required(self, out_json):
		missing = []
		for fieldname, meta in self._schema["fields"].items():
			if int(meta.get("min") or 0) < 1:
				continue

			val = out_json.get(fieldname)
			if self._is_empty(val):
				missing.append(fieldname)

		if missing:
			return self._fail_or_return(
				"{0} is missing required fields: {1}".format(self.DATATYPE_NAME, ", ".join(missing)),
				out_json,
			)

		return out_json

	def _validate_required_valuesets(self, out_json):
		# OFF by default. Only runs if validate_valuesets=True.
		if not self.validate_valuesets:
			return out_json

		for fieldname, meta in self._schema["fields"].items():
			strength = (meta.get("binding_strength") or "").strip().lower()
			valueset_url = meta.get("valueset_url")

			if strength != "required" or not valueset_url:
				continue

			val = out_json.get(fieldname)
			if self._is_empty(val):
				# required binding doesn't mean required field; it means if present must be in VS.
				continue

			if not self.valueset_resolver:
				# Don’t break prod silently; but also don’t explode unless strict.
				self._fail_or_return(
					f"Valueset resolver not configured for required binding: {self.DATATYPE_NAME}.{fieldname} -> {valueset_url}",
					out_json,
				)
				continue

			ok = self.valueset_resolver(valueset_url, val, meta)
			if not ok:
				self._fail_or_return(
					f"Value not in required ValueSet: {self.DATATYPE_NAME}.{fieldname} -> {valueset_url}",
					out_json,
				)

		return out_json

	# ---------- serialization ----------

	def to_json(self):
		out = {}

		# schema-driven: only allowed keys
		for fieldname, meta in self._schema["fields"].items():
			val = self._values.get(meta["attr_name"])
			if self._is_empty(val):
				continue
			out[fieldname] = val

		out.update(self._json_metadata())

		# semantic checks
		self._enforce_min_required(out)
		self._validate_required_valuesets(out)

		return out
