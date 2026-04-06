# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import frappe

from healthcare.tests.utils import HealthcareTestSuite


class TestHealthcareServiceUnitType(HealthcareTestSuite):
	def test_item_creation(self):
		unit_type = frappe.get_doc("Healthcare Service Unit Type", {"service_unit_type": "Inpatient Rooms"})
		self.assertTrue(frappe.db.exists("Item", unit_type.item))

		# check item disabled
		unit_type.disabled = 1
		unit_type.save()
		self.assertEqual(frappe.db.get_value("Item", unit_type.item, "disabled"), 1)
