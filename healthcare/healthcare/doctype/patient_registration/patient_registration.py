# Copyright (c) 2026, ESS LLP and contributors
# For license information, please see license.txt

import datetime

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class PatientRegistration(Document):
	def validate(self):
		self.update_status()

	def update_status(self):
		if self.status == "Cancelled":
			return
		if self.valid_till and getdate(self.valid_till) < getdate():
			self.status = "Expired"
		else:
			self.status = "Active"


def create_patient_registration(patient, sales_invoice=None, start_date=None):
	start_date = getdate(start_date) if start_date else getdate()

	registration = frappe.new_doc("Patient Registration")
	registration.patient = patient
	registration.sales_invoice = sales_invoice
	registration.start_date = start_date
	registration.valid_till = get_valid_till(start_date)
	registration.save(ignore_permissions=True)

	return registration


def get_valid_till(start_date):
	validity = frappe.db.get_single_value("Healthcare Settings", "registration_validity")
	if not validity:
		return None
	return start_date + datetime.timedelta(days=int(validity))
