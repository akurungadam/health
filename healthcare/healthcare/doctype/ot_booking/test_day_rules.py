# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, get_datetime, nowdate

from healthcare.healthcare.doctype.ot_booking.priority import priority_named
from healthcare.healthcare.doctype.ot_booking.test_ot_booking import (
	HOUR,
	create_ot_template,
	create_theatre,
	make_booking,
)
from healthcare.tests.utils import HealthcareTestSuite


class TestDayRules(HealthcareTestSuite):
	def setUp(self):
		self.patients = frappe.get_all("Patient", pluck="name", limit=2)
		self.practitioners = frappe.get_all("Healthcare Practitioner", pluck="name", limit=2)
		self.theatre = create_theatre("_Test OT 1", "_Test General OT")
		self.other_theatre = create_theatre("_Test OT 2", "_Test General OT")
		self.template = create_ot_template("_Test Procedure - Hernia Repair", duration=HOUR)
		test_names = sorted(name for name in dir(self) if name.startswith("test_"))
		self.later_day = add_days(nowdate(), 1200 + test_names.index(self._testMethodName))

	def today_at(self, hour):
		return get_datetime(f"{nowdate()} {hour:02d}:00:00")

	def later_at(self, hour):
		return get_datetime(f"{self.later_day} {hour:02d}:00:00")

	def as_coordinator(self):
		frappe.set_user(create_user("_test_ot_coordinator@example.com", "OT Coordinator"))
		self.addCleanup(frappe.set_user, "Administrator")

	def scheduled_booking(self):
		booking = make_booking(self, self.later_at(9))
		booking.db_set("status", "Scheduled")
		booking.reload()
		return booking

	def test_an_elective_case_cannot_be_added_on_its_own_day(self):
		self.as_coordinator()

		self.assertRaisesRegex(
			frappe.ValidationError, "Only an emergency", make_booking, self, self.today_at(19)
		)

	def test_an_asap_case_is_not_an_emergency(self):
		self.as_coordinator()

		self.assertRaisesRegex(
			frappe.ValidationError,
			"Only an emergency",
			make_booking,
			self,
			self.today_at(19),
			priority=priority_named("ASAP"),
		)

	def test_an_emergency_can_be_added_on_its_own_day(self):
		self.as_coordinator()

		make_booking(self, self.today_at(19), priority=priority_named("STAT"))

	def test_an_ot_manager_adds_an_elective_case_on_its_own_day_without_a_reason(self):
		booking = make_booking(self, self.today_at(19))

		self.assertEqual(frappe.db.get_value("OT Booking", booking.name, "status"), "Tentative")

	def test_a_scheduled_case_needs_a_reason_to_move(self):
		booking = self.scheduled_booking()
		booking.scheduled_start = self.later_at(13)

		self.assertRaisesRegex(frappe.ValidationError, "Change Reason", booking.save)

	def test_a_scheduled_case_needs_a_reason_to_be_cancelled(self):
		booking = self.scheduled_booking()
		booking.status = "Cancelled"

		self.assertRaisesRegex(frappe.ValidationError, "Change Reason", booking.save)

	def test_a_reason_goes_to_the_timeline_and_is_emptied(self):
		booking = self.scheduled_booking()
		booking.update({"theatre": self.other_theatre, "change_reason": "Laminar flow unit needed"})

		booking.save()

		self.assertTrue(has_reason_comment(booking.name, "Laminar flow unit needed"))
		self.assertFalse(frappe.db.get_value("OT Booking", booking.name, "change_reason"))

	def test_a_tentative_case_on_its_own_day_moves_without_a_reason(self):
		booking = make_booking(self, self.today_at(19), priority=priority_named("STAT"))
		booking.scheduled_start = self.today_at(20)

		booking.save()

	def test_a_tentative_case_is_cancelled_without_a_reason(self):
		booking = make_booking(self, self.later_at(9))
		booking.status = "Cancelled"

		booking.save()

	def test_a_tentative_case_on_a_later_day_moves_without_a_reason(self):
		booking = make_booking(self, self.later_at(9))
		booking.scheduled_start = self.later_at(13)

		booking.save()

	def test_moving_a_scheduled_case_forward_in_status_needs_no_reason(self):
		booking = self.scheduled_booking()
		booking.status = "In Progress"

		booking.save()


def has_reason_comment(booking, text):
	return bool(frappe.db.exists("Comment", {"reference_name": booking, "content": ["like", f"%{text}%"]}))


def create_user(email, role):
	if not frappe.db.exists("User", email):
		user = frappe.get_doc({"doctype": "User", "email": email, "first_name": role})
		user.insert(ignore_permissions=True)
		user.add_roles(role)
	return email
