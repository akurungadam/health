# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EmergencyRecord(Document):
	_DOCTYPE_NAME = "Emergency Record"

	def validate(self):
		self.set_patient_age()

	def set_patient_age(self):
		if not self.patient:
			return
		age = frappe.get_cached_doc("Patient", self.patient).calculate_age()
		self.patient_age = age.get("age_in_string") if age else None
