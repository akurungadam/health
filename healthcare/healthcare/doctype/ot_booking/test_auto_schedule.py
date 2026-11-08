# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, get_datetime, getdate, nowdate

from healthcare.healthcare.doctype.ot_booking.auto_schedule import book_day, plan_day
from healthcare.healthcare.doctype.ot_booking.priority import priority_named
from healthcare.healthcare.doctype.ot_booking.test_availability import create_unavailable_block
from healthcare.healthcare.doctype.ot_booking.test_booking_procedures import create_service_request
from healthcare.healthcare.doctype.ot_booking.test_ot_booking import (
	HOUR,
	create_ot_template,
	create_theatre,
	make_booking,
)
from healthcare.tests.utils import HealthcareTestSuite

DEPARTMENT = "_Test Medical Department"
COMPANY = "_Test Company"


class TestAutoSchedule(HealthcareTestSuite):
	def setUp(self):
		self.patients = frappe.get_all("Patient", pluck="name", limit=3)
		self.practitioners = frappe.get_all("Healthcare Practitioner", pluck="name", limit=3)
		self.theatre = create_theatre("_Test OT 1", "_Test General OT")
		frappe.db.set_value("Healthcare Service Unit", self.theatre, "medical_department", DEPARTMENT)
		other = create_theatre("_Test OT 2", "_Test General OT")
		frappe.db.set_value("Healthcare Service Unit", other, "medical_department", None)
		self.template = create_ot_template("_Test Procedure - Hernia Repair", duration=HOUR)
		frappe.db.set_value(
			"Clinical Procedure Template", self.template.name, "medical_department", DEPARTMENT
		)
		self.use_settings(ot_cleaning_minutes=30, ot_day_start_time="08:00:00", ot_day_end_time="20:00:00")
		self.use_settings(ot_holiday_list=None)
		self.day = add_days(getdate(nowdate()), 1)

	def use_settings(self, **values):
		saved = {field: frappe.db.get_single_value("Healthcare Settings", field) for field in values}
		frappe.db.set_single_value("Healthcare Settings", values)
		self.addCleanup(frappe.db.set_single_value, "Healthcare Settings", saved)

	def at(self, hour, minutes=0):
		return get_datetime(f"{self.day} {hour:02d}:{minutes:02d}:00")

	def waiting(self, patient, priority="Routine", due_in=None):
		request = create_service_request(self.patients[patient], self.practitioners[patient])
		request.db_set({"priority": priority_named(priority), "medical_department": DEPARTMENT})
		if due_in is not None:
			request.db_set("expected_date", add_days(self.day, due_in))
		return request.name

	def plan(self):
		return plan_day(str(self.day), COMPANY, DEPARTMENT)

	def placed(self, plan):
		return [(row["name"], row["start"]) for row in plan["placed"]]

	def test_cases_go_in_order_of_priority(self):
		routine = self.waiting(0, "Routine", due_in=0)
		stat = self.waiting(1, "STAT")

		plan = self.plan()

		self.assertEqual(self.placed(plan)[:2], [(stat, "08:00"), (routine, "09:30")])

	def test_routine_cases_due_sooner_go_first(self):
		later = self.waiting(0, "Routine", due_in=0)
		sooner = self.waiting(1, "Routine", due_in=-2)

		plan = self.plan()

		self.assertEqual([name for name, _start in self.placed(plan)][:2], [sooner, later])

	def test_routine_cases_not_yet_due_wait(self):
		not_due = self.waiting(0, "Routine", due_in=5)
		undated = self.waiting(1, "Routine")

		plan = self.plan()

		listed = [row["name"] for row in plan["placed"] + plan["not_placed"]]
		self.assertNotIn(not_due, listed)
		self.assertNotIn(undated, listed)

	def test_a_case_that_does_not_fit_is_reported(self):
		create_unavailable_block(self.theatre, "Healthcare Service Unit", self.day, "08:00:00", "20:00:00")
		stat = self.waiting(0, "STAT")

		plan = self.plan()

		self.assertIn(stat, [row["name"] for row in plan["not_placed"]])

	def test_a_case_to_reschedule_is_placed_too(self):
		booking = make_booking(self, get_datetime(f"{add_days(self.day, 3)} 09:00:00"), patient=2, surgeon=2)
		booking.db_set({"status": "Postponed", "priority": priority_named("Urgent")})

		plan = self.plan()

		self.assertIn(booking.name, [row["name"] for row in plan["placed"]])

	def test_a_plan_keeps_nothing_and_booking_keeps_what_it_placed(self):
		stat = self.waiting(0, "STAT")
		before = frappe.db.count("OT Booking")

		self.plan()
		self.assertEqual(frappe.db.count("OT Booking"), before)

		book_day(str(self.day), COMPANY, DEPARTMENT)
		booking = frappe.get_doc("OT Booking", {"status": ["!=", "Cancelled"], "patient": self.patients[0]})
		self.assertEqual((booking.status, get_datetime(booking.scheduled_start)), ("Tentative", self.at(8)))
		self.assertEqual(booking.procedures[0].service_request, stat)

	def test_a_day_gone_by_is_not_scheduled(self):
		self.waiting(0, "STAT")

		self.assertRaisesRegex(
			frappe.ValidationError, "today or a day to come", plan_day, str(add_days(nowdate(), -1)), COMPANY
		)

	def test_scheduling_the_day_needs_permission(self):
		frappe.set_user("test_user@marleyhealth.io")  # a login with no clinical role
		self.addCleanup(frappe.set_user, "Administrator")

		self.assertRaises(frappe.PermissionError, self.plan)
