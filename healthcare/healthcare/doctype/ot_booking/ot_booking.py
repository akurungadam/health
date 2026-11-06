# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class OTBooking(Document):
	def validate(self):
		self.patient_name = frappe.db.get_value("Patient", self.patient, "patient_name")
		self.scheduled_date = getdate(self.scheduled_start)


def on_doctype_update():
	frappe.db.add_index("OT Booking", ["theatre", "scheduled_date"])
