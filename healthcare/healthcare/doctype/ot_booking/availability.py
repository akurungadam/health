# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Refuses a booking on a theatre holiday, or when a team member or the theatre is marked
Unavailable, or a team member is on approved leave (when HRMS is installed). A half-day
leave, and anything about an emergency, is only warned about."""

import frappe
from frappe import _
from frappe.utils import format_date, format_time

from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday

from healthcare.healthcare.doctype.healthcare_practitioner.practitioner_leave import (
	find_leaves,
	leave_message,
)
from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import ot_setting
from healthcare.healthcare.doctype.ot_booking.conflict_checker import INACTIVE_STATUSES, booking_slot
from healthcare.healthcare.doctype.ot_booking.priority import is_emergency
from healthcare.healthcare.doctype.practitioner_availability.practitioner_availability import (
	find_unavailable_blocks,
)


def validate_availability(booking):
	if booking.status in INACTIVE_STATUSES:
		return
	leaves = booking_leaves(booking)
	refusals = holiday_messages(booking) + blocked_messages(booking)
	refusals += [leave_message(leave) for leave in leaves if not leave.is_half_day]
	warnings = [leave_message(leave) for leave in leaves if leave.is_half_day]
	if is_emergency(booking.priority):
		warnings = refusals + warnings
	elif refusals:
		frappe.throw(refusals, title=_("Not Available"), as_list=True)
	if warnings:
		frappe.msgprint(warnings, title=_("Not Available"), indicator="orange", as_list=True)


def holiday_messages(booking):
	"""A half-day holiday can still be booked; only full holidays close the theatres"""
	if not is_holiday(theatre_holiday_list(booking.company), booking.scheduled_date):
		return []
	return [_("{0} is a theatre holiday").format(frappe.bold(format_date(booking.scheduled_date)))]


def theatre_holiday_list(company):
	return ot_setting("ot_holiday_list") or frappe.get_cached_value(
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


def booking_leaves(booking):
	start, end = booking_slot(booking)
	return find_leaves(team_practitioners(booking), start, end)


def team_practitioners(booking):
	return [member.practitioner for member in booking.team]
