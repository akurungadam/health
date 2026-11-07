# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, getdate

from healthcare.healthcare.doctype.ot_booking.availability import validate_availability
from healthcare.healthcare.doctype.ot_booking.booking_procedures import (
	create_procedures,
	release_procedures,
	sync_procedures,
	validate_release,
)
from healthcare.healthcare.doctype.ot_booking.conflict_checker import (
	INACTIVE_STATUSES,
	validate_no_conflicts,
)
from healthcare.healthcare.doctype.ot_booking.day_rules import log_change_reason, validate_day_rules
from healthcare.healthcare.doctype.ot_booking.fasting import sync_fasting_task
from healthcare.healthcare.doctype.ot_booking.priority import set_priority

ACTIVE_REQUEST_STATUS = "active-Request Status"
# the statuses a case may move to next from the OT Scheduler
NEXT_STATUSES = {
	"Tentative": ("Scheduled", "Postponed", "Cancelled"),
	"Scheduled": ("Tentative", "In Progress", "Postponed", "Cancelled"),
	"In Progress": ("Completed",),
}
# every status change a save may make: the scheduler's, and a postponed case put back on a day
# or cancelled. A booking follows its procedures without a save, so that is not one of them.
ALLOWED_STATUS_CHANGES = {**NEXT_STATUSES, "Postponed": ("Tentative", "Cancelled")}
NEW_STATUSES = ("Tentative", "Scheduled")


class OTBooking(Document):
	def validate(self):
		self.patient_name = frappe.db.get_value("Patient", self.patient, "patient_name")
		set_priority(self)
		self.validate_status_change()
		self.set_templates_from_requests()
		self.set_procedure_durations()
		self.validate_durations()
		self.set_schedule()
		self.validate_theatre()
		self.validate_procedures()
		self.validate_service_requests()
		self.validate_primary_surgeon()
		validate_day_rules(self)
		validate_release(self)
		validate_no_conflicts(self)
		validate_availability(self)

	def on_update(self):
		release_procedures(self)
		sync_procedures(self)
		sync_fasting_task(self)
		log_change_reason(self)

	@frappe.whitelist()
	def create_clinical_procedures(self):
		self.check_permission("write")
		frappe.has_permission("Clinical Procedure", "create", throw=True)
		if self.status in INACTIVE_STATUSES or self.status == "Completed":
			frappe.throw(_("Procedures cannot be created for a {0} booking").format(_(self.status)))
		return create_procedures(self)

	def set_templates_from_requests(self):
		"""A row booked from a Service Request performs the procedure that was ordered"""
		for row in self.procedures:
			if row.service_request:
				row.procedure_template = frappe.db.get_value(
					"Service Request", row.service_request, "template_dn"
				)

	def set_procedure_durations(self):
		for row in self.procedures:
			if not row.duration:
				row.duration = template_duration(row.procedure_template)

	def validate_status_change(self):
		before = self.get_doc_before_save()
		if not before:
			if self.status not in NEW_STATUSES:
				frappe.throw(_("A new case cannot be {0}").format(_(self.status)), title=_("Not Allowed"))
		elif self.status != before.status and self.status not in ALLOWED_STATUS_CHANGES.get(
			before.status, ()
		):
			frappe.throw(
				_("A {0} case cannot become {1}").format(_(before.status), _(self.status)),
				title=_("Not Allowed"),
			)

	def validate_durations(self):
		"""A row of no time, or less, would make the case end before it starts"""
		for row in self.procedures:
			if cint(row.duration) <= 0:
				frappe.throw(
					_("Row {0}: the duration of {1} must be greater than zero").format(
						row.idx, frappe.bold(row.procedure_template)
					)
				)

	def set_schedule(self):
		self.scheduled_date = getdate(self.scheduled_start)
		total_seconds = sum(cint(row.duration) for row in self.procedures)
		self.scheduled_end = add_to_date(self.scheduled_start, seconds=total_seconds)

	def validate_theatre(self):
		is_ot, company = frappe.db.get_value("Healthcare Service Unit", self.theatre, ["is_ot", "company"])
		if not is_ot:
			frappe.throw(_("{0} is not an operation theatre").format(frappe.bold(self.theatre)))
		if company != self.company:
			frappe.throw(
				_("Theatre {0} belongs to {1}, not to {2}").format(
					frappe.bold(self.theatre), frappe.bold(company), frappe.bold(self.company)
				)
			)

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

	def validate_service_requests(self):
		for row in self.procedures:
			if not row.service_request:
				continue
			if frappe.db.get_value("Service Request", row.service_request, "patient") != self.patient:
				frappe.throw(
					_("Row {0}: Service Request {1} is for another patient").format(
						row.idx, frappe.bold(row.service_request)
					)
				)
			other_booking = find_active_booking(row.service_request, exclude=self.name)
			if other_booking:
				frappe.throw(
					_("Row {0}: Service Request {1} is already booked in {2}").format(
						row.idx, frappe.bold(row.service_request), frappe.bold(other_booking)
					)
				)

	def validate_primary_surgeon(self):
		primary = [member for member in self.team if member.is_primary]
		if len(primary) != 1:
			frappe.throw(_("Mark exactly one team member as the primary surgeon"))
		if primary[0].role != "Surgeon":
			frappe.throw(_("The primary team member must have the role Surgeon"))


@frappe.whitelist()
def make_ot_booking(service_request: str) -> Document:
	"""A new, unsaved booking for an open surgical Service Request"""
	frappe.has_permission("Service Request", "read", service_request, throw=True)
	frappe.has_permission("OT Booking", "create", throw=True)
	request = frappe.get_doc("Service Request", service_request)
	validate_bookable(request)

	booking = frappe.new_doc("OT Booking")
	booking.update(
		{
			"patient": request.patient,
			"company": request.company,
			"inpatient_record": request.inpatient_record,
			"priority": request.priority,
		}
	)
	booking.append(
		"procedures",
		{
			"procedure_template": request.template_dn,
			"service_request": request.name,
			"duration": template_duration(request.template_dn),
		},
	)
	surgeon = request.referred_to_practitioner or request.practitioner
	booking.append("team", {"practitioner": surgeon, "role": "Surgeon", "is_primary": 1})
	return booking


def template_duration(template):
	return frappe.db.get_value("Clinical Procedure Template", template, "default_duration")


def validate_bookable(request):
	is_surgical = request.template_dt == "Clinical Procedure Template" and frappe.db.get_value(
		"Clinical Procedure Template", request.template_dn, "requires_ot"
	)
	if not is_surgical:
		frappe.throw(
			_("Service Request {0} is not for a procedure that requires an operation theatre").format(
				frappe.bold(request.name)
			)
		)
	if request.docstatus != 1 or request.status != ACTIVE_REQUEST_STATUS:
		frappe.throw(_("Service Request {0} is not active").format(frappe.bold(request.name)))
	booking = find_active_booking(request.name)
	if booking:
		frappe.throw(
			_("Service Request {0} is already booked in {1}").format(
				frappe.bold(request.name), frappe.bold(booking)
			)
		)


def find_active_booking(service_request, exclude=None):
	"""The booking holding a request. A Postponed one still holds it; only a cancel frees it."""
	booking = frappe.qb.DocType("OT Booking")
	row = frappe.qb.DocType("OT Booking Procedure")
	query = (
		frappe.qb.from_(row)
		.join(booking)
		.on(booking.name == row.parent)
		.select(booking.name)
		.where(row.parenttype == "OT Booking")
		.where(row.service_request == service_request)
		.where(booking.status != "Cancelled")
		.where(booking.name != (exclude or ""))
		.limit(1)
	)
	result = query.run()
	return result[0][0] if result else None


def on_doctype_update():
	frappe.db.add_index("OT Booking", ["theatre", "scheduled_date"])
