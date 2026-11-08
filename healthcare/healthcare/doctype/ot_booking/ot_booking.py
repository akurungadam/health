# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, getdate

from healthcare.healthcare.doctype.ot_booking.availability import validate_availability
from healthcare.healthcare.doctype.ot_booking.booking_procedures import (
	ACTIVE_REQUEST_STATUS,
	create_procedures,
	release_procedures,
	sync_procedures,
	validate_procedures_follow,
	validate_release,
)
from healthcare.healthcare.doctype.ot_booking.conflict_checker import (
	INACTIVE_STATUSES,
	lock_theatre_and_people,
	validate_no_conflicts,
)
from healthcare.healthcare.doctype.ot_booking.day_rules import log_change_reason, validate_day_rules
from healthcare.healthcare.doctype.ot_booking.fasting import is_fasting_confirmed, sync_fasting_task
from healthcare.healthcare.doctype.ot_booking.priority import set_priority
from healthcare.healthcare.doctype.ot_booking.same_patient import warn_other_cases

# the statuses a case may move to next from the OT Scheduler
NEXT_STATUSES = {
	"Tentative": ("Scheduled", "Postponed", "Cancelled"),
	"Scheduled": ("Tentative", "In Progress", "Postponed", "Cancelled"),
	"In Progress": ("Completed",),
}
# every status change a save may make: the scheduler's, a postponed case put back on a day or
# cancelled, and a started case cancelled once its procedures are (validate_release refuses it
# while a row still holds a submitted one). A booking follows its procedures without a save, so
# that is not one of them.
ALLOWED_STATUS_CHANGES = {
	**NEXT_STATUSES,
	"In Progress": ("Completed", "Cancelled"),
	"Postponed": ("Tentative", "Cancelled"),
}
NEW_STATUSES = ("Tentative", "Scheduled")


class OTBooking(Document):
	@property
	def fasting_confirmed(self):
		"""A virtual field, read from the ward's fasting task (fasting.py)"""
		return is_fasting_confirmed(self, [row.procedure_template for row in self.procedures])

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
		self.validate_procedure_links()
		if self.status not in INACTIVE_STATUSES:
			# before the request check, so two bookings of one request (one patient) take turns
			lock_theatre_and_people(self)
		self.validate_service_requests()
		self.validate_inpatient_record()
		self.validate_primary_surgeon()
		validate_day_rules(self)
		validate_release(self)
		validate_procedures_follow(self)
		validate_no_conflicts(self)
		validate_availability(self)

	def on_update(self):
		release_procedures(self)
		sync_procedures(self)
		sync_fasting_task(self)
		log_change_reason(self)
		warn_other_cases(self)

	@frappe.whitelist()
	def create_clinical_procedures(self):
		"""From the saved booking, never from unsaved edits a form sent along with the call"""
		# locked, so two calls at once take turns instead of both making the procedures
		saved = frappe.get_doc(self.doctype, self.name, for_update=True)
		saved.check_permission("write")
		frappe.has_permission("Clinical Procedure", "create", throw=True)
		if saved.status in INACTIVE_STATUSES or saved.status == "Completed":
			frappe.throw(_("Procedures cannot be created for a {0} booking").format(_(saved.status)))
		created = create_procedures(saved)
		self.reload()
		return created

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
		"""A row of no time, or less, would make the case end before it starts; and a case is
		shorter than a day, which the clash checks, the board and the slot finder rely on when they
		look one day back for cases still running"""
		for row in self.procedures:
			if cint(row.duration) <= 0:
				frappe.throw(
					_("Row {0}: the duration of {1} must be greater than zero").format(
						row.idx, frappe.bold(row.procedure_template)
					)
				)
		if sum(cint(row.duration) for row in self.procedures) >= 24 * 60 * 60:
			frappe.throw(_("A case must take less than 24 hours"), title=_("Case Too Long"))

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

	def validate_procedure_links(self):
		"""A row's Clinical Procedure is linked by the server when it makes it for this booking, so a
		save keeps each row's link as stored: none on a new row, never another procedure. A linked
		row describes its procedure, so its procedure and request stay, and it stays in the booking."""
		stored = self.stored_procedure_rows()
		for row in self.procedures:
			before = stored.get(row.name) or frappe._dict()
			if (row.clinical_procedure or None) != (before.clinical_procedure or None):
				self.refuse_row(
					row.idx, _("the Clinical Procedure is linked by the system and cannot be set by hand")
				)
			if before.clinical_procedure and (
				row.procedure_template != before.procedure_template
				or (row.service_request or None) != (before.service_request or None)
			):
				self.refuse_row(row.idx, _("its Clinical Procedure is made, so its procedure cannot change"))
		kept = {row.name for row in self.procedures}
		for name, before in stored.items():
			if before.clinical_procedure and name not in kept:
				self.refuse_row(before.idx, _("its Clinical Procedure is made, so the row cannot be removed"))

	def stored_procedure_rows(self):
		if self.is_new():
			return {}
		rows = frappe.get_all(
			"OT Booking Procedure",
			fields=["name", "idx", "clinical_procedure", "procedure_template", "service_request"],
			filters={"parent": self.name, "parenttype": "OT Booking"},
		)
		return {row.name: row for row in rows}

	def refuse_row(self, idx, reason):
		frappe.throw(_("Row {0}: {1}").format(idx, reason), title=_("Not Allowed"))

	def validate_service_requests(self):
		seen = set()
		stored = self.stored_procedure_rows()
		for row in self.procedures:
			if not row.service_request:
				continue
			if row.service_request != (stored.get(row.name) or frappe._dict()).service_request:
				# newly attached: an order put on hold or revoked since it was picked reserves no time
				validate_open_surgical_request(request_details(row.service_request))
			if row.service_request in seen:
				frappe.throw(
					_("Row {0}: Service Request {1} is already in this booking").format(
						row.idx, frappe.bold(row.service_request)
					)
				)
			seen.add(row.service_request)
			if frappe.db.get_value("Service Request", row.service_request, "patient") != self.patient:
				frappe.throw(
					_("Row {0}: Service Request {1} is for another patient").format(
						row.idx, frappe.bold(row.service_request)
					)
				)
			other_booking = find_active_booking(row.service_request, exclude=self.name, for_update=True)
			if other_booking:
				frappe.throw(
					_("Row {0}: Service Request {1} is already booked in {2}").format(
						row.idx, frappe.bold(row.service_request), frappe.bold(other_booking)
					)
				)

	def validate_inpatient_record(self):
		"""The admission is the patient's own, so its bed and record are theirs"""
		if not self.inpatient_record:
			return
		if frappe.db.get_value("Inpatient Record", self.inpatient_record, "patient") != self.patient:
			frappe.throw(
				_("Inpatient Record {0} is not this patient's admission").format(
					frappe.bold(self.inpatient_record)
				),
				title=_("Another Patient's Admission"),
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


def request_details(service_request):
	fields = ["name", "template_dt", "template_dn", "docstatus", "status"]
	return frappe.db.get_value("Service Request", service_request, fields, as_dict=True)


def template_duration(template):
	return frappe.db.get_value("Clinical Procedure Template", template, "default_duration")


def validate_bookable(request):
	validate_open_surgical_request(request)
	booking = find_active_booking(request.name)
	if booking:
		frappe.throw(
			_("Service Request {0} is already booked in {1}").format(
				frappe.bold(request.name), frappe.bold(booking)
			)
		)


def validate_open_surgical_request(request):
	"""A submitted, active order for a procedure that needs an operation theatre"""
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


def find_active_booking(service_request, exclude=None, for_update=False):
	"""The booking holding a request. A Postponed one still holds it; only a cancel frees it. A
	locking read sees a booking another coordinator saved while this one waited for its locks."""
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
	if for_update:
		query = query.for_update()
	result = query.run()
	return result[0][0] if result else None


def on_doctype_update():
	frappe.db.add_index("OT Booking", ["theatre", "scheduled_date"])
