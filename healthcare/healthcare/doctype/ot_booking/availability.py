# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Refuses a booking on a theatre holiday, or when a team member or the theatre is marked
Unavailable, or a team member is on approved leave (when HRMS is installed). An emergency
is only warned about."""

import frappe
from frappe import _
from frappe.utils import format_date, format_time, getdate

from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday

from healthcare.healthcare.doctype.ot_booking.conflict_checker import INACTIVE_STATUSES, booking_slot
from healthcare.healthcare.doctype.practitioner_availability.practitioner_availability import (
	find_unavailable_blocks,
)


def validate_availability(booking):
	if booking.status in INACTIVE_STATUSES:
		return
	messages = holiday_messages(booking) + blocked_messages(booking) + leave_messages(booking)
	if not messages:
		return
	if booking.priority == "Emergency":
		frappe.msgprint(messages, title=_("Not Available"), indicator="orange", as_list=True)
	else:
		frappe.throw(messages, title=_("Not Available"), as_list=True)


def holiday_messages(booking):
	"""A half-day holiday can still be booked; only full holidays close the theatres"""
	if not is_holiday(theatre_holiday_list(booking.company), booking.scheduled_date):
		return []
	return [_("{0} is a theatre holiday").format(frappe.bold(format_date(booking.scheduled_date)))]


def theatre_holiday_list(company):
	return frappe.db.get_single_value("Healthcare Settings", "ot_holiday_list") or frappe.get_cached_value(
		"Company", company, "default_holiday_list"
	)


def blocked_messages(booking):
	scopes = team_practitioners(booking)
	scopes.append(booking.theatre)
	return [
		_("{0} is unavailable from {1} to {2} on {3} ({4})").format(
			frappe.bold(block.scope),
			format_time(block.start_time),
			format_time(block.end_time),
			format_date(block.start_date),
			block.name,
		)
		for block in find_unavailable_blocks(scopes, *booking_slot(booking))
	]


def leave_messages(booking):
	if "hrms" not in frappe.get_installed_apps():
		return []
	employees = team_employees(booking)
	if not employees:
		return []
	start, end = booking_slot(booking)
	leaves = frappe.get_all(
		"Leave Application",
		fields=["name", "employee"],
		filters={
			"employee": ["in", list(employees)],
			"status": "Approved",
			"docstatus": 1,
			"from_date": ["<=", getdate(end)],
			"to_date": [">=", getdate(start)],
		},
	)
	return [
		_("{0} is on leave ({1})").format(frappe.bold(employees[leave.employee]), leave.name)
		for leave in leaves
	]


def team_practitioners(booking):
	return [member.practitioner for member in booking.team]


def team_employees(booking):
	"""Employee → practitioner, for the team members linked to an Employee"""
	practitioners = frappe.get_all(
		"Healthcare Practitioner",
		fields=["name", "employee"],
		filters={"name": ["in", team_practitioners(booking)], "employee": ["is", "set"]},
	)
	return {practitioner.employee: practitioner.name for practitioner in practitioners}
