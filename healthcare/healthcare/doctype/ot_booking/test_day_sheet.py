# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, get_datetime, nowdate

from healthcare.healthcare.doctype.ot_booking.day_sheet import get_day_sheet
from healthcare.healthcare.doctype.ot_booking.test_ot_booking import (
	HOUR,
	create_ot_template,
	create_theatre,
	make_booking,
)
from healthcare.tests.utils import HealthcareTestSuite

COMPANY = "_Test Company"


class TestDaySheet(HealthcareTestSuite):
	def setUp(self):
		self.patients = frappe.get_all("Patient", pluck="name", limit=3)
		self.practitioners = frappe.get_all("Healthcare Practitioner", pluck="name", limit=3)
		self.theatre = create_theatre("_Test OT 1", "_Test General OT")
		self.other_theatre = create_theatre("_Test OT 2", "_Test General OT")
		self.template = create_ot_template("_Test Procedure - Hernia Repair", duration=HOUR)
		test_names = sorted(name for name in dir(self) if name.startswith("test_"))
		self.day = add_days(nowdate(), 2800 + test_names.index(self._testMethodName))
		self.first = make_booking(self, self.at(9))
		self.second = make_booking(self, self.at(9), theatre=self.other_theatre, patient=1, surgeon=1)

	def at(self, hour):
		return get_datetime(f"{self.day} {hour:02d}:00:00")

	def name_of(self, practitioner):
		return frappe.db.get_value("Healthcare Practitioner", practitioner, "practitioner_name")

	def test_the_sheet_lists_each_theatres_cases(self):
		sheet = get_day_sheet(str(self.day), COMPANY)

		self.assertEqual(sheet.count("<section>"), 2)
		self.assertIn(frappe.utils.escape_html(self.first.patient_name), sheet)

	def test_a_practitioner_filter_keeps_only_their_section(self):
		surgeon = self.name_of(self.practitioners[0])

		sheet = get_day_sheet(str(self.day), COMPANY, mode="practitioner", practitioner=surgeon)

		self.assertEqual(sheet.count("<section>"), 1)
		self.assertIn(frappe.utils.escape_html(surgeon), sheet)

	def test_a_theatre_filter_keeps_only_that_theatre(self):
		sheet = get_day_sheet(str(self.day), COMPANY, theatre=self.other_theatre)

		self.assertEqual(sheet.count("<section>"), 1)

	def test_names_are_escaped(self):
		self.first.db_set("patient_name", "<b>Bold</b>")

		sheet = get_day_sheet(str(self.day), COMPANY)

		self.assertIn("&lt;b&gt;Bold&lt;/b&gt;", sheet)
		self.assertNotIn("<b>Bold</b>", sheet)

	def test_the_sheet_needs_permission(self):
		frappe.set_user("test_user@marleyhealth.io")  # a login with no clinical role
		self.addCleanup(frappe.set_user, "Administrator")

		self.assertRaises(frappe.PermissionError, get_day_sheet, str(self.day), COMPANY)
