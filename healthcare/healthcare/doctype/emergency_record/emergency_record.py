# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EmergencyRecord(Document):
	def after_insert(self):
		if self.patient:
			patient_doc = frappe.get_doc("Patient", self.patient)
			if not patient_doc.emergency_record:
				patient_doc.db_set(
					{
						"emergency_record": self.name,
						"triage_level": self.triage_level,
						"triage_color": self.triage_color,
					}
				)
