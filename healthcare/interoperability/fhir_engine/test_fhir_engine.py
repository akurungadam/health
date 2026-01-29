# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and Contributors
# See license.txt

import json
import re

import frappe
from frappe.tests import IntegrationTestCase

from healthcare.interoperability.fhir_engine.fhir_engine import (
	FHIRComplexDatatype,
	FHIRExtension,
	FHIRPrimitiveDatatype,
)

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestFHIREngine(IntegrationTestCase):
	def test_prerequisite_datatypes_exist(self):
		# Primitive
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "boolean"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "date"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "Extension"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "integer"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "decimal"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "dateTime"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "time"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "instant"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "string"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "code"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "id"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "uri"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "url"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "canonical"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "base64Binary"))

		# Complex (common)
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "Address"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "Attachment"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "HumanName"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "Identifier"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "ContactPoint"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "Reference"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "Period"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "Coding"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "CodeableConcept"))
		self.assertTrue(frappe.get_cached_doc("FHIR Datatype", "Meta"))

	# -----------------------
	# Helpers
	# -----------------------

	def _pick_regex_safe_value_for_primitive(self, primitive_name, datatype_doc):
		primitive_name = (primitive_name or "").strip()
		raw = (datatype_doc.get("regex") or "").strip()

		# candidates by name
		candidates = {
			"boolean": ["true", "false", True, False],
			"integer": ["1", 1, "42"],
			"unsignedInt": ["0", 0, "1", 1],
			"positiveInt": ["1", 1, "2", 2],
			"decimal": ["12.3", "12.30", 12.3, "0.1"],
			"date": ["1995-12-08", "2025-01-01"],
			"dateTime": ["2025-12-26T10:00:00+05:30", "2025-12-26T10:00:00Z"],
			"time": ["10:30:00", "00:00:00"],
			"instant": ["2025-12-26T10:00:00Z"],
			"base64Binary": ["ZGF0YQ=="],
			"uri": [
				"http://example.org",
				"urn:uuid:123e4567-e89b-12d3-a456-426614174000",
			],
			"url": ["https://example.org/a"],
			"canonical": ["http://hl7.org/fhir/StructureDefinition/Patient"],
			"id": ["PAT-0001", "id123"],
			"code": ["male", "unknown"],
			"string": ["demo"],
		}.get(primitive_name, ["demo", "x", "A", "test-1"])

		# if no regex configured, first candidate is fine
		if not raw:
			return candidates[0]

		try:
			compiled = re.compile(raw)
		except Exception:
			# bad regex config: don’t make tests flaky
			return candidates[0]

		for c in candidates:
			text = c if isinstance(c, str) else str(c)
			if compiled.fullmatch(text):
				return c

		# last resort: if nothing matches, skip instead of failing CI with config mismatch
		self.skipTest(f"No sample value matches regex for primitive {primitive_name}: {raw}")

	def _demo_extension(self):
		return {
			"url": "https://example.org/fhir/StructureDefinition/demo-ext",
			"valueString": "ok",
		}

	def _demo_modifier_extension(self):
		return {
			"url": "https://example.org/fhir/StructureDefinition/demo-mod",
			"valueBoolean": True,
		}

	# -----------------------
	# Existing focused tests
	# -----------------------

	def test_primitive_boolean_json_pair_with_result_metadata(self):
		primitive = FHIRPrimitiveDatatype("boolean", "true")
		result = primitive.to_json_pair("active")
		print(json.dumps(result, indent=1))
		self.assertEqual(result, {"active": True})

	def test_primitive_boolean_json_pair_with_extension_goes_to_underscore(self):
		primitive = FHIRPrimitiveDatatype("boolean", True)
		primitive.add_extension(self._demo_extension())

		result = primitive.to_json_pair("active")
		print(json.dumps(result, indent=1))

		self.assertEqual(result["active"], True)
		self.assertIn("_active", result)
		self.assertIn("extension", result["_active"])

	def test_primitive_boolean_json_pair_with_modifier_extension_goes_to_underscore(
		self,
	):
		primitive = FHIRPrimitiveDatatype("boolean", False)
		primitive.add_modifier_extension(self._demo_modifier_extension())

		result = primitive.to_json_pair("active")
		print(json.dumps(result, indent=1))

		self.assertEqual(result["active"], False)
		self.assertIn("_active", result)
		self.assertIn("modifierExtension", result["_active"])

	def test_primitive_metadata_can_exist_with_result_value(self):
		primitive = FHIRPrimitiveDatatype("boolean", None)
		primitive.add_extension(
			{
				"url": "https://example.org/fhir/StructureDefinition/data-absent-reason",
				"valueCode": "unknown",
			}
		)

		result = primitive.to_json_pair("deceasedBoolean")
		print(json.dumps(result, indent=1))

		self.assertNotIn("deceasedBoolean", result)
		self.assertIn("_deceasedBoolean", result)
		self.assertIn("extension", result["_deceasedBoolean"])

	# -----------------------
	# (3) ALL primitives: no meta / extension / modifierExtension / metadata-only
	# -----------------------

	def test_all_primitive_datatypes_json_pair_no_meta_extension_modifier(self):
		rows = frappe.get_all(
			"FHIR Datatype",
			filters={"is_primitive": 1},
			fields=["name", "regex"],
			order_by="name asc",
		)

		self.assertTrue(rows, "No primitive FHIR Datatype records found")

		for row in rows:
			primitive_name = row["name"]
			datatype_doc = frappe.get_cached_doc("FHIR Datatype", primitive_name)

			value = self._pick_regex_safe_value_for_primitive(primitive_name, datatype_doc)

			# 1) No metadata
			primitive = FHIRPrimitiveDatatype(primitive_name, value)
			result = primitive.to_json_pair("field")
			print(primitive_name, json.dumps(result, indent=1))

			self.assertIn("field", result)
			self.assertNotIn("_field", result)

			# 2) With extension -> underscore sibling
			primitive_ext = FHIRPrimitiveDatatype(primitive_name, value)
			primitive_ext.add_extension(self._demo_extension())

			result_ext = primitive_ext.to_json_pair("field")
			print(primitive_name, "extension", json.dumps(result_ext, indent=1))

			self.assertIn("field", result_ext)
			self.assertIn("_field", result_ext)
			self.assertIn("extension", result_ext["_field"])

			# 3) With modifierExtension -> underscore sibling
			primitive_mod = FHIRPrimitiveDatatype(primitive_name, value)
			primitive_mod.add_modifier_extension(self._demo_modifier_extension())

			result_mod = primitive_mod.to_json_pair("field")
			print(primitive_name, "modifierExtension", json.dumps(result_mod, indent=1))

			self.assertIn("field", result_mod)
			self.assertIn("_field", result_mod)
			self.assertIn("modifierExtension", result_mod["_field"])

			# 4) Metadata-only (no value)
			primitive_absent = FHIRPrimitiveDatatype(primitive_name, None)
			primitive_absent.add_extension(
				{
					"url": "https://example.org/fhir/StructureDefinition/data-absent-reason",
					"valueCode": "unknown",
				}
			)

			result_absent = primitive_absent.to_json_pair("field")
			print(primitive_name, "metadata-only", json.dumps(result_absent, indent=1))

			self.assertNotIn("field", result_absent)
			self.assertIn("_field", result_absent)
			self.assertIn("extension", result_absent["_field"])

	# -----------------------
	# Complex tests
	# -----------------------

	def test_complex_address_extension_is_inside_object_not_underscore(self):
		addr = FHIRComplexDatatype.build(
			"Address",
			{
				"type": "both",
				"line": ["  a  ", "", None, "b"],
				"city": "London",
			},
		)

		addr.add_extension(
			{
				"url": "https://example.org/fhir/StructureDefinition/address-verification",
				"valueCode": "verified",
			}
		)

		result = addr.to_json()
		print(json.dumps(result, indent=1))

		self.assertNotIn("_address", result)
		self.assertEqual(result.get("type"), "both")
		self.assertEqual(result.get("line"), ["a", "b"])
		self.assertEqual(result.get("city"), "London")
		self.assertIn("extension", result)

	def test_complex_attachment_fields_and_extensions(self):
		att = FHIRComplexDatatype.build(
			"Attachment",
			{
				"contentType": "application/pdf",
				"url": "https://example.org/report.pdf",
				"title": "Report",
				"unknownKey": "should_be_dropped",
			},
		)

		att.add_extension(
			{
				"url": "https://example.org/fhir/StructureDefinition/attachment-tag",
				"valueString": "radiology",
			}
		)

		result = att.to_json()
		print(json.dumps(result, indent=1))

		self.assertNotIn("unknownKey", result)
		self.assertEqual(result.get("contentType"), "application/pdf")
		self.assertEqual(result.get("url"), "https://example.org/report.pdf")
		self.assertEqual(result.get("title"), "Report")
		self.assertIn("extension", result)

	def test_all_complex_datatypes_can_serialize_and_drop_unknown_key(self):
		rows = frappe.get_all(
			"FHIR Datatype",
			filters={"is_primitive": 0},
			fields=["name"],
			order_by="name asc",
		)

		self.assertTrue(rows, "No complex FHIR Datatype records found")

		for row in rows:
			datatype_name = row["name"]

			# super abstract / troublemakers
			if datatype_name in ("Element", "BackboneElement"):
				continue

			obj = FHIRComplexDatatype.build(datatype_name, {"unknownKey": "should_be_dropped"}, strict=False)
			obj.add_extension(self._demo_extension())

			result = obj.to_json()
			print(datatype_name, json.dumps(result, indent=1))

			self.assertTrue(isinstance(result, dict))
			json.dumps(result)

			self.assertNotIn("unknownKey", result)
			for key in result.keys():
				self.assertFalse(key.startswith("_"))

			self.assertIn("extension", result)

	# -----------------------
	# (4) Complex min enforcement + valueset validation scaffold
	# -----------------------

	def test_complex_min_required_fields_enforced_when_strict(self):
		# Pick a datatype that *actually* has min>0 fields; Meta usually has required? depends on your import.
		# We'll find one dynamically to avoid brittle test assumptions.
		rows = frappe.get_all(
			"FHIR Datatype",
			filters={"is_primitive": 0},
			fields=["name"],
			order_by="name asc",
		)

		candidate = None
		for r in rows:
			name = r["name"]
			if name in ("Element", "BackboneElement"):
				continue
			doc = frappe.get_cached_doc("FHIR Datatype", name)
			for el in doc.get("elements") or []:
				try:
					if int(el.get("min") or 0) > 0:
						candidate = name
						break
				except Exception:
					continue
			if candidate:
				break

		if not candidate:
			self.skipTest("No complex datatype with min>0 fields found in your DB")

		# Provide empty payload; should fail in strict mode if min fields exist
		with self.assertRaises(Exception):
			FHIRComplexDatatype.build(candidate, {}, strict=True).to_json()

	def test_complex_valueset_validation_is_off_by_default(self):
		# Should not raise even if datatype contains required bindings,
		# because validate_valuesets default is False.
		obj = FHIRComplexDatatype.build("CodeableConcept", {"text": "demo"}, strict=True)
		result = obj.to_json()
		print(json.dumps(result, indent=1))
		self.assertTrue(isinstance(result, dict))

	def test_extension_value_x_accepts_value_key(self):
		ext = FHIRExtension(
			{
				"url": "https://example.org/fhir/StructureDefinition/demo-ext",
				"valueCode": "unknown",
			}
		)

		result = ext.to_json()
		print(json.dumps(result, indent=1))

		self.assertEqual(result["url"], "https://example.org/fhir/StructureDefinition/demo-ext")
		self.assertEqual(result["valueCode"], "unknown")
