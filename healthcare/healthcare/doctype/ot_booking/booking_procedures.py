# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""A booking's Clinical Procedures: one per procedure row, one after the other in the
booked slot, with the draft ones kept in step when the booking moves."""

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, get_time, getdate

from healthcare.healthcare.doctype.clinical_procedure.clinical_procedure import set_stock_items
from healthcare.healthcare.doctype.ot_booking.conflict_checker import INACTIVE_STATUSES
from healthcare.healthcare.doctype.ot_booking.day_rules import is_moved

ACTIVE_REQUEST_STATUS = "active-Request Status"
from healthcare.healthcare.doctype.service_request.service_request import make_clinical_procedure


def create_procedures(booking):
	created = []
	for row, start in rows_with_start(booking):
		if row.clinical_procedure:
			continue
		procedure = new_procedure(booking, row, start)
		procedure.insert()
		row.db_set("clinical_procedure", procedure.name)
		created.append(procedure.name)
	return created


def sync_procedures(booking):
	"""A Clinical Procedure's service unit is set-only-once, so a draft is updated directly"""
	for row, start in rows_with_start(booking):
		if row.clinical_procedure and is_draft(row.clinical_procedure):
			frappe.db.set_value("Clinical Procedure", row.clinical_procedure, schedule(booking, row, start))


def validate_release(booking):
	"""A case being cancelled or postponed gives up its draft procedures; a submitted one stops it"""
	if not is_stopping(booking):
		return
	for row in booking.procedures:
		if row.clinical_procedure and not is_draft(row.clinical_procedure):
			frappe.throw(
				_("Row {0}: Clinical Procedure {1} is already submitted, so this case cannot be {2}").format(
					row.idx, frappe.bold(row.clinical_procedure), _(booking.status)
				),
				title=_("Procedure Started"),
			)


def validate_procedures_follow(booking):
	"""A submitted procedure keeps the theatre and time it was submitted with, so its case cannot
	move until it is cancelled; a draft one follows the case (sync_procedures)"""
	before = booking.get_doc_before_save()
	if not before or booking.status in INACTIVE_STATUSES or not is_moved(booking, before):
		return
	for row in booking.procedures:
		if row.clinical_procedure and not is_draft(row.clinical_procedure):
			frappe.throw(
				_("Row {0}: Clinical Procedure {1} is already submitted, so this case cannot move").format(
					row.idx, frappe.bold(row.clinical_procedure)
				),
				title=_("Procedure Submitted"),
			)


def release_procedures(booking):
	"""Deleted, not kept: a request allows only one draft procedure, and rebooking makes a new one"""
	if not is_stopping(booking):
		return
	for row in booking.procedures:
		if row.clinical_procedure:
			procedure = row.clinical_procedure
			row.db_set("clinical_procedure", None)
			frappe.delete_doc("Clinical Procedure", procedure, ignore_permissions=True)


def is_stopping(booking):
	before = booking.get_doc_before_save()
	return booking.status in INACTIVE_STATUSES and (not before or before.status not in INACTIVE_STATUSES)


def rows_with_start(booking):
	start = get_datetime(booking.scheduled_start)
	for row in booking.procedures:
		yield row, start
		start = add_to_date(start, seconds=cint(row.duration))


def new_procedure(booking, row, start):
	if row.service_request:
		validate_request_active(row)
		procedure = make_clinical_procedure(row.service_request)
	else:
		procedure = procedure_from_template(booking, row.procedure_template)
	procedure.update(schedule(booking, row, start))
	procedure.practitioner = primary_surgeon(booking)
	procedure.ot_booking = booking.name
	procedure.priority = booking.priority
	procedure.inpatient_record = booking.inpatient_record or procedure.inpatient_record
	procedure.patient_name, procedure.patient_sex = frappe.db.get_value(
		"Patient", booking.patient, ["patient_name", "sex"]
	)
	return procedure


def validate_request_active(row):
	"""A request put on hold or revoked since it was booked makes no clinical work"""
	if frappe.db.get_value("Service Request", row.service_request, "status") != ACTIVE_REQUEST_STATUS:
		frappe.throw(
			_("Row {0}: Service Request {1} is no longer active, so no procedure is made for it").format(
				row.idx, frappe.bold(row.service_request)
			),
			title=_("Request Not Active"),
		)


def procedure_from_template(booking, template):
	procedure = frappe.new_doc("Clinical Procedure")
	procedure.procedure_template = template
	procedure.patient = booking.patient
	procedure.company = booking.company
	procedure.consume_stock = frappe.db.get_value("Clinical Procedure Template", template, "consume_stock")
	procedure.warehouse = frappe.db.get_value("Company", booking.company, "default_warehouse")
	if procedure.consume_stock:
		set_stock_items(procedure, template, "Clinical Procedure Template")
	return procedure


def schedule(booking, row, start):
	return {
		"service_unit": booking.theatre,
		"start_date": getdate(start),
		"start_time": get_time(start),
		"planned_end_datetime": add_to_date(start, seconds=cint(row.duration)),
	}


def primary_surgeon(booking):
	return next(member.practitioner for member in booking.team if member.is_primary)


def is_draft(procedure):
	return frappe.db.get_value("Clinical Procedure", procedure, "docstatus") == 0
