# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""A booking's Clinical Procedures: one per procedure row, one after the other in the
booked slot, with the draft ones kept in step when the booking moves."""

import frappe
from frappe.utils import add_to_date, cint, get_datetime, get_time, getdate

from healthcare.healthcare.doctype.clinical_procedure.clinical_procedure import set_stock_items
from healthcare.healthcare.doctype.service_request.service_request import make_clinical_procedure


def create_procedures(booking):
	created = []
	for row, start in rows_with_start(booking):
		if row.clinical_procedure:
			continue
		procedure = new_procedure(booking, row, start)
		procedure.insert()
		# validate sets the planned end from the template; the booking row's duration wins
		procedure.db_set("planned_end_datetime", schedule(booking, row, start)["planned_end_datetime"])
		row.db_set("clinical_procedure", procedure.name)
		created.append(procedure.name)
	return created


def sync_procedures(booking):
	"""A Clinical Procedure's service unit is set-only-once, so a draft is updated directly"""
	for row, start in rows_with_start(booking):
		if row.clinical_procedure and is_draft(row.clinical_procedure):
			frappe.db.set_value("Clinical Procedure", row.clinical_procedure, schedule(booking, row, start))


def rows_with_start(booking):
	start = get_datetime(booking.scheduled_start)
	for row in booking.procedures:
		yield row, start
		start = add_to_date(start, seconds=cint(row.duration))


def new_procedure(booking, row, start):
	if row.service_request:
		procedure = make_clinical_procedure(row.service_request)
	else:
		procedure = procedure_from_template(booking, row.procedure_template)
	procedure.update(schedule(booking, row, start))
	procedure.practitioner = primary_surgeon(booking)
	procedure.ot_booking = booking.name
	procedure.inpatient_record = booking.inpatient_record or procedure.inpatient_record
	procedure.patient_name, procedure.patient_sex = frappe.db.get_value(
		"Patient", booking.patient, ["patient_name", "sex"]
	)
	return procedure


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
