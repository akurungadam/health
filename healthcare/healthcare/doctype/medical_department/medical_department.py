# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document


class MedicalDepartment(Document):
	def validate(self):
		if self.encounter_doctype:
			if not frappe.db.get_value("DocType", self.encounter_doctype, "is_submittable"):
				frappe.throw("Custom DocType for Encounter should be 'Submittable'")
