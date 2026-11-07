# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""One day of the OT Scheduler: the theatres grouped by OT complex, the day's bookings,
the theatre holiday, the time theatres are blocked and the practitioners who are away."""

from datetime import datetime

from dateutil.relativedelta import relativedelta

import frappe
from frappe.utils import cint, get_time, getdate

from healthcare.healthcare.doctype.healthcare_practitioner.practitioner_leave import find_leaves
from healthcare.healthcare.doctype.ot_booking.availability import theatre_holiday_list
from healthcare.healthcare.doctype.ot_booking.conflict_checker import INACTIVE_STATUSES
from healthcare.healthcare.doctype.ot_booking.day_rules import needs_change_reason
from healthcare.healthcare.doctype.ot_booking.ot_booking import NEXT_STATUSES
from healthcare.healthcare.doctype.practitioner_availability.practitioner_availability import (
	find_unavailable_blocks,
)


@frappe.whitelist()
def get_board(date: str, company: str | None = None) -> dict:
	frappe.has_permission("OT Booking", "read", throw=True)
	date = getdate(date)
	company = company or frappe.defaults.get_user_default("Company")
	start, end = day_window(date)
	theatres = get_theatres(company)
	return {
		"date": date,
		"day_start": start,
		"day_end": end,
		"cleaning_minutes": cint(frappe.db.get_single_value("Healthcare Settings", "ot_cleaning_minutes")),
		"holiday": get_holiday(company, date),
		"complexes": group_by_complex(theatres),
		"bookings": get_bookings(date, list(theatres)),
		"blocks": find_unavailable_blocks(list(theatres), start, end) if theatres else [],
		"away": get_away(date, start, end, company),
	}


def day_window(date):
	start = frappe.db.get_single_value("Healthcare Settings", "ot_day_start_time") or "08:00:00"
	end = frappe.db.get_single_value("Healthcare Settings", "ot_day_end_time") or "20:00:00"
	return datetime.combine(date, get_time(start)), datetime.combine(date, get_time(end))


def get_theatres(company):
	"""Theatre name → theatre, in tree order"""
	filters = {"is_ot": 1, "is_group": 0}
	if company:
		filters["company"] = company
	theatres = frappe.get_all(
		"Healthcare Service Unit",
		fields=[
			"name",
			"healthcare_service_unit_name as label",
			"parent_healthcare_service_unit as complex",
			"service_unit_type",
		],
		filters=filters,
		order_by="lft",
	)
	return {theatre.name: theatre for theatre in theatres}


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
			"scheduled_start",
			"scheduled_end",
			"fasting_confirmed",
			"modified",
		],
		filters={
			"scheduled_date": date,
			"status": ["not in", INACTIVE_STATUSES],
			"theatre": ["in", theatres],
		},
		order_by="scheduled_start",
		limit=0,
	)
	if bookings:
		add_surgeons_and_procedures(bookings)
		add_patient_details(bookings, date)
	return bookings


def add_surgeons_and_procedures(bookings):
	names = [booking.name for booking in bookings]
	surgeons = dict(
		frappe.get_all(
			"OT Booking Team",
			fields=["parent", "practitioner_name"],
			filters={"parent": ["in", names], "parenttype": "OT Booking", "is_primary": 1},
			as_list=True,
		)
	)
	procedures = frappe.get_all(
		"OT Booking Procedure",
		fields=["parent", "procedure_template", "clinical_procedure"],
		filters={"parent": ["in", names], "parenttype": "OT Booking"},
		order_by="idx",
	)
	for booking in bookings:
		booking.next_statuses = NEXT_STATUSES.get(booking.status, ())
		booking.needs_reason = needs_change_reason(booking)
		booking.surgeon = surgeons.get(booking.name)
		rows = [row for row in procedures if row.parent == booking.name]
		booking.procedures = [row.procedure_template for row in rows]
		booking.procedures_pending = booking.status != "Completed" and any(
			not row.clinical_procedure for row in rows
		)


def add_patient_details(rows, on_date):
	"""Each row's patient `sex`, and `age` on `on_date` such as 45y, or 8m under a year"""
	patients = {
		patient.name: patient
		for patient in frappe.get_all(
			"Patient",
			fields=["name", "sex", "dob"],
			filters={"name": ["in", list({row.patient for row in rows})]},
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
