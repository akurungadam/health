# Copyright (c) 2026, ESS LLP and Contributors
# See license.txt

import frappe
from frappe.utils import add_days, getdate

from healthcare.healthcare.doctype.patient_registration.patient_registration import (
	create_patient_registration,
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
