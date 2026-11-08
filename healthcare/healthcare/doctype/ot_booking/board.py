# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""One day of the OT Scheduler: the theatres grouped by OT complex, the day's bookings,
the theatre holiday, the time theatres are blocked and the practitioners who are away."""

from datetime import datetime, time

from dateutil.relativedelta import relativedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_time, getdate

from healthcare.healthcare.doctype.healthcare_practitioner.practitioner_leave import find_leaves
from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import ot_setting
from healthcare.healthcare.doctype.ot_booking.availability import theatre_holiday_list
from healthcare.healthcare.doctype.ot_booking.conflict_checker import INACTIVE_STATUSES
from healthcare.healthcare.doctype.ot_booking.day_rules import needs_change_reason
from healthcare.healthcare.doctype.ot_booking.fasting import is_fasting_confirmed
from healthcare.healthcare.doctype.ot_booking.ot_booking import NEXT_STATUSES
from healthcare.healthcare.doctype.ot_booking.priority import add_priority
from healthcare.healthcare.doctype.ot_booking.same_patient import add_other_cases
from healthcare.healthcare.doctype.practitioner_availability.practitioner_availability import (
	find_unavailable_blocks,
)


@frappe.whitelist()
def get_board(date: str, company: str | None = None, department: str | None = None) -> dict:
	frappe.has_permission("OT Booking", "read", throw=True)
	date = getdate(date)
	company = company or frappe.defaults.get_user_default("Company")
	start, end = day_window(date)
	theatres = get_theatres(company, department)
	return {
		"date": date,
		"company": company,
		"department": department or "",
		# the board is read-only for a viewer who cannot change bookings
		"can_edit": bool(frappe.has_permission("OT Booking", "write")),
		"companies": frappe.get_list("Company", pluck="name", order_by="name", limit=0),
		"departments": theatre_departments(company),
		"day_start": start,
		"day_end": end,
		"cleaning_minutes": cint(ot_setting("ot_cleaning_minutes")),
		"layout": ot_setting("ot_board_layout"),
		"holiday": get_holiday(company, date),
		"complexes": group_by_complex(theatres),
		"bookings": get_bookings(date, list(theatres)),
		"blocks": find_unavailable_blocks(list(theatres), start, end) if theatres else [],
		"away": get_away(date, start, end, company),
	}


def day_window(date):
	start, end = ot_setting("ot_day_start_time"), ot_setting("ot_day_end_time")
	return datetime.combine(date, get_time(start)), datetime.combine(date, get_time(end))


def get_theatres(company, department=None):
	"""Theatre name → theatre, in tree order: only those the user may read"""
	check_company_access(company)
	filters = theatre_filters(company)
	if department:
		filters["medical_department"] = department
	theatres = frappe.get_list(
		"Healthcare Service Unit",
		fields=[
			"name",
			"healthcare_service_unit_name as label",
			"parent_healthcare_service_unit as complex",
			"service_unit_type",
		],
		filters=filters,
		order_by="lft",
		limit=0,
	)
	return {theatre.name: theatre for theatre in theatres}


def check_company_access(company):
	"""A theatre's company ignores user permissions, so the company itself is checked: it must be
	one the user can see"""
	if company and company not in frappe.get_list("Company", pluck="name", limit=0):
		frappe.throw(
			_("You cannot see the theatres of {0}").format(frappe.bold(company)), frappe.PermissionError
		)


def theatre_filters(company):
	filters = {"is_ot": 1, "is_group": 0}
	if company:
		filters["company"] = company
	return filters


def theatre_departments(company):
	"""The departments the company's theatres belong to, for the board's Department filter"""
	check_company_access(company)
	filters = {**theatre_filters(company), "medical_department": ["is", "set"]}
	return frappe.get_list(
		"Healthcare Service Unit",
		filters=filters,
		pluck="medical_department",
		distinct=True,
		order_by="medical_department",
		limit=0,
	)


def group_by_complex(theatres):
	complexes = {}
	for theatre in theatres.values():
		complexes.setdefault(theatre.complex, {"name": theatre.complex, "theatres": []})
		complexes[theatre.complex]["theatres"].append(theatre)
	return list(complexes.values())


def get_holiday(company, date):
	holiday_list = theatre_holiday_list(company)
	if not holiday_list:
		return None
	return frappe.db.get_value(
		"Holiday",
		{"parent": holiday_list, "holiday_date": date},
		["description", "is_half_day"],
		as_dict=True,
	)


def get_bookings(date, theatres):
	"""The day's cases, and the night's from the day before that run on into it. A case is shorter
	than a day, so looking one day back finds them all."""
	if not theatres:
		return []
	bookings = frappe.get_list(
		"OT Booking",
		fields=[
			"name",
			"theatre",
			"patient",
			"patient_name",
			"status",
			"priority",
			"scheduled_date",
			"scheduled_start",
			"scheduled_end",
			"modified",
		],
		filters={
			"scheduled_date": ["between", [add_days(date, -1), date]],
			"scheduled_end": [">", datetime.combine(date, time.min)],
			"status": ["not in", INACTIVE_STATUSES],
			"theatre": ["in", theatres],
		},
		order_by="scheduled_start",
		limit=0,
	)
	if bookings:
		add_surgeons_and_procedures(bookings)
		add_patient_details(bookings, date)
		add_other_cases(bookings)
	return bookings


def add_surgeons_and_procedures(bookings):
	names = [booking.name for booking in bookings]
	team = frappe.get_all(
		"OT Booking Team",
		fields=["parent", "practitioner_name", "role", "is_primary"],
		filters={"parent": ["in", names], "parenttype": "OT Booking"},
		order_by="idx",
	)
	surgeons = {member.parent: member.practitioner_name for member in team if member.is_primary}
	procedures = frappe.get_all(
		"OT Booking Procedure",
		fields=["parent", "procedure_template", "clinical_procedure"],
		filters={"parent": ["in", names], "parenttype": "OT Booking"},
		order_by="idx",
	)
	add_priority(bookings)
	for booking in bookings:
		booking.needs_reason = needs_change_reason(booking)
		booking.surgeon = surgeons.get(booking.name)
		# everyone on the case, for the board's practitioner filter and the practitioner-wise print
		members = [member for member in team if member.parent == booking.name]
		booking.team_names = [member.practitioner_name for member in members]
		booking.team_roles = [{"name": member.practitioner_name, "role": member.role} for member in members]
		rows = [row for row in procedures if row.parent == booking.name]
		booking.next_statuses = next_statuses(booking, rows)
		booking.procedures = [row.procedure_template for row in rows]
		booking.fasting_confirmed = is_fasting_confirmed(booking, booking.procedures)
		booking.procedures_pending = booking.status != "Completed" and any(
			not row.clinical_procedure for row in rows
		)


def next_statuses(booking, rows):
	"""A started case may also be cancelled once no row holds a procedure, as cancelling its
	procedures releases them"""
	statuses = NEXT_STATUSES.get(booking.status, ())
	if booking.status == "In Progress" and not any(row.clinical_procedure for row in rows):
		statuses = (*statuses, "Cancelled")
	return statuses


def add_patient_details(rows, on_date):
	"""Each row's patient `sex`, and `age` on `on_date` such as 45y, or 8m under a year. A
	patient the caller cannot read gets neither."""
	if not frappe.has_permission("Patient", "read"):
		patients = {}
	else:
		patients = {
			patient.name: patient
			for patient in frappe.get_list(
				"Patient",
				fields=["name", "sex", "dob"],
				filters={"name": ["in", list({row.patient for row in rows})]},
				limit=0,
			)
		}
	for row in rows:
		patient = patients.get(row.patient, frappe._dict())
		row.sex = patient.sex
		row.age = age_text(patient.dob, on_date)


def age_text(dob, on_date):
	if not dob:
		return None
	age = relativedelta(getdate(on_date), getdate(dob))
	return f"{age.years}y" if age.years else f"{age.months}m"


def get_away(date, start, end, company):
	"""Practitioners the caller can read who are on leave in `company`, or blocked,
	during the theatre day. Rows say who, why and when, never which record."""
	if not frappe.has_permission("Healthcare Practitioner", "read"):
		return []
	practitioners = dict(
		frappe.get_list(
			"Healthcare Practitioner",
			fields=["name", "practitioner_name"],
			filters={"status": "Active"},
			as_list=True,
			limit=0,
		)
	)
	if not practitioners:
		return []
	away = [
		away_row(practitioners, block.scope, "Unavailable", block.start_time, block.end_time)
		for block in find_unavailable_blocks(list(practitioners), start, end)
	]
	away += [
		away_row(practitioners, leave.practitioner, "Half-day Leave" if leave.is_half_day else "Leave")
		for leave in find_leaves(list(practitioners), date, date, company)
	]
	return away


def away_row(practitioners, practitioner, reason, from_time=None, to_time=None):
	return {
		"practitioner": practitioner,
		"practitioner_name": practitioners[practitioner],
		"reason": reason,
		"from_time": from_time,
		"to_time": to_time,
	}
