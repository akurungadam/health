# Copyright (c) 2015, ESS LLP and Contributors
# See license.txt


import frappe
from frappe.utils import add_days, date_diff, nowdate

from erpnext.accounts.doctype.pos_profile.test_pos_profile import make_pos_profile

from healthcare.healthcare.doctype.patient_appointment.test_patient_appointment import (
	create_appointment,
	update_status,
)
from healthcare.healthcare.utils import get_encounters_to_invoice
from healthcare.tests.test_utils import create_encounter
from healthcare.tests.utils import HealthcareTestSuite


class TestFeeValidity(HealthcareTestSuite):
	def setUp(self):
		super().setUp()
		frappe.db.sql("""delete from `tabPatient Appointment`""")
		frappe.db.sql("""delete from `tabPatient Encounter`""")
		frappe.db.sql("""delete from `tabFee Validity`""")
		make_pos_profile()

	def test_fee_validity(self):
		patient = frappe.get_list("Patient", pluck="name")[0]
		practitioner = frappe.get_list("Healthcare Practitioner", pluck="name")[0]
		item = "HLC-SI-001"

		healthcare_settings = frappe.get_single("Healthcare Settings")
		healthcare_settings.enable_free_follow_ups = 1
		healthcare_settings.max_visits = 1
		healthcare_settings.valid_days = 7
		healthcare_settings.show_payment_popup = 1
		healthcare_settings.op_consulting_charge_item = item
		healthcare_settings.save(ignore_permissions=True)

		# For first appointment, invoice is generated. First appointment not considered in fee validity
		appointment = create_appointment(patient, practitioner, nowdate())
		fee_validity = frappe.db.exists(
			"Fee Validity",
			{
				"patient": patient,
				"practitioner": practitioner,
				"reference_dt": "Patient Appointment",
				"reference_dn": appointment.name,
			},
		)
		invoiced = frappe.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 1)
		self.assertTrue(fee_validity)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Active")

		# appointment should not be invoiced as it is within fee validity
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 4))
		invoiced = frappe.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 0)

		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "visited"), 1)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Completed")

		# appointment should be invoiced as it is within fee validity but the max_visits are exceeded, should insert new fee validity
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 5), invoice=1)
		invoiced = frappe.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 1)

		fee_validity = frappe.db.exists(
			"Fee Validity",
			{
				"patient": patient,
				"practitioner": practitioner,
				"reference_dt": "Patient Appointment",
				"reference_dn": appointment.name,
			},
		)
		self.assertTrue(fee_validity)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Active")

		# appointment should be invoiced as it is not within fee validity and insert new fee validity
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 13), invoice=1)
		invoiced = frappe.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 1)

		fee_validity = frappe.db.exists(
			"Fee Validity",
			{
				"patient": patient,
				"practitioner": practitioner,
				"reference_dt": "Patient Appointment",
				"reference_dn": appointment.name,
			},
		)
		self.assertTrue(fee_validity)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Active")

		# For first appointment cancel should cancel fee validity
		update_status(appointment.name, "Cancelled")
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Cancelled")

	def test_practitioner_fee_validity(self):
		patient = frappe.get_list("Patient", pluck="name")[0]
		practitioner = frappe.get_list("Healthcare Practitioner", pluck="name")[0]
		item = "HLC-SI-001"

		healthcare_settings = frappe.get_single("Healthcare Settings")
		healthcare_settings.enable_free_follow_ups = 1
		healthcare_settings.max_visits = 1
		healthcare_settings.valid_days = 7
		healthcare_settings.show_payment_popup = 1
		healthcare_settings.op_consulting_charge_item = item
		healthcare_settings.save(ignore_permissions=True)

		frappe.db.set_value(
			"Healthcare Practitioner",
			practitioner,
			{"enable_free_follow_ups": 1, "max_visits": 2, "valid_days": 5},
		)

		# For first appointment, invoice is generated. First appointment not considered in fee validity
		appointment = create_appointment(patient, practitioner, nowdate())
		fee_validity = frappe.db.exists(
			"Fee Validity",
			{
				"patient": patient,
				"practitioner": practitioner,
				"reference_dt": "Patient Appointment",
				"reference_dn": appointment.name,
			},
		)
		invoiced = frappe.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 1)
		self.assertTrue(fee_validity)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Active")
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "max_visits"), 2)

		start_date, valid_till = frappe.db.get_value(
			"Fee Validity", fee_validity, ["start_date", "valid_till"]
		)
		self.assertEqual(date_diff(valid_till, start_date), 5)

	def test_encounter_billed_when_setting_disabled(self):
		"""Free follow ups must not apply to encounters until explicitly opted in"""
		patient, practitioner = self.enable_free_follow_ups(apply_on_encounters=0)

		first = create_encounter(patient, practitioner, submit=True)
		second = create_encounter(patient, practitioner, submit=True)

		self.assertFalse(
			frappe.db.exists("Fee Validity", {"reference_dt": "Patient Encounter"}),
			"Fee Validity created for an encounter while the setting is disabled",
		)
		for encounter in (first, second):
			self.assertIn(encounter.name, self.encounters_to_invoice(patient))

	def test_fee_validity_for_encounter(self):
		patient, practitioner = self.enable_free_follow_ups()

		# first encounter is billed and starts the validity
		first = create_encounter(patient, practitioner, submit=True)
		fee_validity = frappe.db.exists(
			"Fee Validity", {"reference_dt": "Patient Encounter", "reference_dn": first.name}
		)
		self.assertTrue(fee_validity)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Active")
		self.assertIn(first.name, self.encounters_to_invoice(patient))

		# second encounter is a free follow up, so it is not billed
		second = create_encounter(patient, practitioner, submit=True)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "visited"), 1)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Completed")
		self.assertNotIn(second.name, self.encounters_to_invoice(patient))

		# max visits are used up, so the third encounter is billed and starts a new validity
		third = create_encounter(patient, practitioner, submit=True)
		self.assertIn(third.name, self.encounters_to_invoice(patient))
		self.assertTrue(
			frappe.db.exists(
				"Fee Validity", {"reference_dt": "Patient Encounter", "reference_dn": third.name}
			)
		)

	def test_fee_validity_shared_between_appointment_and_encounter(self):
		patient, practitioner = self.enable_free_follow_ups()

		appointment = create_appointment(patient, practitioner, nowdate())
		fee_validity = frappe.db.exists(
			"Fee Validity", {"reference_dt": "Patient Appointment", "reference_dn": appointment.name}
		)
		self.assertTrue(fee_validity)

		# the walk in encounter consumes the visit the appointment paid for
		encounter = create_encounter(patient, practitioner, submit=True)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "visited"), 1)
		self.assertNotIn(encounter.name, self.encounters_to_invoice(patient))

	def test_encounter_with_appointment_ignored(self):
		"""An encounter booked through an appointment is counted on the appointment only"""
		patient, practitioner = self.enable_free_follow_ups()

		create_appointment(patient, practitioner, nowdate())
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 1))
		fee_validity = frappe.db.get_value(
			"Fee Validity", {"patient": patient, "practitioner": practitioner}, "name"
		)
		visited = frappe.db.get_value("Fee Validity", fee_validity, "visited")

		create_encounter(patient, practitioner, submit=True, appointment=appointment.name)

		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "visited"), visited)

	def test_cancel_encounter_restores_visit(self):
		patient, practitioner = self.enable_free_follow_ups()

		create_encounter(patient, practitioner, submit=True)
		encounter = create_encounter(patient, practitioner, submit=True)
		fee_validity = frappe.db.get_value(
			"Fee Validity", {"patient": patient, "practitioner": practitioner}, "name"
		)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "visited"), 1)

		encounter.cancel()

		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "visited"), 0)
		self.assertFalse(
			frappe.db.exists(
				"Fee Validity Reference",
				{"reference_dt": "Patient Encounter", "reference_dn": encounter.name},
			)
		)

	def enable_free_follow_ups(self, apply_on_encounters=1, max_visits=1, valid_days=7):
		patient = frappe.get_list("Patient", pluck="name")[0]
		practitioner = frappe.get_list("Healthcare Practitioner", pluck="name")[0]

		healthcare_settings = frappe.get_single("Healthcare Settings")
		healthcare_settings.enable_free_follow_ups = 1
		healthcare_settings.apply_free_follow_ups_on_encounters = apply_on_encounters
		healthcare_settings.max_visits = max_visits
		healthcare_settings.valid_days = valid_days
		healthcare_settings.show_payment_popup = 1
		healthcare_settings.op_consulting_charge_item = "HLC-SI-001"
		healthcare_settings.save(ignore_permissions=True)

		return patient, practitioner

	def encounters_to_invoice(self, patient):
		patient = frappe.get_doc("Patient", patient)
		return [
			item["reference_name"]
			for item in get_encounters_to_invoice(patient, "_Test Company")
			if item["reference_type"] == "Patient Encounter"
		]
