# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""The slot finder: the earliest free gaps a waiting case fits in, across the theatres the board
shows, over the coming days. A gap holds the case and its cleaning time inside the theatre day,
clear of other cases, theatre blocks, the patient's other cases, the team's other theatres and
blocks, and the surgeon's leave, and never on a full theatre holiday, even for an emergency: one
can still be dropped there. At most one slot per theatre per day, the earliest the server
accepts; those before the case's Expected By come first. It only offers
free gaps and never pushes a case. Every slot it returns has passed the server's own checks in
a dry run (`check_drop`), so booking it meets no refusal the finder could have known about."""

from datetime import datetime, timedelta

import frappe
from frappe.utils import add_days, get_datetime, get_time, getdate, now_datetime, today

from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday

from healthcare.healthcare.doctype.healthcare_practitioner.practitioner_leave import find_leaves
from healthcare.healthcare.doctype.ot_booking.availability import theatre_holiday_list
from healthcare.healthcare.doctype.ot_booking.board import day_window, get_theatres
from healthcare.healthcare.doctype.ot_booking.conflict_checker import (
	INACTIVE_STATUSES,
	cleaning_time,
	practitioners_allowed_to_overlap,
)
from healthcare.healthcare.doctype.ot_booking.ot_booking import make_ot_booking
from healthcare.healthcare.doctype.ot_booking.priority import is_emergency
from healthcare.healthcare.doctype.ot_booking.scheduling import check_drop
from healthcare.healthcare.doctype.practitioner_availability.practitioner_availability import (
	find_unavailable_blocks,
)

GRID = timedelta(minutes=15)
MAX_CHECKS = 40


@frappe.whitelist()
def find_slots(
	service_request: str | None = None,
	booking: str | None = None,
	company: str | None = None,
	department: str | None = None,
	days: int = 7,
	limit: int = 5,
) -> list:
	frappe.has_permission("OT Booking", "write", throw=True)
	case = case_to_place(service_request, booking)
	company = company or case.company or frappe.defaults.get_user_default("Company")
	theatres = matching_theatres(case, company, department)
	candidates = []
	for day in coming_days(case, int(days)):
		candidates += day_candidates(case, company, theatres, day)
	candidates.sort(key=lambda slot: (slot["after_expected"], slot["start"]))
	return confirmed(case, service_request, candidates, int(limit))


def case_to_place(service_request, booking):
	"""The case as a booking, with what the finder needs: its length, theatre type, surgeon,
	priority and Expected By"""
	if service_request:
		case = make_ot_booking(service_request)
		case.expected_date = frappe.db.get_value("Service Request", service_request, "expected_date")
	else:
		case = frappe.get_doc("OT Booking", booking)
		case.check_permission("write")
		case.expected_date = None
	case.length = timedelta(seconds=sum(int(row.duration or 0) for row in case.procedures))
	case.surgeon = next((member.practitioner for member in case.team if member.is_primary), None)
	case.theatre_types = {
		frappe.db.get_value("Clinical Procedure Template", row.procedure_template, "required_theatre_type")
		for row in case.procedures
	} - {None}
	return case


def matching_theatres(case, company, department):
	if len(case.theatre_types) > 1:
		return []
	theatres = get_theatres(company, department).values()
	return [t for t in theatres if not case.theatre_types or t.service_unit_type in case.theatre_types]


def coming_days(case, days):
	"""From today for an emergency, else from tomorrow: only an emergency is added on the day"""
	first = getdate(today()) if is_emergency(case.priority) else add_days(getdate(today()), 1)
	return [add_days(first, offset) for offset in range(days)]


def day_candidates(case, company, theatres, day, also=()):
	"""Each theatre's free starts that day; `also` holds more starts worth trying"""
	if not theatres or not case.length or skipped_day(case, company, day):
		return []
	start, end = day_window(day)
	if day == getdate(today()):
		start = max(start, rounded_up(now_datetime()))
	team_busy, team_ends = team_times(case, start, end)
	people_busy = team_busy + patient_busy_times(case, start)
	slots = []
	for theatre in theatres:
		busy = theatre_busy_times(case, theatre.name, start, end) + people_busy
		gaps = free_starts(start, end, case.length, busy, also=[*team_ends, *also])
		slots += [slot(case, theatre, gap) for gap in gaps]
	return slots


def skipped_day(case, company, day):
	"""A full theatre holiday or the surgeon's full day of leave"""
	if is_holiday(theatre_holiday_list(company), day):
		return True
	leaves = find_leaves([case.surgeon], day, day) if case.surgeon else []
	return any(not leave.is_half_day for leave in leaves)


def theatre_busy_times(case, theatre, start, end):
	"""The theatre's cases with their cleaning time either side, and its Unavailable blocks"""
	cleaning = cleaning_time()
	cases = frappe.get_all(
		"OT Booking",
		fields=["scheduled_start", "scheduled_end"],
		filters={
			"theatre": theatre,
			**running_into(start - cleaning),
			"status": ["not in", INACTIVE_STATUSES],
			"name": ["!=", case.name or ""],
		},
	)
	busy = [
		(get_datetime(c.scheduled_start) - cleaning, get_datetime(c.scheduled_end) + cleaning) for c in cases
	]
	return busy + block_times([theatre], start, end)


def team_times(case, start, end):
	"""The team's busy times (their blocks, and their cases in any theatre that day unless allowed
	to overlap), and the ends of the cases of those who are allowed: a start worth trying, as the
	server may still refuse a third theatre at once"""
	team = list({member.practitioner for member in case.team if member.practitioner})
	if not team:
		return [], []
	may_overlap = practitioners_allowed_to_overlap(team)
	cases = team_cases(case, team, start)
	busy = block_times(team, start, end) + times_of(c for c in cases if c.practitioner not in may_overlap)
	return busy, [get_datetime(c.scheduled_end) for c in cases if c.practitioner in may_overlap]


def team_cases(case, team, start):
	booking, member = frappe.qb.DocType("OT Booking"), frappe.qb.DocType("OT Booking Team")
	day = getdate(start)
	return (
		frappe.qb.from_(booking)
		.join(member)
		.on(member.parent == booking.name)
		.select(member.practitioner, booking.scheduled_start, booking.scheduled_end)
		.where(member.parenttype == "OT Booking")
		.where(member.practitioner.isin(team))
		.where(booking.scheduled_date[add_days(day, -1) : day])
		.where(booking.scheduled_end > start)
		.where(booking.status.notin(INACTIVE_STATUSES))
		.where(booking.name != (case.name or ""))
	).run(as_dict=True)


def patient_busy_times(case, start):
	"""The patient's other cases that day"""
	cases = frappe.get_all(
		"OT Booking",
		fields=["scheduled_start", "scheduled_end"],
		filters={
			"patient": case.patient,
			**running_into(start),
			"status": ["not in", INACTIVE_STATUSES],
			"name": ["!=", case.name or ""],
		},
	)
	return times_of(cases)


def running_into(start):
	"""Cases of the day, and those from the night before still running at `start`"""
	day = getdate(start)
	return {"scheduled_date": ["between", [add_days(day, -1), day]], "scheduled_end": [">", start]}


def times_of(cases):
	return [(get_datetime(c.scheduled_start), get_datetime(c.scheduled_end)) for c in cases]


def block_times(scopes, start, end):
	day = getdate(start)
	return [
		(datetime.combine(day, get_time(b.start_time)), datetime.combine(day, get_time(b.end_time)))
		for b in find_unavailable_blocks(scopes, start, end)
	]


def free_starts(start, end, length, busy, also=()):
	"""The start of each free gap, on the 15-minute grid, where `length` and the cleaning after it
	fit between `start` and `end` without entering a busy time; earliest first. `also` holds more
	moments worth trying, such as when an overlapping practitioner's case ends."""
	needed = length + cleaning_time()
	moments = [busy_end for _, busy_end in busy] + list(also)
	starts = sorted({start, *(max(rounded_up(moment), start) for moment in moments)})
	return [
		candidate
		for candidate in starts
		if candidate + needed <= end
		and not any(candidate < busy_end and busy_start < candidate + length for busy_start, busy_end in busy)
	]


def rounded_up(moment):
	moment = get_datetime(moment).replace(second=0, microsecond=0)
	extra = timedelta(minutes=moment.minute % 15)
	return moment + (GRID - extra if extra else timedelta(0))


def slot(case, theatre, start):
	return {
		"theatre": theatre.name,
		"theatre_label": theatre.label,
		"date": getdate(start),
		"start": start,
		"end": start + case.length,
		"after_expected": bool(case.expected_date) and getdate(start) > getdate(case.expected_date),
	}


def confirmed(case, service_request, candidates, limit):
	"""The first slot the server's own checks accept in each theatre and day, in a dry run that
	keeps nothing: a refused gap gives way to the next one in that theatre that day"""
	slots, taken, checks = [], set(), 0
	for candidate in candidates:
		if len(slots) == limit or checks == MAX_CHECKS:
			break
		if (candidate["theatre"], candidate["date"]) in taken:
			continue
		checks += 1
		if not check_drop(*drop_for(case, service_request, candidate)):
			slots.append(candidate)
			taken.add((candidate["theatre"], candidate["date"]))
	return slots


def drop_for(case, service_request, candidate):
	start = str(candidate["start"])
	if service_request:
		return "book_request", {
			"service_request": service_request,
			"theatre": candidate["theatre"],
			"start": start,
		}
	params = {
		"name": case.name,
		"theatre": candidate["theatre"],
		"start": start,
		"modified": str(case.modified),
	}
	return "move_booking", params
