# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""What the OT Scheduler page changes: an open surgical request dropped into a theatre
slot becomes a booking, and a booked case dragged elsewhere moves. Both save the
booking, so every booking check still runs."""

import frappe
from frappe import _
from frappe.utils import nowdate

from healthcare.healthcare.doctype.ot_booking.board import add_patient_details
from healthcare.healthcare.doctype.ot_booking.conflict_checker import INACTIVE_STATUSES
from healthcare.healthcare.doctype.ot_booking.ot_booking import (
	ACTIVE_REQUEST_STATUS,
	NEXT_STATUSES,
	make_ot_booking,
)

MOVABLE_STATUSES = ("Tentative", "Scheduled")


@frappe.whitelist()
def get_open_requests(company: str | None = None) -> list:
	"""Active surgical Service Requests with no active booking, oldest first"""
	frappe.has_permission("OT Booking", "read", throw=True)
	durations = surgical_template_durations()
	if not durations:
		return []
	filters = {
		"docstatus": 1,
		"status": ACTIVE_REQUEST_STATUS,
		"template_dt": "Clinical Procedure Template",
		"template_dn": ["in", list(durations)],
	}
	if company:
		filters["company"] = company
	requests = frappe.get_list(
		"Service Request",
		fields=[
			"name",
			"patient",
			"patient_name",
			"practitioner_name",
			"template_dn as procedure",
			"order_date",
		],
		filters=filters,
		order_by="order_date asc, order_time asc",
		limit=0,
	)
	booked = booked_requests([request.name for request in requests])
	open_requests = [request for request in requests if request.name not in booked]
	for request in open_requests:
		request.duration = durations[request.procedure]
	if open_requests:
		add_patient_details(open_requests, nowdate())
	return open_requests


@frappe.whitelist()
def book_request(service_request: str, theatre: str, start: str) -> str:
	booking = make_ot_booking(service_request)
	booking.update({"theatre": theatre, "scheduled_start": start})
	return booking.insert().name


@frappe.whitelist()
def move_booking(name: str, theatre: str, start: str, modified: str, reason: str | None = None) -> str:
	booking = frappe.get_doc("OT Booking", name)
	booking.check_permission("write")
	validate_movable(booking, modified, reason)
	booking.update({"theatre": theatre, "scheduled_start": start})
	if reason:
		booking.change_reason = reason
	return booking.save().name


@frappe.whitelist()
def create_procedures(name: str) -> list:
	"""The booking's Clinical Procedures not yet created, one per procedure row"""
	return frappe.get_doc("OT Booking", name).create_clinical_procedures()


@frappe.whitelist()
def set_status(name: str, status: str, modified: str) -> str:
	booking = frappe.get_doc("OT Booking", name)
	booking.check_permission("write")
	validate_unchanged(booking, modified)
	if status not in NEXT_STATUSES.get(booking.status, ()):
		frappe.throw(
			_("A {0} case cannot become {1}").format(_(booking.status), _(status)), title=_("Not Allowed")
		)
	booking.status = status
	return booking.save().name


def validate_unchanged(booking, modified):
	if str(booking.modified) != modified:
		frappe.throw(
			_("{0} was changed by someone else. Reload the board and try again").format(
				frappe.bold(booking.name)
			),
			title=_("Changed Elsewhere"),
		)


def validate_movable(booking, modified, reason):
	validate_unchanged(booking, modified)
	if booking.status not in MOVABLE_STATUSES:
		frappe.throw(_("A {0} case cannot be moved").format(_(booking.status)), title=_("Not Movable"))
	if booking.status == "Scheduled" and not reason:
		frappe.throw(_("Give a reason to move a Scheduled case"), title=_("Reason Required"))


def surgical_template_durations():
	return dict(
		frappe.get_all(
			"Clinical Procedure Template",
			fields=["name", "default_duration"],
			filters={"requires_ot": 1},
			as_list=True,
		)
	)


def booked_requests(requests):
	if not requests:
		return set()
	booking = frappe.qb.DocType("OT Booking")
	row = frappe.qb.DocType("OT Booking Procedure")
	query = (
		frappe.qb.from_(row)
		.join(booking)
		.on(booking.name == row.parent)
		.select(row.service_request)
		.where(row.parenttype == "OT Booking")
		.where(row.service_request.isin(requests))
		.where(booking.status.notin(INACTIVE_STATUSES))
	)
	return {request for (request,) in query.run()}
