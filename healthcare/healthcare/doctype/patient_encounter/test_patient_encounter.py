# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import frappe

from healthcare.healthcare.doctype.patient_encounter.patient_encounter import PatientEncounter
from healthcare.tests.utils import HealthcareTestSuite


class TestPatientEncounter(HealthcareTestSuite):
	def setUp(self):
		super().setUp()
		gender_m = frappe.get_doc({"doctype": "Gender", "gender": "Male"})
		gender_f = frappe.get_doc({"doctype": "Gender", "gender": "Female"})

		self.patient_male = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "John",
				"sex": gender_m.gender,
				"customer_group": "Individual",
			}
		).insert()
		self.patient_female = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Curie",
				"sex": gender_f.gender,
				"customer_group": "Individual",
			}
		).insert()
		self.practitioner = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "Doc",
				"sex": "Male",
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

	def test_treatment_plan_template_filter(self):
		encounter = frappe.get_doc(
			{
				"doctype": "Patient Encounter",
				"patient": self.patient_male.name,
				"practitioner": self.practitioner.name,
				"appointment_type": "_Test Appointment Type",
			}
		).insert()
		plans = PatientEncounter.get_applicable_treatment_plans(encounter.as_dict())
		self.assertEqual(plans[0]["name"], self.care_plan_male.template_name)

		encounter = frappe.get_doc(
			{
				"doctype": "Patient Encounter",
				"patient": self.patient_female.name,
				"practitioner": self.practitioner.name,
				"appointment_type": "_Test Appointment Type",
			}
		).insert()
		plans = PatientEncounter.get_applicable_treatment_plans(encounter.as_dict())
		self.assertEqual(plans[0]["name"], self.care_plan_female.template_name)
