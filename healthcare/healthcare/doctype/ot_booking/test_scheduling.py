# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, get_datetime, nowdate

from healthcare.healthcare.doctype.ot_booking.scheduling import (
	book_request,
	get_open_requests,
	move_booking,
)
from healthcare.healthcare.doctype.ot_booking.test_booking_procedures import create_service_request
from healthcare.healthcare.doctype.ot_booking.test_ot_booking import (
	HOUR,
	create_ot_template,
	create_theatre,
	make_booking,
)
from healthcare.tests.utils import HealthcareTestSuite


class TestScheduling(HealthcareTestSuite):
	def setUp(self):
		self.patients = frappe.get_all("Patient", pluck="name", limit=2)
		self.practitioners = frappe.get_all("Healthcare Practitioner", pluck="name", limit=2)
		self.theatre = create_theatre("_Test OT 1", "_Test General OT")
		self.other_theatre = create_theatre("_Test OT 2", "_Test General OT")
		self.template = create_ot_template("_Test Procedure - Hernia Repair", duration=HOUR)
		test_names = sorted(name for name in dir(self) if name.startswith("test_"))
		self.day = add_days(nowdate(), 1100 + test_names.index(self._testMethodName))

	def at(self, hour):
		return get_datetime(f"{self.day} {hour:02d}:00:00")

	def open_request_names(self):
		return [request.name for request in get_open_requests()]

	def move(self, booking, hour, theatre=None, reason=None):
		return move_booking(
			booking.name, theatre or self.theatre, str(self.at(hour)), str(booking.modified), reason
		)

	def test_an_open_surgical_request_is_listed_with_its_duration(self):
		request = create_service_request(self.patients[0], self.practitioners[0])

		listed = {row.name: row for row in get_open_requests()}

		self.assertEqual(listed[request.name].duration, HOUR)

	def test_a_booked_request_is_not_listed(self):
		request = create_service_request(self.patients[0], self.practitioners[0])
		book_request(request.name, self.theatre, str(self.at(9)))

		self.assertNotIn(request.name, self.open_request_names())

	def test_a_request_that_needs_no_theatre_is_not_listed(self):
		template = create_ot_template("_Test Procedure - Dressing Change", HOUR, requires_ot=0)
		request = create_service_request(self.patients[0], self.practitioners[0], template.name)

		self.assertNotIn(request.name, self.open_request_names())

	def test_a_dropped_request_is_booked_in_its_theatre_and_time(self):
		request = create_service_request(self.patients[0], self.practitioners[0])

		booking = frappe.get_doc("OT Booking", book_request(request.name, self.theatre, str(self.at(9))))

		self.assertEqual((booking.theatre, get_datetime(booking.scheduled_start)), (self.theatre, self.at(9)))

	def test_a_request_dropped_onto_a_busy_theatre_is_refused(self):
		make_booking(self, self.at(9), patient=1, surgeon=1)
		request = create_service_request(self.patients[0], self.practitioners[0])

		self.assertRaisesRegex(
			frappe.ValidationError, "is booked", book_request, request.name, self.theatre, str(self.at(9))
		)

	def test_a_tentative_case_moves_to_another_theatre_and_time(self):
		booking = make_booking(self, self.at(9))

		self.move(booking, 13, theatre=self.other_theatre)

		booking.reload()
		self.assertEqual(
			(booking.theatre, get_datetime(booking.scheduled_start)), (self.other_theatre, self.at(13))
		)

	def test_a_case_changed_elsewhere_is_not_moved(self):
		booking = make_booking(self, self.at(9))
		stale = frappe.get_doc("OT Booking", booking.name)
		booking.anaesthesia_type = "General"
		booking.save()

		self.assertRaisesRegex(frappe.ValidationError, "changed by someone else", self.move, stale, 13)

	def test_a_scheduled_case_needs_a_reason_to_move(self):
		booking = make_booking(self, self.at(9))
		booking.db_set("status", "Scheduled", update_modified=False)

		self.assertRaisesRegex(frappe.ValidationError, "Give a reason", self.move, booking, 13)
		self.move(booking, 13, reason="Surgeon delayed")

		self.assertEqual(frappe.db.get_value("OT Booking", booking.name, "change_reason"), "Surgeon delayed")

	def test_a_completed_case_cannot_move(self):
		booking = make_booking(self, self.at(9))
		booking.db_set("status", "Completed", update_modified=False)

		self.assertRaisesRegex(frappe.ValidationError, "cannot be moved", self.move, booking, 13)

	def test_moving_needs_permission(self):
		booking = make_booking(self, self.at(9))
		frappe.set_user("test_user@marleyhealth.io")  # a login with no clinical role
		self.addCleanup(frappe.set_user, "Administrator")

		self.assertRaises(frappe.PermissionError, self.move, booking, 13)
