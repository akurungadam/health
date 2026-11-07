# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, get_datetime, nowdate

from healthcare.healthcare.doctype.ot_booking.test_ot_booking import (
	HOUR,
	create_ot_template,
	create_theatre,
	make_booking,
)
from healthcare.tests.utils import HealthcareTestSuite


class TestProcedureStatus(HealthcareTestSuite):
	def setUp(self):
		self.patients = frappe.get_all("Patient", pluck="name", limit=1)
		self.practitioners = frappe.get_all("Healthcare Practitioner", pluck="name", limit=1)
		self.theatre = create_theatre("_Test OT 1", "_Test General OT")
		self.template = create_ot_template("_Test Procedure - Hernia Repair", duration=HOUR)
		self.second = create_ot_template("_Test Procedure - Mesh Fixation", duration=HOUR // 2)
		test_names = sorted(name for name in dir(self) if name.startswith("test_"))
		self.day = add_days(nowdate(), 1600 + test_names.index(self._testMethodName))

	def booking_with_procedures(self, status="Scheduled"):
		start = get_datetime(f"{self.day} 09:00:00")
		booking = make_booking(self, start, templates=[self.template.name, self.second.name])
		booking.db_set("status", "Scheduled")
		names = booking.create_clinical_procedures()
		booking.db_set("status", status)
		return booking, [submitted(name) for name in names]

	def status(self, booking):
		return frappe.db.get_value("OT Booking", booking.name, "status")

	def test_starting_a_procedure_starts_the_case(self):
		booking, (first, _second) = self.booking_with_procedures()

		first.start_procedure()

		self.assertEqual(self.status(booking), "In Progress")

	def test_the_case_stays_in_progress_until_every_procedure_is_completed(self):
		booking, (first, second) = self.booking_with_procedures()
		first.start_procedure()
		first.complete_procedure()

		self.assertEqual(self.status(booking), "In Progress")

		second.start_procedure()
		second.complete_procedure()

		self.assertEqual(self.status(booking), "Completed")

	def test_a_postponed_case_is_left_alone(self):
		booking, (first, _second) = self.booking_with_procedures(status="Postponed")

		first.start_procedure()

		self.assertEqual(self.status(booking), "Postponed")

	def test_the_case_never_moves_backwards(self):
		booking, (first, _second) = self.booking_with_procedures(status="Completed")

		first.start_procedure()

		self.assertEqual(self.status(booking), "Completed")


def submitted(procedure):
	doc = frappe.get_doc("Clinical Procedure", procedure)
	doc.submit()
	return doc
