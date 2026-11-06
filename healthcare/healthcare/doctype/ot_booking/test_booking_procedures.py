# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, add_to_date, get_datetime, nowdate, nowtime

from healthcare.healthcare.doctype.ot_booking.ot_booking import make_ot_booking
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

	def test_a_cancelled_booking_frees_its_request(self):
		booking = self.book_from_request(self.at(9))
		booking.db_set("status", "Cancelled")

		make_ot_booking(booking.procedures[0].service_request)

	def test_a_row_takes_its_procedure_and_duration_from_its_request(self):
		request = create_service_request(self.patients[0], self.practitioners[0])
		booking = make_booking(self, self.at(9))
		booking.procedures[0].procedure_template = None
		booking.procedures[0].duration = None
		booking.procedures[0].service_request = request.name

		booking.save()

		self.assertEqual(booking.procedures[0].procedure_template, self.template.name)
		self.assertEqual(booking.procedures[0].duration, HOUR)

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

	def test_procedures_are_created_once(self):
		booking = make_booking(self, self.at(9))
		booking.create_clinical_procedures()
		booking.reload()

		self.assertEqual(booking.create_clinical_procedures(), [])

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
