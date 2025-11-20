# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate, nowtime

from healthcare.healthcare.doctype.medical_department.test_medical_department import (
	create_custom_encounter_doctype,
	delete_department_if_exists,
)
from healthcare.healthcare.doctype.patient_appointment.test_patient_appointment import (
	create_appointment_type,
	create_healthcare_docs,
)
from healthcare.healthcare.doctype.patient_encounter.patient_encounter import PatientEncounter


class TestPatientEncounter(IntegrationTestCase):
	def setUp(self):
		try:
			gender_m = frappe.get_doc({"doctype": "Gender", "gender": "MALE"}).insert()
			gender_f = frappe.get_doc({"doctype": "Gender", "gender": "FEMALE"}).insert()
		except frappe.exceptions.DuplicateEntryError:
			gender_m = frappe.get_doc({"doctype": "Gender", "gender": "MALE"})
			gender_f = frappe.get_doc({"doctype": "Gender", "gender": "FEMALE"})

		self.patient_male = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "John",
				"sex": gender_m.gender,
			}
		).insert()
		self.patient_female = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Curie",
				"sex": gender_f.gender,
			}
		).insert()
		self.practitioner = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "Doc",
				"sex": "MALE",
			}
		).insert()
		try:
			self.care_plan_male = frappe.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - m",
					"gender": gender_m.gender,
				}
			).insert()
			self.care_plan_female = frappe.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - f",
					"gender": gender_f.gender,
				}
			).insert()
		except frappe.exceptions.DuplicateEntryError:
			self.care_plan_male = frappe.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - m",
					"gender": gender_m.gender,
				}
			)
			self.care_plan_female = frappe.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - f",
					"gender": gender_f.gender,
				}
			)

	def tearDown(self):
		frappe.db.sql("DELETE FROM `tabDocType` where name = 'Test Custom Encounter DocType'")
		frappe.db.sql("DELETE FROM `tabMedical Department` where name = '_Test Medical Department'")

	def test_treatment_plan_template_filter(self):
		encounter = frappe.get_doc(
			{
				"doctype": "Patient Encounter",
				"patient": self.patient_male.name,
				"practitioner": self.practitioner.name,
				"appointment_type": create_appointment_type().name,
			}
		).insert()
		plans = PatientEncounter.get_applicable_treatment_plans(encounter.as_dict())
		self.assertEqual(plans[0]["name"], self.care_plan_male.template_name)

		encounter = frappe.get_doc(
			{
				"doctype": "Patient Encounter",
				"patient": self.patient_female.name,
				"practitioner": self.practitioner.name,
				"appointment_type": create_appointment_type().name,
			}
		).insert()
		plans = PatientEncounter.get_applicable_treatment_plans(encounter.as_dict())
		self.assertEqual(plans[0]["name"], self.care_plan_female.template_name)

	def test_encounter_created_on_custom_encounter(self):
		# create enc doctype
		custom_encounter_dt = create_custom_encounter_doctype()

		# create medical department with link
		delete_department_if_exists()
		frappe.get_doc(
			{
				"doctype": "Medical Department",
				"department": "_Test Medical Department",
				"encounter_doctype": custom_encounter_dt.name,
			}
		).insert()

		# should create encounter
		patient, practitioner = create_healthcare_docs()
		encounter = (
			frappe.get_doc(
				{
					"doctype": custom_encounter_dt.name,
					"patient": patient,
					"practitioner": practitioner,
					"encounter_date": nowdate(),
					"encounter_time": nowtime(),
					"appointment_type": create_appointment_type().name,
				}
			)
			.insert()
			.submit()
		)
		self.assertTrue(
			frappe.db.exists(
				{
					"doctype": "Patient Encounter",
					"encounter_doctype": custom_encounter_dt.name,
					"encounter": encounter.name,
				}
			)
		)

	def test_encounter_cannot_cancel_if_custom_encounter(self):
		# create enc doctype
		custom_encounter_dt = create_custom_encounter_doctype()

		# create medical department with link
		delete_department_if_exists()
		frappe.get_doc(
			{
				"doctype": "Medical Department",
				"department": "_Test Medical Department",
				"encounter_doctype": custom_encounter_dt.name,
			}
		).insert()

		# should create encounter
		patient, practitioner = create_healthcare_docs()
		encounter = (
			frappe.get_doc(
				{
					"doctype": custom_encounter_dt.name,
					"patient": patient,
					"practitioner": practitioner,
					"encounter_date": nowdate(),
					"encounter_time": nowtime(),
					"appointment_type": create_appointment_type().name,
				}
			)
			.insert()
			.submit()
		)
		encounter = frappe.get_doc(
			{
				"doctype": "Patient Encounter",
				"encounter_doctype": custom_encounter_dt.name,
				"encounter": encounter.name,
			}
		)

		self.assertRaises(frappe.ValidationError, encounter.cancel)
