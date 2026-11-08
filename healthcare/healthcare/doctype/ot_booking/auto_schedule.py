# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Auto Schedule the Day: the waiting cases of the board's company and department, placed one by
one in the earliest free working-hours gap of one day that fits them, as the slot finder finds
gaps. It takes every STAT, ASAP and Urgent case, and the Routine ones due by that day (their
Expected By on or before it); the rest wait. They go in order of priority, then of Expected By.
An Expected By may be past (an overdue case goes first among the Routine ones), but the day
itself is today or one to come. Each case placed counts as busy for the ones after it.

A plan is a dry run that keeps nothing. Booking books what the plan showed and nothing else: each
placement the user approved, as Tentative, checked by the server on its own. A case no longer
waiting, or a placement that no longer fits, is reported, never swapped for another; a request
that came in after the plan waits for the next one."""

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, today

from healthcare.healthcare.doctype.ot_booking.refusal import refusal_text
from healthcare.healthcare.doctype.ot_booking.same_patient import (
	case_text,
	nearest_first,
	other_cases,
	starts_before,
)
from healthcare.healthcare.doctype.ot_booking.scheduling import (
	get_open_requests,
	get_postponed,
	place_booking,
	place_request,
)
from healthcare.healthcare.doctype.ot_booking.slots import case_to_place, day_candidates, matching_theatres

PRIORITY_RANK = {"STAT": 0, "ASAP": 1, "URGENT": 2}
ROUTINE_RANK = 3
MAX_TRIES = 40


@frappe.whitelist(methods=["POST"])
def plan_day(date: str, company: str | None = None, department: str | None = None) -> dict:
	"""What booking the day would do, keeping nothing"""
	frappe.db.savepoint("plan_day")
	try:
		return schedule_day(getdate(date), company, department)
	finally:
		frappe.db.rollback(save_point="plan_day")


@frappe.whitelist(methods=["POST"])
def book_day(
	date: str,
	company: str | None = None,
	department: str | None = None,
	placements: str | list | None = None,
) -> dict:
	"""Books the placements of a plan: each a case's `name`, `theatre` and `scheduled_start`"""
	day = getdate(date)
	company = check_day(day, company)
	approved = frappe.parse_json(placements) or []
	if not approved:
		frappe.throw(_("Preview the day before booking it"), title=_("Nothing to Book"))
	waiting = {case.name: case for case in waiting_cases(day, company, department)}
	placed, not_placed = [], []
	for placement in approved:
		place = book_placement(frappe._dict(placement), waiting.get(placement.get("name")), day)
		(placed if place.get("start") else not_placed).append(place)
	return {"placed": placed, "not_placed": not_placed}


def book_placement(placement, waiting, day):
	"""The previewed case booked where the preview put it, or why it no longer can be"""
	if not waiting:
		reason = _("It is no longer waiting to be scheduled")
		return {"name": placement.name, "patient_name": placement.patient_name, "reason": reason}
	start = get_datetime(placement.scheduled_start)
	if getdate(start) != day:
		return result(waiting, reason=_("Its previewed time is not on this day"))
	refusal = try_booking(waiting, {"theatre": placement.theatre, "start": start})
	if refusal:
		return result(waiting, reason=refusal)
	return {"name": waiting.name, "patient_name": waiting.patient_name, "start": f"{start:%H:%M}"}


def check_day(day, company):
	"""The company to schedule for, once the user may book and the day is not past"""
	frappe.has_permission("OT Booking", "write", throw=True)
	if day < getdate(today()):
		frappe.throw(_("Only today or a day to come can be scheduled"), title=_("Day Has Passed"))
	return company or frappe.defaults.get_user_default("Company")


def schedule_day(day, company, department):
	company = check_day(day, company)
	placed, not_placed = [], []
	for waiting in waiting_cases(day, company, department):
		place = place_case(waiting, day, company, department)
		(placed if place.get("start") else not_placed).append(place)
	return {"placed": placed, "not_placed": not_placed}


def waiting_cases(day, company, department):
	"""The pane's requests and cases to reschedule that are pressing or due by `day`, in order"""
	requests = [
		as_waiting(row, "request", row.expected_date) for row in get_open_requests(company, department)
	]
	postponed = get_postponed(company, department)
	due = expected_dates(postponed)
	cases = requests + [as_waiting(row, "booking", due.get(row.name)) for row in postponed]
	cases = [case for case in cases if case.rank < ROUTINE_RANK or is_due(case, day)]
	return sorted(cases, key=lambda case: (case.rank, getdate(case.expected_date or "9999-12-31")))


def as_waiting(row, kind, expected_date):
	procedures = [row.procedure] if kind == "request" else row.procedures
	return frappe._dict(
		kind=kind,
		name=row.name,
		modified=row.get("modified"),
		patient=row.patient,
		patient_name=row.patient_name,
		procedures=", ".join(procedures),
		expected_date=expected_date,
		rank=PRIORITY_RANK.get((row.priority_label or "").upper(), ROUTINE_RANK),
	)


def is_due(case, day):
	return bool(case.expected_date) and getdate(case.expected_date) <= day


def expected_dates(bookings):
	"""Each postponed case's Expected By: the earliest of its requests'"""
	if not bookings:
		return {}
	rows = frappe.get_all(
		"OT Booking Procedure",
		fields=["parent", "service_request"],
		filters={"parent": ["in", [booking.name for booking in bookings]], "service_request": ["is", "set"]},
	)
	dates = dict(
		frappe.get_all(
			"Service Request",
			fields=["name", "expected_date"],
			filters={"name": ["in", [row.service_request for row in rows]], "expected_date": ["is", "set"]},
			as_list=True,
		)
	)
	due = {}
	for row in rows:
		if dates.get(row.service_request):
			due[row.parent] = min(filter(None, [due.get(row.parent), dates[row.service_request]]))
	return due


def place_case(waiting, day, company, department):
	"""The case booked at the earliest gap the server accepts that day, or why it could not be;
	nearest the patient's other cases of the day first, so they go back to back"""
	messages = len(frappe.local.message_log)
	try:
		# a request booked meanwhile by someone else is refused here, for this case alone
		others = other_cases(waiting.patient, day)
		theatres, candidates = case_candidates(waiting, day, company, department, others)
	except frappe.ValidationError as error:
		return result(waiting, reason=refusal_text(error, messages))
	reason = _("No free time in a theatre it can use that day")
	for candidate in candidates[:MAX_TRIES]:
		refusal = try_booking(waiting, candidate)
		if not refusal:
			return result(waiting, theatres[candidate["theatre"]], candidate, others=others)
		reason = refusal
	return result(waiting, reason=reason)


def case_candidates(waiting, day, company, department, others):
	service_request = waiting.name if waiting.kind == "request" else None
	case = case_to_place(service_request, waiting.name if waiting.kind == "booking" else None)
	theatres = {theatre.name: theatre for theatre in matching_theatres(case, company, department)}
	candidates = day_candidates(case, company, list(theatres.values()), day, also=starts_before(case, others))
	return theatres, nearest_first(candidates, others)


def try_booking(waiting, candidate):
	"""Books the case at the candidate, or returns why the server refused it and undoes the try.
	It never pushes other cases back: a plan moves only the cases it shows."""
	messages = len(frappe.local.message_log)
	frappe.db.savepoint("auto_schedule_case")
	try:
		params = {"theatre": candidate["theatre"], "start": str(candidate["start"])}
		if waiting.kind == "request":
			place_request(waiting.name, push=False, **params)
		else:
			place_booking(waiting.name, modified=str(waiting.modified), push=False, **params)
	except frappe.ValidationError as error:
		frappe.db.rollback(save_point="auto_schedule_case")
		return refusal_text(error, messages)
	frappe.db.release_savepoint("auto_schedule_case")
	# the board marks a patient's second case itself, so the booking's warning is not repeated
	del frappe.local.message_log[messages:]
	return None


def result(waiting, theatre=None, candidate=None, reason=None, others=()):
	row = {
		"name": waiting.name,
		"patient": waiting.patient,
		"patient_name": waiting.patient_name,
		"procedures": waiting.procedures,
	}
	if candidate:
		start, end = get_datetime(candidate["start"]), get_datetime(candidate["end"])
		row.update(
			{
				"theatre": theatre.name,
				"theatre_label": theatre.label,
				"scheduled_start": str(start),
				"scheduled_end": str(end),
				"start": start.strftime("%H:%M"),
				"end": end.strftime("%H:%M"),
				# the patient's cases already on the day, for the board to mark a second case
				"other_cases": [case_text(case) for case in others],
			}
		)
	else:
		row["reason"] = reason
	return row
