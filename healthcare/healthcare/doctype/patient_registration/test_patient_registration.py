# Copyright (c) 2026, ESS LLP and Contributors
# See license.txt

import frappe
from frappe.utils import add_days, getdate

from healthcare.healthcare.doctype.patient_registration.patient_registration import (
	create_patient_registration,
	expire_registrations,
)
from healthcare.tests.utils import HealthcareTestSuite


class TestPatientRegistration(HealthcareTestSuite):
	def setUp(self):
		super().setUp()
		frappe.db.sql("""delete from `tabPatient Registration`""")

	def get_patient(self):
		return frappe.get_list("Patient", pluck="name")[0]

	def test_valid_till_from_settings(self):
		frappe.db.set_single_value("Healthcare Settings", "registration_validity", 30)

		registration = create_patient_registration(self.get_patient())

		expected = add_days(getdate(), 30)
		self.assertEqual(getdate(registration.valid_till), getdate(expected))
		self.assertEqual(registration.status, "Active")

	def test_zero_validity_never_expires(self):
		frappe.db.set_single_value("Healthcare Settings", "registration_validity", 0)

		registration = create_patient_registration(self.get_patient())

		self.assertIsNone(registration.valid_till)
		self.assertEqual(registration.status, "Active")

	def test_past_validity_marks_expired(self):
		registration = create_patient_registration(self.get_patient())
		registration.valid_till = add_days(getdate(), -1)
		registration.save(ignore_permissions=True)

		self.assertEqual(registration.status, "Expired")

	def test_scheduler_expires_and_disables_patient(self):
		patient = self.get_patient()
		frappe.db.set_value("Patient", patient, "status", "Active")
		registration = create_patient_registration(patient)
		registration.db_set("valid_till", add_days(getdate(), -1))

		expire_registrations()

		self.assertEqual(frappe.db.get_value("Patient Registration", registration.name, "status"), "Expired")
		self.assertEqual(frappe.db.get_value("Patient", patient, "status"), "Disabled")

	def test_scheduler_keeps_patient_with_active_registration(self):
		frappe.db.set_single_value("Healthcare Settings", "registration_validity", 0)
		patient = self.get_patient()
		frappe.db.set_value("Patient", patient, "status", "Active")
		lapsed = create_patient_registration(patient)
		lapsed.db_set("valid_till", add_days(getdate(), -1))
		create_patient_registration(patient, start_date=getdate())  # never-expiring registration

		expire_registrations()

		self.assertEqual(frappe.db.get_value("Patient", patient, "status"), "Active")
