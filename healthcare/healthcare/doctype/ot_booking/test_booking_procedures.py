# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, add_to_date, get_datetime, nowdate, nowtime

from healthcare.healthcare.doctype.ot_booking.ot_booking import make_ot_booking
from healthcare.healthcare.doctype.ot_booking.priority import priority_named
from healthcare.healthcare.doctype.ot_booking.scheduling import book_request, get_open_requests
from healthcare.healthcare.doctype.ot_booking.test_day_rules import create_user
from healthcare.healthcare.doctype.ot_booking.test_ot_booking import (
	HOUR,
	create_ot_template,
	create_theatre,
	make_booking,
)
from healthcare.tests.utils import HealthcareTestSuite


class TestBookingProcedures(HealthcareTestSuite):
	def setUp(self):
		self.patients = frappe.get_all("Patient", pluck="name", limit=2)
		self.practitioners = frappe.get_all("Healthcare Practitioner", pluck="name", limit=3)
		self.theatre = create_theatre("_Test OT 1", "_Test General OT")
		self.other_theatre = create_theatre("_Test OT 2", "_Test General OT")
		self.template = create_ot_template("_Test Procedure - Hernia Repair", duration=HOUR)
		test_names = sorted(name for name in dir(self) if name.startswith("test_"))
		self.day = add_days(nowdate(), 400 + test_names.index(self._testMethodName))

	def at(self, hour):
		return get_datetime(f"{self.day} {hour:02d}:00:00")

	def book_from_request(self, start):
		booking = make_ot_booking(create_service_request(self.patients[0], self.practitioners[0]).name)
		booking.theatre = self.theatre
		booking.scheduled_start = start
		return booking.insert()

	def test_booking_from_a_request_carries_its_patient_procedure_and_surgeon(self):
		request = create_service_request(self.patients[0], self.practitioners[0])

		booking = make_ot_booking(request.name)

		self.assertEqual(booking.patient, self.patients[0])
		self.assertEqual(booking.procedures[0].service_request, request.name)
		self.assertEqual(booking.procedures[0].procedure_template, self.template.name)
		self.assertEqual(booking.procedures[0].duration, HOUR)
		self.assertEqual(
			(booking.team[0].practitioner, booking.team[0].is_primary), (self.practitioners[0], 1)
		)

	def test_the_requests_priority_reaches_the_booking_and_its_procedure(self):
		request = create_service_request(self.patients[0], self.practitioners[0])
		request.db_set("priority", priority_named("STAT"))
		booking = make_ot_booking(request.name)
		booking.update({"theatre": self.theatre, "scheduled_start": self.at(9)})
		booking.insert()

		procedure = frappe.get_doc("Clinical Procedure", booking.create_clinical_procedures()[0])

		self.assertEqual((booking.priority, procedure.priority), (priority_named("STAT"),) * 2)

	def test_a_request_that_needs_no_theatre_cannot_be_booked(self):
		template = create_ot_template("_Test Procedure - Dressing Change", HOUR, requires_ot=0)
		request = create_service_request(self.patients[0], self.practitioners[0], template.name)

		self.assertRaisesRegex(
			frappe.ValidationError, "does not require|not for a procedure", make_ot_booking, request.name
		)

	def test_a_request_is_booked_only_once(self):
		booking = self.book_from_request(self.at(9))
		request = booking.procedures[0].service_request

		self.assertRaisesRegex(frappe.ValidationError, "already booked", make_ot_booking, request)

	def test_a_row_takes_its_procedure_and_duration_from_its_request(self):
		request = create_service_request(self.patients[0], self.practitioners[0])
		booking = make_booking(self, self.at(9))
		booking.procedures[0].procedure_template = None
		booking.procedures[0].duration = None
		booking.procedures[0].service_request = request.name

		booking.save()

		self.assertEqual(booking.procedures[0].procedure_template, self.template.name)
		self.assertEqual(booking.procedures[0].duration, HOUR)

	def test_a_request_cannot_be_in_a_booking_twice(self):
		booking = self.book_from_request(self.at(9))
		booking.append("procedures", {"service_request": booking.procedures[0].service_request})

		self.assertRaisesRegex(frappe.ValidationError, "already in this booking", booking.save)

	def test_a_procedure_keeps_its_booked_duration_when_submitted(self):
		booking = make_booking(self, self.at(9))
		booking.procedures[0].duration = 2 * HOUR
		booking.save()
		procedure = frappe.get_doc("Clinical Procedure", booking.create_clinical_procedures()[0])

		procedure.submit()

		self.assertEqual(get_datetime(procedure.planned_end_datetime), self.at(11))

	def test_a_case_with_a_submitted_procedure_cannot_move(self):
		booking = make_booking(self, self.at(9))
		frappe.get_doc("Clinical Procedure", booking.create_clinical_procedures()[0]).submit()
		booking.reload()
		booking.update({"scheduled_start": self.at(13), "change_reason": "Surgeon delayed"})

		self.assertRaisesRegex(frappe.ValidationError, "cannot move", booking.save)

	def cancel_its_procedure(self, booking):
		procedure = frappe.get_doc("Clinical Procedure", booking.create_clinical_procedures()[0])
		procedure.submit()
		procedure.cancel()
		booking.reload()
		return procedure.name

	def test_a_cancelled_procedure_is_released_and_kept(self):
		booking = make_booking(self, self.at(9))

		procedure = self.cancel_its_procedure(booking)

		self.assertIsNone(booking.procedures[0].clinical_procedure)
		self.assertEqual(
			frappe.db.get_value("Clinical Procedure", procedure, ["docstatus", "ot_booking"]),
			(2, booking.name),
		)

	def test_a_case_whose_procedure_was_cancelled_can_move(self):
		booking = make_booking(self, self.at(9))
		self.cancel_its_procedure(booking)
		booking.scheduled_start = self.at(13)

		booking.save()

		self.assertEqual(get_datetime(booking.scheduled_start), self.at(13))

	def test_a_case_whose_procedure_was_cancelled_can_be_cancelled(self):
		booking = make_booking(self, self.at(9))
		procedure = self.cancel_its_procedure(booking)
		booking.status = "Cancelled"

		booking.save()

		self.assertTrue(frappe.db.exists("Clinical Procedure", procedure))

	def test_a_request_gets_a_new_procedure_after_one_is_cancelled(self):
		booking = self.book_from_request(self.at(9))
		cancelled = self.cancel_its_procedure(booking)

		made = booking.create_clinical_procedures()

		self.assertEqual(len(made), 1)
		self.assertNotEqual(made[0], cancelled)

	def test_a_submitted_procedure_keeps_its_times(self):
		booking = make_booking(self, self.at(9))
		booking.procedures[0].duration = 2 * HOUR
		booking.save()
		frappe.get_doc("Clinical Procedure", booking.create_clinical_procedures()[0]).submit()
		booking.reload()
		booking.procedures[0].duration = HOUR

		self.assertRaisesRegex(frappe.ValidationError, "cannot change its times", booking.save)

	def test_a_procedure_takes_its_theatres_store(self):
		store = self.theatre_store()

		booking = make_booking(self, self.at(9))

		procedure = booking.create_clinical_procedures()[0]
		self.assertEqual(frappe.db.get_value("Clinical Procedure", procedure, "warehouse"), store)

	def test_a_draft_procedure_moved_to_a_theatre_without_a_store_takes_the_companys(self):
		self.theatre_store()
		booking = make_booking(self, self.at(9))
		procedure = booking.create_clinical_procedures()[0]
		booking.reload()

		booking.theatre = self.other_theatre
		booking.save()

		company_store = frappe.db.get_value("Company", booking.company, "default_warehouse")
		self.assertEqual(frappe.db.get_value("Clinical Procedure", procedure, "warehouse"), company_store)

	def theatre_store(self):
		"""A store of the company other than its default, given to the first theatre"""
		default = frappe.db.get_value("Company", "_Test Company", "default_warehouse")
		store = frappe.get_all(
			"Warehouse",
			filters={"company": "_Test Company", "is_group": 0, "name": ["!=", default]},
			pluck="name",
			limit=1,
		)[0]
		frappe.db.set_value("Healthcare Service Unit", self.theatre, "warehouse", store)
		frappe.db.set_value("Healthcare Service Unit", self.other_theatre, "warehouse", None)
		return store

	def test_another_patients_procedure_cannot_be_linked(self):
		other = make_booking(self, self.at(13), patient=1, surgeon=1)
		theirs = other.create_clinical_procedures()[0]
		booking = make_booking(self, self.at(9))
		booking.procedures[0].clinical_procedure = theirs

		self.assertRaisesRegex(frappe.ValidationError, "linked by the system", booking.save)

	def test_a_linked_procedure_cannot_be_swapped(self):
		booking = make_booking(self, self.at(9))
		booking.create_clinical_procedures()
		other = make_booking(self, self.at(13), patient=1, surgeon=1)
		booking.reload()
		booking.procedures[0].clinical_procedure = other.create_clinical_procedures()[0]

		self.assertRaisesRegex(frappe.ValidationError, "linked by the system", booking.save)

	def test_a_linked_row_keeps_its_procedure(self):
		booking = make_booking(self, self.at(9))
		booking.create_clinical_procedures()
		booking.reload()
		booking.procedures[0].procedure_template = create_ot_template("_Test Procedure - Other", HOUR).name

		self.assertRaisesRegex(frappe.ValidationError, "procedure cannot change", booking.save)

	def test_a_linked_row_cannot_be_removed(self):
		booking = make_booking(self, self.at(9))
		booking.create_clinical_procedures()
		booking.reload()
		booking.procedures = []
		booking.append("procedures", {"procedure_template": self.template.name})

		self.assertRaisesRegex(frappe.ValidationError, "cannot be removed", booking.save)

	def test_an_ot_coordinator_alone_can_book_a_request_and_make_its_procedures(self):
		request = create_service_request(self.patients[0], self.practitioners[0])
		frappe.set_user(create_user("_test_ot_coordinator@example.com", "OT Coordinator"))
		self.addCleanup(frappe.set_user, "Administrator")

		self.assertIn(request.name, [row.name for row in get_open_requests(company="_Test Company")])
		booking = frappe.get_doc("OT Booking", book_request(request.name, self.theatre, str(self.at(9))))
		self.assertTrue(booking.create_clinical_procedures())

	def test_a_draft_procedure_follows_a_new_surgeon(self):
		booking = make_booking(self, self.at(9))
		procedure = booking.create_clinical_procedures()[0]
		booking.reload()
		booking.team[0].practitioner = self.practitioners[1]

		booking.save()

		self.assertEqual(
			frappe.db.get_value("Clinical Procedure", procedure, "practitioner"), self.practitioners[1]
		)

	def test_a_submitted_procedure_keeps_its_surgeon(self):
		booking = make_booking(self, self.at(9))
		frappe.get_doc("Clinical Procedure", booking.create_clinical_procedures()[0]).submit()
		booking.reload()
		booking.team[0].practitioner = self.practitioners[1]

		self.assertRaisesRegex(frappe.ValidationError, "cannot change surgeon", booking.save)

	def test_procedures_are_made_from_the_saved_booking(self):
		booking = make_booking(self, self.at(9))
		booking.scheduled_start = self.at(13)  # an edit the form has not saved

		procedure = frappe.get_doc("Clinical Procedure", booking.create_clinical_procedures()[0])

		self.assertEqual(str(procedure.start_time), "9:00:00")

	def test_a_request_is_booked_only_once_even_by_a_second_save(self):
		booking = self.book_from_request(self.at(9))
		request = booking.procedures[0].service_request
		other = make_booking(self, self.at(13))
		other.append("procedures", {"service_request": request})

		self.assertRaisesRegex(frappe.ValidationError, "already booked", other.save)

	def test_a_request_withdrawn_before_the_booking_is_saved_is_refused(self):
		request = create_service_request(self.patients[0], self.practitioners[0])
		booking = make_ot_booking(request.name)
		booking.update({"theatre": self.theatre, "scheduled_start": self.at(9)})
		request.db_set("status", "revoked-Request Status")

		self.assertRaisesRegex(frappe.ValidationError, "is not active", booking.insert)

	def test_a_request_added_to_a_saved_booking_must_be_active(self):
		booking = make_booking(self, self.at(9))
		request = create_service_request(self.patients[0], self.practitioners[0])
		request.db_set("status", "on-hold-Request Status")
		booking.procedures[0].service_request = request.name

		self.assertRaisesRegex(frappe.ValidationError, "is not active", booking.save)

	def test_a_withdrawn_request_makes_no_procedure(self):
		booking = self.book_from_request(self.at(9))
		frappe.db.set_value(
			"Service Request", booking.procedures[0].service_request, "status", "revoked-Request Status"
		)

		self.assertRaisesRegex(frappe.ValidationError, "no longer active", booking.create_clinical_procedures)

	def test_a_request_for_another_patient_is_refused(self):
		request = create_service_request(self.patients[1], self.practitioners[0])
		booking = make_ot_booking(request.name)
		booking.patient = self.patients[0]
		booking.theatre = self.theatre
		booking.scheduled_start = self.at(9)

		self.assertRaisesRegex(frappe.ValidationError, "another patient", booking.insert)

	def test_procedures_follow_each_other_in_the_booked_theatre(self):
		second = create_ot_template("_Test Procedure - Mesh Fixation", duration=HOUR // 2)
		booking = make_booking(self, self.at(9), templates=[self.template.name, second.name])

		created = booking.create_clinical_procedures()

		first, following = (frappe.get_doc("Clinical Procedure", name) for name in created)
		self.assertEqual((first.service_unit, first.ot_booking), (self.theatre, booking.name))
		self.assertEqual(start_of(first), self.at(9))
		self.assertEqual(start_of(following), self.at(10))
		self.assertEqual(get_datetime(following.planned_end_datetime), add_to_date(self.at(10), minutes=30))
		self.assertEqual(following.practitioner, self.practitioners[0])

	def test_a_procedure_from_a_request_links_the_request(self):
		booking = self.book_from_request(self.at(9))

		procedure = frappe.get_doc("Clinical Procedure", booking.create_clinical_procedures()[0])

		self.assertEqual(procedure.service_request, booking.procedures[0].service_request)

	def test_moving_the_booking_moves_its_draft_procedures(self):
		booking = make_booking(self, self.at(9))
		booking.create_clinical_procedures()
		booking.reload()

		booking.theatre = self.other_theatre
		booking.scheduled_start = self.at(13)
		booking.save()

		procedure = frappe.get_doc("Clinical Procedure", booking.procedures[0].clinical_procedure)
		self.assertEqual((procedure.service_unit, start_of(procedure)), (self.other_theatre, self.at(13)))

	def test_no_procedures_for_a_cancelled_booking(self):
		booking = make_booking(self, self.at(9))
		booking.db_set("status", "Cancelled")

		self.assertRaises(frappe.ValidationError, booking.create_clinical_procedures)

	def test_booking_and_creating_procedures_need_permission(self):
		request = create_service_request(self.patients[0], self.practitioners[0])
		booking = make_booking(self, self.at(9))
		frappe.set_user("test_user@marleyhealth.io")  # a login with no clinical role
		self.addCleanup(frappe.set_user, "Administrator")

		self.assertRaises(frappe.PermissionError, make_ot_booking, request.name)
		self.assertRaises(frappe.PermissionError, booking.create_clinical_procedures)


def start_of(procedure):
	return get_datetime(f"{procedure.start_date} {procedure.start_time}")


def create_service_request(patient, practitioner, template="_Test Procedure - Hernia Repair"):
	request = frappe.get_doc(
		{
			"doctype": "Service Request",
			"order_date": nowdate(),
			"order_time": nowtime(),
			"company": "_Test Company",
			"patient": patient,
			"practitioner": practitioner,
			"status": "draft-Request Status",
			"quantity": 1,
			"template_dt": "Clinical Procedure Template",
			"template_dn": template,
		}
	)
	request.insert(ignore_permissions=True)
	request.submit()
	return request
