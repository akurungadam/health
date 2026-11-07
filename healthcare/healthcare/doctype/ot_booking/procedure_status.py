# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""A booking moves with its Clinical Procedures: In Progress once one starts, Completed once
every procedure row has one and all are Completed. It never moves backwards, and a Cancelled
or Postponed booking stays as it is. The status is written directly, because a case that has
started must not be stopped by a booking check, such as a block added since it was booked.
The ward's fasting task is still tidied up, since the case no longer needs it."""

import frappe

from healthcare.healthcare.doctype.ot_booking.conflict_checker import INACTIVE_STATUSES
from healthcare.healthcare.doctype.ot_booking.fasting import sync_fasting_task

STATUS_ORDER = ("Tentative", "Scheduled", "In Progress", "Completed")


def lock_booking(procedure):
	"""Taken before the procedure's own row, so two procedures of one case finishing together
	take turns and always lock in the same order"""
	if procedure.ot_booking:
		frappe.db.get_value("OT Booking", procedure.ot_booking, "name", for_update=True)


def follow_procedure(procedure):
	if not procedure.ot_booking:
		return
	booking = frappe.get_doc("OT Booking", procedure.ot_booking)
	status = status_from_procedures(booking)
	if is_forward(booking.status, status):
		booking.db_set("status", status)
		sync_fasting_task(booking)
		booking.notify_update()


def status_from_procedures(booking):
	names = [row.clinical_procedure for row in booking.procedures if row.clinical_procedure]
	# a locking read sees the latest committed status, not this transaction's older snapshot
	statuses = frappe.db.get_values(
		"Clinical Procedure", {"name": ["in", names]}, "status", pluck=True, for_update=True
	)
	if len(names) == len(booking.procedures) and statuses and all(s == "Completed" for s in statuses):
		return "Completed"
	if any(status in ("In Progress", "Completed") for status in statuses):
		return "In Progress"
	return None


def is_forward(current, status):
	if not status or current in INACTIVE_STATUSES:
		return False
	return STATUS_ORDER.index(status) > STATUS_ORDER.index(current)
