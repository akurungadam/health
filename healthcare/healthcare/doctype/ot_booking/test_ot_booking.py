# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, add_to_date, cint, get_datetime, nowdate

from healthcare.healthcare.doctype.healthcare_service_unit_type.test_healthcare_service_unit_type import (
	create_theatre_type,
)
from healthcare.healthcare.doctype.ot_booking.priority import priority_named
from healthcare.tests.utils import HealthcareTestSuite

HOUR = 3600


class TestOTBooking(HealthcareTestSuite):
	def setUp(self):
		self.patients = frappe.get_all("Patient", pluck="name", limit=3)
		self.practitioners = frappe.get_all("Healthcare Practitioner", pluck="name", limit=3)
		self.theatre = create_theatre("_Test OT 1", "_Test General OT")
		self.other_theatre = create_theatre("_Test OT 2", "_Test General OT")
		self.third_theatre = create_theatre("_Test OT 3", "_Test General OT")
		self.template = create_ot_template("_Test Procedure - Hernia Repair", duration=HOUR)
		# every test books its own day, so the tests in this class never overlap each other
		test_names = sorted(name for name in dir(self) if name.startswith("test_"))
		self.day = add_days(nowdate(), 30 + test_names.index(self._testMethodName))

	def assert_refused(self, message, start, **fields):
		self.assertRaisesRegex(frappe.ValidationError, message, make_booking, self, start, **fields)

	def at(self, hour):
		return get_datetime(f"{self.day} {hour:02d}:00:00")

	def test_schedule_comes_from_the_procedure_durations(self):
		second = create_ot_template("_Test Procedure - Mesh Fixation", duration=HOUR // 2)
		booking = make_booking(self, self.at(9), templates=[self.template.name, second.name])

		self.assertEqual(str(booking.scheduled_date), self.day)
		self.assertEqual(get_datetime(booking.scheduled_end), add_to_date(self.at(9), seconds=HOUR * 1.5))
		self.assertEqual(booking.procedures[1].duration, HOUR // 2)

	def test_a_new_booking_is_routine(self):
		booking = make_booking(self, self.at(9))

		self.assertEqual(booking.priority, priority_named("Routine"))

	def test_a_procedure_must_take_some_time(self):
		booking = frappe.get_doc("OT Booking", make_booking(self, self.at(9)).name)
		booking.procedures[0].duration = -HOUR

		self.assertRaisesRegex(frappe.ValidationError, "greater than zero", booking.save)

	def test_the_theatre_must_belong_to_the_bookings_company(self):
		other_company = frappe.db.get_value("Company", {"name": ["!=", "_Test Company"]})
		frappe.db.set_value("Healthcare Service Unit", self.other_theatre, "company", other_company)

		self.assert_refused("belongs to", self.at(9), theatre=self.other_theatre)

	def test_a_form_save_follows_the_status_rules(self):
		booking = make_booking(self, self.at(9))
		booking.status = "Completed"
		self.assertRaisesRegex(frappe.ValidationError, "cannot become", booking.save)

		booking.reload()
		booking.db_set("status", "Cancelled")
		booking.reload()
		booking.status = "Scheduled"
		self.assertRaisesRegex(frappe.ValidationError, "cannot become", booking.save)

	def test_a_new_case_cannot_start_completed(self):
		booking = frappe.copy_doc(make_booking(self, self.at(9)))
		booking.update({"status": "Completed", "scheduled_start": self.at(13)})

		self.assertRaisesRegex(frappe.ValidationError, "A new case cannot be", booking.insert)

	def test_theatre_must_be_an_ot(self):
		ward = create_theatre("_Test Not An OT", "_Test General Ward", is_ot=0)

		self.assert_refused("is not an operation theatre", self.at(9), theatre=ward)

	def test_theatre_type_must_match_the_procedure(self):
		template = create_ot_template("_Test Procedure - Knee Replacement", HOUR, "_Test Laminar Flow OT")

		self.assert_refused(
			"needs a .*_Test Laminar Flow OT.* theatre", self.at(9), templates=[template.name]
		)

	def test_procedure_must_require_an_ot(self):
		template = create_ot_template("_Test Procedure - Dressing Change", HOUR, requires_ot=0)

		self.assert_refused("does not require an operation theatre", self.at(9), templates=[template.name])

	def test_exactly_one_primary_surgeon(self):
		self.assert_refused("exactly one", self.at(9), primaries=0)
		self.assert_refused("exactly one", self.at(9), primaries=2)

	def test_theatre_overlap_is_refused(self):
		make_booking(self, self.at(9))

		self.assert_refused("Theatre .* is booked", self.at(9), patient=1, surgeon=1)

	def test_cleaning_time_is_kept_between_cases(self):
		make_booking(self, self.at(9))
		cleaning = cint(frappe.db.get_single_value("Healthcare Settings", "ot_cleaning_minutes"))
		right_after = self.at(10)
		after_cleaning = add_to_date(self.at(10), minutes=cleaning)

		self.assert_refused("minutes of cleaning", right_after, patient=1, surgeon=1)
		make_booking(self, after_cleaning, patient=1, surgeon=1)

	def test_surgeon_cannot_be_in_two_theatres_at_once(self):
		make_booking(self, self.at(9))

		self.assert_refused("is in theatre", self.at(9), theatre=self.other_theatre, patient=1)

	def test_surgeon_needs_no_cleaning_gap_between_theatres(self):
		make_booking(self, self.at(9))

		make_booking(self, self.at(10), theatre=self.other_theatre, patient=1)

	def test_a_practitioner_allowed_to_overlap_covers_two_theatres(self):
		self.allow_overlap(self.practitioners[0])
		make_booking(self, self.at(9))

		make_booking(self, self.at(9), theatre=self.other_theatre, patient=1)

	def test_a_practitioner_allowed_to_overlap_never_covers_three(self):
		self.allow_overlap(self.practitioners[0])
		make_booking(self, self.at(9))
		make_booking(self, self.at(9), theatre=self.other_theatre, patient=1)

		self.assert_refused("is in theatre", self.at(9), theatre=self.third_theatre, patient=2)

	def allow_overlap(self, practitioner):
		frappe.db.set_value("Healthcare Practitioner", practitioner, "allow_overlapping_theatres", 1)
		self.addCleanup(
			frappe.db.set_value, "Healthcare Practitioner", practitioner, "allow_overlapping_theatres", 0
		)

	def test_patient_cannot_have_two_overlapping_bookings(self):
		make_booking(self, self.at(9))

		self.assert_refused("already has a booking", self.at(9), theatre=self.other_theatre, surgeon=1)

	def test_cancelled_and_postponed_bookings_do_not_block(self):
		for status in ("Cancelled", "Postponed"):
			booking = make_booking(self, self.at(9))
			booking.db_set("status", status)

		make_booking(self, self.at(9))

	def test_saving_a_booking_again_does_not_conflict_with_itself(self):
		booking = make_booking(self, self.at(9))
		booking.anaesthesia_type = "General"

		booking.save()


def make_booking(
	test,
	start,
	theatre=None,
	templates=None,
	patient=0,
	surgeon=0,
	primaries=1,
	priority=None,
	change_reason=None,
):
	team = [{"practitioner": test.practitioners[surgeon], "role": "Surgeon", "is_primary": primaries >= 1}]
	if primaries >= 2:
		team.append({"practitioner": test.practitioners[2], "role": "Surgeon", "is_primary": 1})
	booking = frappe.get_doc(
		{
			"doctype": "OT Booking",
			"patient": test.patients[patient],
			"company": "_Test Company",
			"theatre": theatre or test.theatre,
			"scheduled_start": start,
			"priority": priority,
			"change_reason": change_reason,
			"procedures": [{"procedure_template": name} for name in templates or [test.template.name]],
			"team": team,
		}
	)
	return booking.insert()


def create_theatre(name, unit_type, is_ot=1):
	unit_name = f"{name} - _TC"
	if frappe.db.exists("Healthcare Service Unit", unit_name):
		return unit_name
	parent = frappe.db.get_value("Healthcare Service Unit", {"company": "_Test Company", "is_group": 1})
	unit = frappe.get_doc(
		{
			"doctype": "Healthcare Service Unit",
			"healthcare_service_unit_name": name,
			"company": "_Test Company",
			"parent_healthcare_service_unit": parent,
			"service_unit_type": create_theatre_type(unit_type, is_ot=is_ot).name,
		}
	)
	return unit.insert().name


def create_ot_template(name, duration, theatre_type=None, requires_ot=1):
	fields = {
		"requires_ot": requires_ot,
		"default_duration": duration,
		"required_theatre_type": theatre_type and create_theatre_type(theatre_type).name,
	}
	if frappe.db.exists("Clinical Procedure Template", name):
		return frappe.get_doc("Clinical Procedure Template", name).update(fields).save()
	return frappe.get_doc(
		{
			"doctype": "Clinical Procedure Template",
			"template": name,
			"item_code": name,
			"item_group": "Services",
			"description": name,
			**fields,
		}
	).insert()
