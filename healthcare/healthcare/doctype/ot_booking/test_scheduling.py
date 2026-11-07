# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, get_datetime, nowdate

from healthcare.healthcare.doctype.ot_booking.scheduling import (
	book_request,
	create_procedures,
	get_open_requests,
	move_booking,
	set_status,
)
from healthcare.healthcare.doctype.ot_booking.test_booking_procedures import create_service_request
from healthcare.healthcare.doctype.ot_booking.test_ot_booking import (
	HOUR,
	create_ot_template,
	create_theatre,
	make_booking,
)
from healthcare.tests.utils import HealthcareTestSuite

DEPARTMENT = "_Test Medical Department"


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
		self.assertEqual(listed[request.name].sex, frappe.db.get_value("Patient", self.patients[0], "sex"))

	def test_a_request_is_in_its_procedures_department(self):
		frappe.db.set_value(
			"Clinical Procedure Template", self.template.name, "medical_department", DEPARTMENT
		)
		request = create_service_request(self.patients[0], self.practitioners[0])
		frappe.db.set_value("Service Request", request.name, "medical_department", None)

		self.assertIn(request.name, [row.name for row in get_open_requests(department=DEPARTMENT)])
		self.assertNotIn(
			request.name, [row.name for row in get_open_requests(department="_Test Other Department")]
		)

	def test_the_pane_shows_the_default_company_when_none_is_given(self):
		request = create_service_request(self.patients[0], self.practitioners[0])
		other_company = frappe.db.get_value("Company", {"name": ["!=", "_Test Company"]})
		# a Company default is stored under its scrubbed key
		saved = frappe.defaults.get_user_default("Company")
		self.addCleanup(frappe.defaults.set_user_default, "company", saved)

		frappe.defaults.set_user_default("company", "_Test Company")
		self.assertIn(request.name, self.open_request_names())
		frappe.defaults.set_user_default("company", other_company)
		self.assertNotIn(request.name, self.open_request_names())

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

		self.assertRaisesRegex(frappe.ValidationError, "Change Reason", self.move, booking, 13)
		self.move(booking, 13, reason="Surgeon delayed")

		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{"reference_name": booking.name, "content": ["like", "%Surgeon delayed%"]},
			)
		)

	def test_a_completed_case_cannot_move(self):
		booking = make_booking(self, self.at(9))
		booking.db_set("status", "Completed", update_modified=False)

		self.assertRaisesRegex(frappe.ValidationError, "cannot be moved", self.move, booking, 13)

	def test_a_tentative_case_is_scheduled(self):
		booking = make_booking(self, self.at(9))

		set_status(booking.name, "Scheduled", str(booking.modified))

		self.assertEqual(frappe.db.get_value("OT Booking", booking.name, "status"), "Scheduled")

	def test_a_status_may_not_skip_ahead(self):
		booking = make_booking(self, self.at(9))

		self.assertRaisesRegex(
			frappe.ValidationError,
			"cannot become",
			set_status,
			booking.name,
			"Completed",
			str(booking.modified),
		)

	def test_a_case_changed_elsewhere_keeps_its_status(self):
		booking = make_booking(self, self.at(9))
		stale = str(booking.modified)
		booking.anaesthesia_type = "General"
		booking.save()

		self.assertRaisesRegex(
			frappe.ValidationError, "changed by someone else", set_status, booking.name, "Scheduled", stale
		)

	def test_procedures_are_created_from_the_board(self):
		booking = make_booking(self, self.at(9))

		created = create_procedures(booking.name)

		self.assertEqual(len(created), 1)
		self.assertEqual(create_procedures(booking.name), [])

	def test_moving_needs_permission(self):
		booking = make_booking(self, self.at(9))
		frappe.set_user("test_user@marleyhealth.io")  # a login with no clinical role
		self.addCleanup(frappe.set_user, "Administrator")

		self.assertRaises(frappe.PermissionError, self.move, booking, 13)
