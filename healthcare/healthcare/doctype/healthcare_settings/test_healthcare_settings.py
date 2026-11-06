# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils import get_time

from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import store_ot_defaults
from healthcare.tests.utils import HealthcareTestSuite

OT_FIELDS = ("ot_cleaning_minutes", "ot_day_start_time", "ot_day_end_time")


class TestHealthcareSettings(HealthcareTestSuite):
	def setUp(self):
		self.saved = {field: frappe.db.get_single_value("Healthcare Settings", field) for field in OT_FIELDS}

	def tearDown(self):
		for field, value in self.saved.items():
			frappe.db.set_single_value("Healthcare Settings", field, value)

	def test_ot_defaults_are_stored_when_never_set(self):
		frappe.db.delete("Singles", {"doctype": "Healthcare Settings", "field": ["in", OT_FIELDS]})
		frappe.db.set_single_value("Healthcare Settings", "ot_day_end_time", "18:00:00")

		store_ot_defaults()

		self.assertEqual(frappe.db.get_single_value("Healthcare Settings", "ot_cleaning_minutes"), 30)
		start = frappe.db.get_single_value("Healthcare Settings", "ot_day_start_time")
		end = frappe.db.get_single_value("Healthcare Settings", "ot_day_end_time")
		self.assertEqual(get_time(start), get_time("08:00:00"))
		self.assertEqual(get_time(end), get_time("18:00:00"))

	def test_zero_cleaning_minutes_is_kept(self):
		frappe.db.set_single_value("Healthcare Settings", "ot_cleaning_minutes", 0)

		store_ot_defaults()

		self.assertEqual(frappe.db.get_single_value("Healthcare Settings", "ot_cleaning_minutes"), 0)
