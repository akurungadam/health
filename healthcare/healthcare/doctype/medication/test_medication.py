# Copyright (c) 2020, earthians Health Informatics Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils.make_random import get_random

from healthcare.tests.utils import HealthcareTestSuite


class TestMedication(HealthcareTestSuite):
	def test_create_medication_item(self):
		price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
		medication, item = create_medication("Aspirin", is_billable=True, price_list=price_list)

		self.assertTrue(medication.linked_items[0].item)
		self.assertTrue(frappe.db.exists("Item", "Aspirin"))
		self.assertTrue(frappe.db.exists("Item Price", {"item_code": item, "price_list": price_list}))
		self.assertEqual(
			frappe.db.get_value(
				"Item Price", {"item_code": item, "price_list": price_list}, "price_list_rate"
			),
			25,
		)


def create_medication(medication, is_billable=False, price_list=None):
	"""Testing if Item is auto created if is_billable is True"""
	medication_class = get_random("Medication Class")
	if frappe.db.exists("Medication", medication):
		medication_doc = frappe.get_doc("Medication", medication)
		item = None
		if medication_doc.linked_items and len(medication_doc.linked_items):
			item = medication_doc.linked_items[0].item

		return medication_doc, item

	medication_doc = frappe.new_doc("Medication")
	medication_doc.generic_name = medication
	medication_doc.medication_class = medication_class
	medication_doc.strength = 500
	medication_doc.strength_uom = "Milligram"
	medication_doc.price_list = price_list

	if not frappe.db.exists("Dosage Form", "Tablet"):
		frappe.get_doc({"doctype": "Dosage Form", "dosage_form": "Tablet"}).insert()
	medication_doc.dosage_form = "Tablet"
	medication_doc.append(
		"linked_items",
		{"item_code": medication, "item_group": "Drug", "is_billable": is_billable, "rate": 25},
	)
	medication_doc.save()
	return medication_doc, medication
