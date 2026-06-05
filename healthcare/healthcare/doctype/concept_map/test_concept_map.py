# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from healthcare.healthcare.doctype.concept_map.concept_map import TerminologyService

LOCAL_CS = "_Test Local Status"
LOCAL_URI = "https://marley.health/cs/local-status"
FHIR_CS = "_Test FHIR Status"
FHIR_URI = "http://hl7.org/fhir/observation-status"


def _code_system(name, uri):
	if not frappe.db.exists("Code System", name):
		frappe.get_doc({"doctype": "Code System", "code_system": name, "uri": uri}).insert()


def _code_value(code, system, display=None):
	if not frappe.db.exists("Code Value", {"code_value": code, "code_system": system}):
		frappe.get_doc(
			{
				"doctype": "Code Value",
				"code_value": code,
				"code_system": system,
				"display": display or code,
			}
		).insert()
	return frappe.db.get_value("Code Value", {"code_value": code, "code_system": system})


class TestConceptMap(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_code_system(LOCAL_CS, LOCAL_URI)
		_code_system(FHIR_CS, FHIR_URI)
		source = _code_value("Final", LOCAL_CS)
		target = _code_value("final", FHIR_CS, display="Final")
		if not frappe.db.exists("Concept Map", source):
			frappe.get_doc(
				{
					"doctype": "Concept Map",
					"source_code": source,
					"targets": [{"target_code": target}],
				}
			).insert()

	def test_translate_returns_target_coding(self):
		self.assertEqual(
			TerminologyService.translate("Final", system=LOCAL_CS),
			[{"code": "final", "system": FHIR_URI, "display": "Final"}],
		)

	def test_translate_no_match_returns_empty(self):
		self.assertEqual(TerminologyService.translate("DoesNotExist", system=LOCAL_CS), [])

	def test_lookup_returns_own_coding(self):
		self.assertEqual(
			TerminologyService.lookup("final", system=FHIR_CS),
			{"code": "final", "system": FHIR_URI, "display": "Final"},
		)

	def test_duplicate_target_is_rejected(self):
		target = _code_value("final", FHIR_CS, display="Final")
		# the "Final" source already has a Concept Map (autonamed by source_code), so
		# use a fresh source to test the duplicate-target guard on its own document
		other = _code_value("Amended", LOCAL_CS)
		dupe = frappe.get_doc(
			{
				"doctype": "Concept Map",
				"source_code": other,
				"targets": [{"target_code": target}, {"target_code": target}],
			}
		)
		self.assertRaises(frappe.ValidationError, dupe.insert)
