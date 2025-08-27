# Copyright (c) 2023, healthcare and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ClinicalNote(Document):
	def validate(self):
		if not self.user:
			self.user = frappe.session.user

		if not self.practitioner:
			self.practitioner = frappe.get_value(
				"Healthcare Practitioner", filters={"user_id": frappe.session.user}, pluck="name"
			)
