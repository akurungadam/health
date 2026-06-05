# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Value resolution for the FHIR runtime.

Resolves a compiled element's ``value_spec`` against a source document, coerces
the result to its FHIR datatype, and builds Reference objects. Kept separate
from FHIRRuntime so the runtime stays focused on source loading and assembly.
"""

import re
from datetime import date, datetime

import frappe

# FHIR ids must match [A-Za-z0-9.-]{1,64}; Frappe docnames can contain spaces and
# other characters that are illegal there (e.g. a Patient named "John Doe").
FHIR_ID_INVALID = re.compile(r"[^A-Za-z0-9.\-]+")

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


class ValueResolver:
	"""Turns a compiled element + source doc into a FHIR value."""

	def __init__(self):
		self.issues = []

	def resolve(self, element, doc):
		"""Resolve a full element value (value_spec -> default -> datatype/reference)."""
		value_spec = element.get("value_spec") or {}
		value = self.resolve_value_spec(value_spec, doc)

		if (value is None or value == "") and value_spec.get("default") is not None:
			value = value_spec["default"]

		datatype = (element.get("datatype") or "").strip().lower()
		if datatype == "reference":
			if value is None or value == "":
				return None
			return self.build_reference(element, value, doc)

		return self.transform(datatype, value)

	def resolve_value_spec(self, value_spec, doc):
		kind = value_spec.get("kind")

		if kind in ("fixed", "json"):
			value = value_spec.get("value")
		elif kind == "field":
			value = self.get_field(doc, value_spec.get("fieldname"))
		elif kind == "expression":
			value = self._evaluate(value_spec.get("expression"), doc)
		else:
			value = None

		return self._apply_map(value_spec, value)

	def _apply_map(self, value_spec, value):
		"""Translate a resolved value via an optional ``map`` (e.g. local code -> FHIR code).

		``"map": {"Male": "male", "Female": "female", "*": "unknown"}`` - the ``*``
		key, if present, is the fallback for unmapped values.
		"""
		mapping = value_spec.get("map")
		if not isinstance(mapping, dict) or value is None:
			return value
		return mapping.get(str(value), mapping.get("*", value))

	def get_field(self, doc, fieldname):
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

	def _evaluate(self, expression, doc):
		if not expression:
			return None
		try:
			return frappe.safe_eval(expression, eval_locals={"doc": doc})
		except Exception as e:
			self.issues.append(f"Expression failed: {expression} - {e!s}")
			return None

	# =========================================================
	# References
	# =========================================================

	def build_reference(self, element, value, doc):
		config = element.get("reference") or {}
		resource_type = config.get("resource_type")

		reference = {}
		if resource_type:
			reference["reference"] = f"{resource_type}/{self._fhir_id(value)}"
			reference["type"] = resource_type
		else:
			reference["reference"] = str(value)

		display_field = config.get("display_field")
		if display_field:
			display = self.get_field(doc, display_field)
			if display:
				reference["display"] = str(display)

		return reference

	def _fhir_id(self, value):
		"""Coerce a Frappe docname into a valid FHIR id (slugify illegal chars).

		Deterministic so the same docname always yields the same id; the original
		docname is preserved in the reference ``display``. Inbound import should
		match on a stored identifier rather than reverse this slug.
		"""
		token = FHIR_ID_INVALID.sub("-", str(value).strip()).strip("-")
		return token[:64]

	# =========================================================
	# Datatype coercion
	# =========================================================

	def transform(self, datatype, value):
		if value is None:
			return None

		datatype = (datatype or "").strip().lower()

		if datatype == "boolean":
			if isinstance(value, str):
				return value.strip().lower() in ("1", "true", "yes")
			return bool(value)
		if datatype in ("integer", "positiveint", "unsignedint"):
			return self._to_int(value)
		if datatype == "decimal":
			return self._to_float(value)
		if datatype == "date":
			return self._format_date(value)
		if datatype in ("datetime", "instant"):
			return self._format_datetime(value)
		if datatype == "string" or datatype in PRIMITIVE_STRING_TYPES:
			return str(value)

		# complex / unknown datatypes pass through unchanged
		return value

	def _to_int(self, value):
		try:
			return int(value)
		except (ValueError, TypeError):
			return None

	def _to_float(self, value):
		try:
			return float(value)
		except (ValueError, TypeError):
			return None

	def _format_date(self, value):
		if hasattr(value, "strftime"):
			return value.strftime("%Y-%m-%d")
		return str(value)[:10]

	def _format_datetime(self, value):
		dt = self._coerce_datetime(value)
		if dt is None:
			return str(value)
		# A FHIR dateTime/instant carrying a time must carry a timezone; a naive
		# value is assumed to be in the site's timezone. An offset already on the
		# value is preserved.
		if isinstance(dt, datetime) and dt.tzinfo is None:
			dt = dt.replace(tzinfo=self._system_tzinfo())
		return dt.isoformat()

	def _coerce_datetime(self, value):
		if isinstance(value, (datetime, date)):
			return value
		text = str(value).strip()
		if not text:
			return None
		try:
			return datetime.fromisoformat(text.replace("Z", "+00:00"))
		except ValueError:
			pass
		try:
			return frappe.utils.get_datetime(text)
		except Exception:
			return None

	def _system_tzinfo(self):
		try:
			from zoneinfo import ZoneInfo

			return ZoneInfo(frappe.utils.get_system_timezone())
		except Exception:
			return datetime.now().astimezone().tzinfo
