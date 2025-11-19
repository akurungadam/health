# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


class IntegrationTestMedicalDepartment(IntegrationTestCase):
	def setUp(self):
		pass

	def tearDown(self):
		frappe.db.sql("DELETE FROM `tabDocType` where name = 'Test Custom Encounter DocType'")
		frappe.db.sql("DELETE FROM `tabMedical Department` where name = '_Test Medical Department'")

	def test_fail_if_non_submittable_doctype_linked(self):
		custom_encounter_dt = create_custom_encounter_doctype(False)
		delete_department_if_exists()
		dept = frappe.get_doc(
			{
				"doctype": "Medical Department",
				"department": "_Test Medical Department",
				"encounter_doctype": custom_encounter_dt.name,
			}
		)
		self.assertRaises(frappe.ValidationError, dept.insert)

	def test_pass_if_submittable_doctype_linked(self):
		custom_encounter_dt = create_custom_encounter_doctype(True)
		delete_department_if_exists()
		dept = frappe.get_doc(
			{
				"doctype": "Medical Department",
				"department": "_Test Medical Department",
				"encounter_doctype": custom_encounter_dt.name,
			}
		)
		dept.insert()
		self.assertTrue(frappe.db.exists("Medical Department", dept.name))

	def test_pass_if_no_doctype_linked(self):
		delete_department_if_exists()
		dept = frappe.get_doc(
			{
				"doctype": "Medical Department",
				"department": "_Test Medical Department",
			}
		)
		dept.insert()
		self.assertTrue(frappe.db.exists("Medical Department", dept.name))


def create_custom_encounter_doctype(submittable=True):
	if frappe.db.exists(
		{
			"doctype": "DocType",
			"name": "Test Custom Encounter DocType",
		}
	):
		frappe.db.sql("DELETE FROM `tabDocType` where name = 'Test Custom Encounter DocType'")

	return frappe.get_doc(
		{
			"doctype": "DocType",
			"name": "Test Custom Encounter DocType",
			"module": "Healthcare",
			"custom": 1,
			"is_submittable": submittable,
			"fields": [
				{
					"fieldname": "patient",
					"fieldtype": "Link",
					"options": "Patient",
				},
				{
					"fieldname": "practitioner",
					"fieldtype": "Link",
					"options": "Healthcare Practitioner",
				},
				{
					"fieldname": "appointment_type",
					"fieldtype": "Link",
					"options": "Appointment Type",
				},
				{
					"fieldname": "appointment",
					"fieldtype": "Link",
					"options": "Patient Appointment",
				},
				{
					"fieldname": "encounter_date",
					"fieldtype": "Date",
				},
				{
					"fieldname": "encounter_time",
					"fieldtype": "Time",
				},
				{
					"fieldname": "amended_from",
					"fieldtype": "Link",
					"options": "Test Custom Encounter DocType",
				},
			],
		}
	).insert()


def delete_department_if_exists(encounter_doctype=None):
	if frappe.db.exists(
		{
			"doctype": "Medical Department",
			"name": "_Test Medical Department",
		}
	):
		frappe.db.sql("DELETE FROM `tabMedical Department` where name = '_Test Medical Department'")
