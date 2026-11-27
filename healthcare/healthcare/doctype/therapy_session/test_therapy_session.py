# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import frappe

from healthcare.healthcare.doctype.therapy_session.therapy_session import invoice_therapy_session
from healthcare.tests.factories.encounters import create_therapy_plan, create_therapy_session
from healthcare.tests.utils import HealthcareTestSuite


class TestTherapySession(HealthcareTestSuite):
	def test_invoice_preserves_default_naming_series(self):
		default_series = frappe.new_doc("Sales Invoice").naming_series
		self.assertTrue(default_series)

		plan = create_therapy_plan()
		session = create_therapy_session(plan.patient, "Basic Rehab", plan.name)
		self.assertNotEqual(session.naming_series, default_series)
		session.submit()

		invoice = invoice_therapy_session(session.name)

		self.assertEqual(invoice.naming_series, default_series)

	def test_invoice_copies_practitioner(self):
		plan = create_therapy_plan()
		session = create_therapy_session(plan.patient, "Basic Rehab", plan.name)
		session.practitioner = plan.practitioner
		session.save()
		session.submit()

		invoice = invoice_therapy_session(session.name)

		self.assertTrue(session.practitioner)
		self.assertEqual(invoice.ref_practitioner, session.practitioner)
		self.assertEqual(invoice.docstatus, 0)
		self.assertTrue(invoice.is_new())

	def test_session_inside_another_is_rejected(self):
		plan = self.create_plan_with_session("10:00:00", duration=60)
		with self.assertRaisesRegex(frappe.ValidationError, "overlaps"):
			create_therapy_session(plan.patient, "Basic Rehab", plan.name, 15, start_time="10:15:00")

	def test_session_running_into_another_is_rejected(self):
		plan = self.create_plan_with_session("10:30:00", duration=30)
		with self.assertRaisesRegex(frappe.ValidationError, "overlaps"):
			create_therapy_session(plan.patient, "Basic Rehab", plan.name, 45, start_time="10:00:00")

	def test_session_at_the_same_time_is_rejected(self):
		plan = self.create_plan_with_session("10:00:00", duration=30)
		with self.assertRaisesRegex(frappe.ValidationError, "overlaps"):
			create_therapy_session(plan.patient, "Basic Rehab", plan.name, 10, start_time="10:00:00")

	def test_back_to_back_sessions_are_allowed(self):
		plan = self.create_plan_with_session("10:00:00", duration=30)
		session = create_therapy_session(plan.patient, "Basic Rehab", plan.name, 30, start_time="10:30:00")
		self.assertTrue(session.name)

	def create_plan_with_session(self, start_time, duration):
		plan = create_therapy_plan()
		create_therapy_session(plan.patient, "Basic Rehab", plan.name, duration, start_time=start_time)
		return plan

	def test_exercise_set_from_therapy_type(self):
		plan = create_therapy_plan()
		session = create_therapy_session(plan.patient, "Basic Rehab", plan.name)
		if plan.therapy_plan_details:
			therapy_type = frappe.get_doc("Therapy Type", plan.therapy_plan_details[0].therapy_type)
			self.assertEqual(
				session.exercises[0].exercise_type,
				therapy_type.exercises[0].exercise_type,
			)
