# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Finds other active bookings that overlap a booking in its theatre, its team or its patient.
The theatre also needs its cleaning time after every case. A practitioner allowed to overlap
theatres may be in two at once, never three."""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, format_datetime, get_datetime, getdate

from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import ot_setting

INACTIVE_STATUSES = ("Cancelled", "Postponed")
MAX_OVERLAPPING_THEATRES = 2


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
	others = bookings.run(as_dict=True)
	may_overlap = practitioners_allowed_to_overlap(practitioners)
	crowded = crowded_practitioners(others, may_overlap, *booking_slot(booking))
	return [
		_("{0} is in theatre {1} from {2} to {3} ({4})").format(
			frappe.bold(other.practitioner), other.theatre, *slot_text(other), other.name
		)
		for other in others
		if other.practitioner not in may_overlap or other.practitioner in crowded
	]


def crowded_practitioners(others, may_overlap, start, end):
	"""Those allowed to overlap who, with this case, would be in more theatres at one moment than
	allowed. Only the time this case takes counts: two cases of theirs that overlap each other
	before it starts crowd nothing."""
	return {
		practitioner
		for practitioner in may_overlap
		if most_at_once(
			(max(get_datetime(other.scheduled_start), start), min(get_datetime(other.scheduled_end), end))
			for other in others
			if other.practitioner == practitioner
		)
		+ 1
		> MAX_OVERLAPPING_THEATRES
	}


def most_at_once(slots):
	"""The most of `slots` running at one moment; one ending as another starts is not an overlap"""
	moments = sorted(
		(moment, step) for slot_start, slot_end in slots for moment, step in ((slot_start, 1), (slot_end, -1))
	)
	running = most = 0
	for _moment, step in moments:
		running += step
		most = max(most, running)
	return most


def practitioners_allowed_to_overlap(practitioners):
	return set(
		frappe.get_all(
			"Healthcare Practitioner",
			filters={"name": ["in", practitioners], "allow_overlapping_theatres": 1},
			pluck="name",
		)
	)


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
	return timedelta(minutes=cint(ot_setting("ot_cleaning_minutes")))


def slot_text(other):
	return format_datetime(other.scheduled_start), format_datetime(other.scheduled_end)
