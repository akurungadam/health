# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""What the OT Scheduler page changes: an open surgical request dropped into a theatre
slot becomes a booking, and a booked case dragged elsewhere moves. Both save the
booking, so every booking check still runs."""

import frappe
from frappe import _
from frappe.utils import nowdate

from healthcare.healthcare.doctype.ot_booking.board import (
	add_patient_details,
	add_surgeons_and_procedures,
)
from healthcare.healthcare.doctype.ot_booking.booking_procedures import ACTIVE_REQUEST_STATUS
from healthcare.healthcare.doctype.ot_booking.conflict_checker import lock_theatre_and_people
from healthcare.healthcare.doctype.ot_booking.ot_booking import make_ot_booking
from healthcare.healthcare.doctype.ot_booking.priority import add_priority
from healthcare.healthcare.doctype.ot_booking.push import push_following
from healthcare.healthcare.doctype.ot_booking.refusal import refusal_text

MOVABLE_STATUSES = ("Tentative", "Scheduled", "Postponed")


@frappe.whitelist()
def get_open_requests(company: str | None = None, department: str | None = None) -> list:
	"""Active surgical Service Requests with no active booking, oldest first. A request is in a
	department by its own Medical Department, or else by its procedure's. Like the board, it
	shows the user's default company when none is given."""
	frappe.has_permission("OT Booking", "read", throw=True)
	templates = surgical_templates()
	if not templates:
		return []
	filters = {
		"docstatus": 1,
		"status": ACTIVE_REQUEST_STATUS,
		"template_dt": "Clinical Procedure Template",
		"template_dn": ["in", list(templates)],
	}
	company = company or frappe.defaults.get_user_default("Company")
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
			"medical_department",
			"priority",
			"order_date",
			"expected_date",
		],
		filters=filters,
		order_by="order_date asc, order_time asc",
		limit=0,
	)
	booked = booked_requests([request.name for request in requests])
	open_requests = [
		request
		for request in requests
		if request.name not in booked
		and in_department(
			request.medical_department or templates[request.procedure].medical_department, department
		)
	]
	# the most pressing first: the earliest Expected By, then those with none, by order date
	open_requests.sort(key=lambda request: (not request.expected_date, request.expected_date or ""))
	for request in open_requests:
		request.duration = templates[request.procedure].default_duration
		request.theatre_type = templates[request.procedure].required_theatre_type
	add_priority(open_requests)
	if open_requests:
		add_patient_details(open_requests, nowdate())
	return open_requests


@frappe.whitelist()
def get_postponed(company: str | None = None, department: str | None = None) -> list:
	"""Postponed cases waiting for a new day, oldest first. A case is in a department when any
	of its procedures is."""
	filters = {"status": "Postponed"}
	company = company or frappe.defaults.get_user_default("Company")
	if company:
		filters["company"] = company
	bookings = frappe.get_list(
		"OT Booking",
		fields=[
			"name",
			"patient",
			"patient_name",
			"status",
			"priority",
			"scheduled_start",
			"scheduled_end",
			"modified",
		],
		filters=filters,
		order_by="scheduled_start asc",
		limit=0,
	)
	if bookings:
		add_priority(bookings)
		add_surgeons_and_procedures(bookings)
		add_theatre_types(bookings)
		add_patient_details(bookings, nowdate())
	if department and bookings:
		departments = template_departments({name for booking in bookings for name in booking.procedures})
		bookings = [
			booking
			for booking in bookings
			if department in {departments.get(name) for name in booking.procedures}
		]
	return bookings


@frappe.whitelist()
def book_request(service_request: str, theatre: str, start: str, reason: str | None = None) -> str:
	booking = make_ot_booking(service_request)
	booking.update({"theatre": theatre, "scheduled_start": start, "change_reason": reason})
	make_room(booking, reason)
	return booking.insert().name


@frappe.whitelist()
def move_booking(name: str, theatre: str, start: str, modified: str, reason: str | None = None) -> str:
	booking = frappe.get_doc("OT Booking", name)
	booking.check_permission("write")
	validate_movable(booking, modified)
	booking.update({"theatre": theatre, "scheduled_start": start, "change_reason": reason})
	if booking.status == "Postponed":
		booking.status = "Tentative"
	make_room(booking, reason)
	return booking.save().name


@frappe.whitelist()
def create_procedures(name: str) -> list:
	"""The booking's Clinical Procedures not yet created, one per procedure row"""
	return frappe.get_doc("OT Booking", name).create_clinical_procedures()


@frappe.whitelist()
def set_status(name: str, status: str, modified: str, reason: str | None = None) -> str:
	booking = frappe.get_doc("OT Booking", name)
	booking.check_permission("write")
	validate_unchanged(booking, modified)
	booking.update({"status": status, "change_reason": reason})
	return booking.save().name


@frappe.whitelist(methods=["POST"])
def check_drop(method: str, params: str | dict) -> str | None:
	"""Tries a drop without keeping it, so the board asks for a reason only when the drop would
	go through. Returns why it would be refused, or nothing."""
	drops = {"book_request": book_request, "move_booking": move_booking, "set_status": set_status}
	params = frappe.parse_json(params)
	params["reason"] = params.get("reason") or _("Checking the drop")
	messages = len(frappe.local.message_log)
	frappe.db.savepoint("check_drop")
	try:
		drops[method](**params)
	except frappe.ValidationError as error:
		frappe.db.rollback(save_point="check_drop")
		return refusal_text(error, messages)
	frappe.db.rollback(save_point="check_drop")
	frappe.local.message_log = frappe.local.message_log[:messages]
	return None


def make_room(booking, reason):
	"""The case's new slot, then the cases after it pushed back to fit it. While they are pushed,
	a moved case holds its new slot, so each is checked against where the case is going and
	never against the slot it is leaving. It gets its old slot back before its own save, which
	must see the move to check it; any refusal undoes all of it. The locks a save takes come
	first, in the same order, so a booking waiting for this theatre never holds up this case."""
	booking.set_schedule()
	lock_theatre_and_people(booking)
	if booking.is_new():
		return push_following(booking, reason)
	fields = ("theatre", "scheduled_start", "scheduled_end", "scheduled_date")
	leaving = frappe.db.get_value("OT Booking", booking.name, fields, as_dict=True)
	frappe.db.set_value(
		"OT Booking", booking.name, {field: booking.get(field) for field in fields}, update_modified=False
	)
	push_following(booking, reason)
	frappe.db.set_value("OT Booking", booking.name, leaving, update_modified=False)


def validate_unchanged(booking, modified):
	if str(booking.modified) != modified:
		frappe.throw(
			_("{0}'s case was changed by someone else. Reload the board and try again").format(
				frappe.bold(booking.patient_name)
			),
			title=_("Changed Elsewhere"),
		)


def validate_movable(booking, modified):
	validate_unchanged(booking, modified)
	if booking.status not in MOVABLE_STATUSES:
		frappe.throw(_("A {0} case cannot be moved").format(_(booking.status)), title=_("Not Movable"))


def surgical_templates():
	"""Template name → its default duration, medical department and required theatre type, for the
	templates needing an OT"""
	templates = frappe.get_all(
		"Clinical Procedure Template",
		fields=["name", "default_duration", "medical_department", "required_theatre_type"],
		filters={"requires_ot": 1},
	)
	return {template.name: template for template in templates}


def add_theatre_types(bookings):
	"""Each case's theatre type, the one its procedures require, if any"""
	types = dict(
		frappe.get_all(
			"Clinical Procedure Template",
			fields=["name", "required_theatre_type"],
			filters={"name": ["in", list({name for booking in bookings for name in booking.procedures})]},
			as_list=True,
		)
	)
	for booking in bookings:
		booking.theatre_type = ", ".join(sorted({types.get(name) for name in booking.procedures} - {None}))


def template_departments(names):
	return dict(
		frappe.get_all(
			"Clinical Procedure Template",
			fields=["name", "medical_department"],
			filters={"name": ["in", list(names)]},
			as_list=True,
		)
	)


def in_department(own_department, department):
	return not department or own_department == department


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
		.where(booking.status != "Cancelled")
	)
	return {request for (request,) in query.run()}
