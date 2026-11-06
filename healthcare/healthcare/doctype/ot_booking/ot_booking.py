# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, getdate

from healthcare.healthcare.doctype.ot_booking.conflict_checker import validate_no_conflicts


class OTBooking(Document):
	def validate(self):
		self.patient_name = frappe.db.get_value("Patient", self.patient, "patient_name")
		self.set_procedure_durations()
		self.set_schedule()
		self.validate_theatre()
		self.validate_procedures()
		self.validate_primary_surgeon()
		validate_no_conflicts(self)

	def set_procedure_durations(self):
		for row in self.procedures:
			if not row.duration:
				row.duration = frappe.db.get_value(
					"Clinical Procedure Template", row.procedure_template, "default_duration"
				)

	def set_schedule(self):
		self.scheduled_date = getdate(self.scheduled_start)
		total_seconds = sum(cint(row.duration) for row in self.procedures)
		self.scheduled_end = add_to_date(self.scheduled_start, seconds=total_seconds)

	def validate_theatre(self):
		if not frappe.db.get_value("Healthcare Service Unit", self.theatre, "is_ot"):
			frappe.throw(_("{0} is not an operation theatre").format(frappe.bold(self.theatre)))

	def validate_procedures(self):
		theatre_type = frappe.db.get_value("Healthcare Service Unit", self.theatre, "service_unit_type")
		for row in self.procedures:
			requires_ot, required_type = frappe.db.get_value(
				"Clinical Procedure Template",
				row.procedure_template,
				["requires_ot", "required_theatre_type"],
			)
			if not requires_ot:
				frappe.throw(
					_("Row {0}: {1} does not require an operation theatre").format(
						row.idx, frappe.bold(row.procedure_template)
					)
				)
			if required_type and required_type != theatre_type:
				frappe.throw(
					_("Row {0}: {1} needs a {2} theatre").format(
						row.idx, frappe.bold(row.procedure_template), frappe.bold(required_type)
					)
				)

	def validate_primary_surgeon(self):
		primary = [member for member in self.team if member.is_primary]
		if len(primary) != 1:
			frappe.throw(_("Mark exactly one team member as the primary surgeon"))
		if primary[0].role != "Surgeon":
			frappe.throw(_("The primary team member must have the role Surgeon"))


def on_doctype_update():
	frappe.db.add_index("OT Booking", ["theatre", "scheduled_date"])
