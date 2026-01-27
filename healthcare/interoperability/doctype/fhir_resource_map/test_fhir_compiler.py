import frappe
from frappe.tests import IntegrationTestCase


# --- adjust these imports to your real file paths ---
from healthcare.interoperability.doctype.fhir_resource_map.fhir_compiler import (
	FHIRMappingCompiler,
	FHIRMappingCompilationError,
)
from healthcare.interoperability.doctype.fhir_resource_map.fhir_value_resolver import (
	FHIRValueResolver,
	FHIRValueResolutionError,
)


class TestFHIRCompilerAndResolver(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._ensure_test_doctypes()

	@classmethod
	def tearDownClass(cls):
		cls._cleanup_test_doctypes()
		super().tearDownClass()

	def setUp(self):
		self._cleanup_test_records()

	def tearDown(self):
		self._cleanup_test_records()

	# =========================================================
	# Tests
	# =========================================================

	def test_compiler_collapses_object_groups_and_child_table_rows(self):
		resource_map = self._build_resource_map()
		compiled = FHIRMappingCompiler(resource_map).compile()

		elements = compiled.get("elements") or {}

		# identifier leafs should be gone, container should exist
		self.assertIn("Patient.identifier", elements)
		self.assertNotIn("Patient.identifier.type", elements)
		self.assertNotIn("Patient.identifier.use", elements)
		self.assertNotIn("Patient.identifier.value", elements)
		self.assertEqual((elements["Patient.identifier"]["value_spec"]["kind"] or "").strip(), "object_group")

		# link leafs should be gone, container should exist (fixed-only children allowed)
		self.assertIn("Patient.link", elements)
		self.assertNotIn("Patient.link.other", elements)
		self.assertNotIn("Patient.link.type", elements)
		self.assertEqual((elements["Patient.link"]["value_spec"]["kind"] or "").strip(), "object_group")

		# telecom should be child_table_rows (no sibling arrays)
		self.assertIn("Patient.telecom", elements)
		self.assertEqual((elements["Patient.telecom"]["value_spec"]["kind"] or "").strip(), "child_table_rows")
		self.assertIn("row_mapping", elements["Patient.telecom"]["value_spec"])
		self.assertIn("row_constraints", elements["Patient.telecom"]["value_spec"])

	def test_resolver_outputs_grouped_identifier_link_and_rows_telecom(self):
		self._create_gender("Female")
		patient_name = self._create_patient_with_telecom_rows(
			dob="1983-02-04",
			language="en",
			sex="Female",
			telecom_rows=[
				{"type": "phone", "phone_xtty": "+91-9846499464"},
				{"type": "phone", "phone_xtty": "+91-9746409464"},
			],
		)

		self._create_patient_appointment(patient_name, practitioner_name="Dilpreet Saini")

		resource_map = self._build_resource_map()
		compiled = FHIRMappingCompiler(resource_map).compile()

		resolved = FHIRValueResolver(compiled, patient_name).resolve()

		# identifier should be list[dict]
		self.assertIn("Patient.identifier", resolved)
		self.assertIsInstance(resolved["Patient.identifier"], list)
		self.assertEqual(resolved["Patient.identifier"][0]["use"], "usual")
		self.assertEqual(resolved["Patient.identifier"][0]["type"], {"text": "MRN"})
		self.assertEqual(resolved["Patient.identifier"][0]["value"], patient_name)

		# link should be list[dict] (fixed-only)
		self.assertIn("Patient.link", resolved)
		self.assertIsInstance(resolved["Patient.link"], list)
		self.assertEqual(resolved["Patient.link"][0]["type"], "refer")
		self.assertEqual(resolved["Patient.link"][0]["other"], {"display": "something"})

		# telecom should be list[dict] from child table rows
		self.assertIn("Patient.telecom", resolved)
		self.assertIsInstance(resolved["Patient.telecom"], list)
		self.assertEqual(len(resolved["Patient.telecom"]), 2)
		self.assertEqual(resolved["Patient.telecom"][0]["system"], "phone")
		self.assertEqual(resolved["Patient.telecom"][0]["use"], "phone")
		self.assertEqual(resolved["Patient.telecom"][0]["value"], "+91-9846499464")

		# reverse link list -> generalPractitioner (Reference convenience wrapper expected)
		self.assertIn("Patient.generalPractitioner", resolved)
		self.assertIsInstance(resolved["Patient.generalPractitioner"], list)
		self.assertTrue(any(x.get("display") == "Dilpreet Saini" for x in resolved["Patient.generalPractitioner"]))

	def test_resolver_enforces_required_child_in_child_table_rows(self):
		self._create_gender("Female")
		# telecom.value has min=1 in the mapping, so missing phone_xtty should throw
		patient_name = self._create_patient_with_telecom_rows(
			dob="1983-02-04",
			language="en",
			sex="Female",
			telecom_rows=[
				{"type": "phone", "phone_xtty": None},  # missing required value
			],
		)

		resource_map = self._build_resource_map()
		compiled = FHIRMappingCompiler(resource_map).compile()

		with self.assertRaises(FHIRValueResolutionError):
			FHIRValueResolver(compiled, patient_name).resolve()

	# =========================================================
	# Resource Map for tests (no dependency on FHIR Resource Map doctype)
	# =========================================================

	def _build_resource_map(self):
		# Minimal object that matches your compiler expectations: attribute access + .get()
		return frappe._dict(
			resource_type="Patient",
			primary_doctype="Test Patient",
			base_structure_definition="Patient-4.0.1",
			sources=[
				{
					"source_key": "gender",
					"kind": "direct_link",
					"source_doctype": "Test Gender",
					"link_fieldname": "sex",
					"filters_json": "{}",
					"order_by": "creation desc",
				},
				{
					"source_key": "pa",
					"kind": "reverse_link",
					"source_doctype": "Test Patient Appointment",
					"link_fieldname": "patient",
					"filters_json": "{}",
					"order_by": "creation desc",
				},
			],
			profiles=[{"url": "https://www.nrces.in/ndhm/fhir/r4/index.html"}],
			element_maps=[
				# basics
				self._row("Patient.birthDate", {"kind": "field", "source_key": "primary", "fieldname": "dob"}, "date", 0, "1"),
				self._row("Patient.language", {"kind": "field", "source_key": "primary", "fieldname": "language"}, "code", 0, "1"),
				self._row("Patient.deceasedBoolean", {"kind": "fixed", "value": "False"}, "boolean", 0, "1", is_choice_type=1),
				self._row("Patient.multipleBirthBoolean", {"kind": "fixed", "value": False}, "boolean,integer", 0, "1", is_choice_type=1),

				# direct link
				self._row("Patient.gender", {"kind": "field", "source_key": "gender", "fieldname": "name"}, "code", 0, "1", binding_strength="required"),

				# reverse link list -> list[Reference]
				self._row("Patient.generalPractitioner", {"kind": "field", "source_key": "pa", "fieldname": "practitioner_name"}, "Reference", 0, "*"),

				# identifier leafs (should collapse to Patient.identifier)
				self._row("Patient.identifier.type", {"kind": "fixed", "value": "MRN"}, "CodeableConcept", 1, "1", binding_strength="extensible"),
				self._row("Patient.identifier.use", {"kind": "fixed", "value": "usual"}, "code", 0, "1", binding_strength="required"),
				self._row("Patient.identifier.value", {"kind": "field", "source_key": "primary", "fieldname": "name"}, "string", 1, "1"),

				# link leafs (fixed-only => safe collapse)
				self._row("Patient.link.other", {"kind": "fixed", "value": {"display": "something"}}, "Reference", 1, "1"),
				self._row("Patient.link.type", {"kind": "fixed", "value": "refer"}, "code", 1, "1", binding_strength="required"),

				# telecom leafs from child table (should collapse to child_table_rows)
				self._row("Patient.telecom.system", {"kind": "field", "source_key": "primary", "fieldname": "custom_telecom.type"}, "code", 0, "1", binding_strength="required"),
				self._row("Patient.telecom.use", {"kind": "field", "source_key": "primary", "fieldname": "custom_telecom.type"}, "code", 0, "1", binding_strength="required"),
				self._row("Patient.telecom.value", {"kind": "field", "source_key": "primary", "fieldname": "custom_telecom.phone_xtty"}, "string", 1, "1"),
			],
		)

	def _row(self, fhir_path, pointer, datatype, min_value, max_value, binding_strength="", is_choice_type=0):
		return {
			"fhir_path": fhir_path,
			"value_pointer": pointer,
			"datatype": datatype,
			"min": min_value,
			"max": max_value,
			"regex": None,
			"binding_strength": binding_strength,
			"is_choice_type": is_choice_type,
			"valueset_url": "",
			"profile": "",
			"target_profiles": [],
		}

	# =========================================================
	# Test data helpers
	# =========================================================

	def _create_gender(self, name):
		if frappe.db.exists("Test Gender", name):
			return name
		doc = frappe.get_doc({"doctype": "Test Gender", "gender_name": name})
		doc.insert(ignore_permissions=True)
		return doc.name

	def _create_patient_with_telecom_rows(self, dob, language, sex, telecom_rows):
		doc = frappe.get_doc(
			{
				"doctype": "Test Patient",
				"dob": dob,
				"language": language,
				"sex": sex,
				"custom_telecom": telecom_rows or [],
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _create_patient_appointment(self, patient_name, practitioner_name):
		doc = frappe.get_doc(
			{
				"doctype": "Test Patient Appointment",
				"patient": patient_name,
				"practitioner_name": practitioner_name,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _cleanup_test_records(self):
		for doctype in ("Test Patient Appointment", "Test Patient", "Test Gender"):
			frappe.db.delete(doctype)
		frappe.db.commit()

	# =========================================================
	# DocType bootstrap (no MagicMock, real DB doctypes)
	# =========================================================

	@classmethod
	def _ensure_test_doctypes(cls):
		# Child table doctype
		cls._ensure_doctype(
			name="Test Patient Telecom",
			istable=1,
			fields=[
				{"fieldname": "type", "fieldtype": "Data", "label": "Type"},
				{"fieldname": "phone_xtty", "fieldtype": "Data", "label": "Phone"},
			],
		)

		# Gender doctype
		cls._ensure_doctype(
			name="Test Gender",
			istable=0,
			fields=[
				{"fieldname": "gender_name", "fieldtype": "Data", "label": "Gender Name", "reqd": 1},
			],
			autoname="field:gender_name",
		)

		# Appointment doctype (reverse link)
		# IMPORTANT: patient is Data (not Link) to avoid DocType validation issues in test env
		cls._ensure_doctype(
			name="Test Patient Appointment",
			istable=0,
			fields=[
				{"fieldname": "patient", "fieldtype": "Data", "label": "Patient", "reqd": 1},
				{"fieldname": "practitioner_name", "fieldtype": "Data", "label": "Practitioner Name"},
			],
		)

		# Patient doctype (primary)
		cls._ensure_doctype(
			name="Test Patient",
			istable=0,
			fields=[
				{"fieldname": "dob", "fieldtype": "Date", "label": "DOB"},
				{"fieldname": "language", "fieldtype": "Data", "label": "Language"},
				{"fieldname": "sex", "fieldtype": "Link", "label": "Sex", "options": "Test Gender"},
				{"fieldname": "custom_telecom", "fieldtype": "Table", "label": "Custom Telecom", "options": "Test Patient Telecom"},
			],
		)

		frappe.db.commit()


	@classmethod
	def _cleanup_test_doctypes(cls):
		# Delete in dependency order
		for name in ("Test Patient Appointment", "Test Patient", "Test Gender", "Test Patient Telecom"):
			if frappe.db.exists("DocType", name):
				frappe.delete_doc("DocType", name, ignore_permissions=True, force=True)

		frappe.db.commit()

	@classmethod
	def _ensure_doctype(cls, name, istable, fields, autoname=None):
		if frappe.db.exists("DocType", name):
			return

		doc = frappe.get_doc(
			{
				"doctype": "DocType",
				"name": name,
				"module": "Custom",
				"custom": 1,
				"istable": 1 if istable else 0,
				"is_submittable": 0,
				"autoname": autoname or "hash",
				"fields": fields,
				"permissions": [
					{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
				],
			}
		)
		doc.insert(ignore_permissions=True)
