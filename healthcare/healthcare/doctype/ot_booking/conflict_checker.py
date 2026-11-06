# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Finds other active bookings that overlap a booking in its theatre, its team or its patient.
The theatre also needs its cleaning time after every case."""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, format_datetime, get_datetime, getdate

INACTIVE_STATUSES = ("Cancelled", "Postponed")


def validate_no_conflicts(booking):
	if booking.status in INACTIVE_STATUSES:
		return
	lock_theatre(booking.theatre)
	for message in find_conflicts(booking):
		frappe.throw(message, title=_("Booking Conflict"))


def lock_theatre(theatre):
	"""Two coordinators booking the same gap wait for each other instead of both succeeding"""
	frappe.db.get_value("Healthcare Service Unit", theatre, "name", for_update=True)


def find_conflicts(booking):
	return theatre_conflicts(booking) + team_conflicts(booking) + patient_conflicts(booking)


def theatre_conflicts(booking):
	table = frappe.qb.DocType("OT Booking")
	cleaning = cleaning_time()
	start, end = booking_slot(booking)
	bookings = overlapping(booking, start - cleaning, end + cleaning).where(table.theatre == booking.theatre)
	return [
		_(
			"Theatre {0} is booked from {1} to {2} ({3}), and needs {4} minutes of cleaning after each case"
		).format(frappe.bold(booking.theatre), *slot_text(other), other.name, cleaning.seconds // 60)
		for other in bookings.run(as_dict=True)
	]


def team_conflicts(booking):
	table = frappe.qb.DocType("OT Booking")
	practitioners = [member.practitioner for member in booking.team]
	if not practitioners:
		return []
	team = frappe.qb.DocType("OT Booking Team")
	bookings = (
		overlapping(booking, *booking_slot(booking))
		.join(team)
		.on(team.parent == table.name)
		.select(team.practitioner, table.theatre)
		.where(team.parenttype == "OT Booking")
		.where(team.practitioner.isin(practitioners))
	)
	return [
		_("{0} is in theatre {1} from {2} to {3} ({4})").format(
			frappe.bold(other.practitioner), other.theatre, *slot_text(other), other.name
		)
		for other in bookings.run(as_dict=True)
	]


def patient_conflicts(booking):
	table = frappe.qb.DocType("OT Booking")
	bookings = overlapping(booking, *booking_slot(booking)).where(table.patient == booking.patient)
	return [
		_("Patient {0} already has a booking from {1} to {2} ({3})").format(
			frappe.bold(booking.patient), *slot_text(other), other.name
		)
		for other in bookings.run(as_dict=True)
	]


def overlapping(booking, start, end):
	"""Other active bookings that start before `end` and end after `start`. The date
	range keeps the query on the (theatre, scheduled_date) index."""
	table = frappe.qb.DocType("OT Booking")
	return (
		frappe.qb.from_(table)
		.select(table.name, table.scheduled_start, table.scheduled_end)
		.where(table.name != (booking.name or ""))
		.where(table.status.notin(INACTIVE_STATUSES))
		.where(table.scheduled_date[add_days(getdate(start), -1) : getdate(end)])
		.where(table.scheduled_start < end)
		.where(table.scheduled_end > start)
	)


def booking_slot(booking):
	return get_datetime(booking.scheduled_start), get_datetime(booking.scheduled_end)


def cleaning_time():
	return timedelta(minutes=cint(frappe.db.get_single_value("Healthcare Settings", "ot_cleaning_minutes")))


def slot_text(other):
	return format_datetime(other.scheduled_start), format_datetime(other.scheduled_end)
