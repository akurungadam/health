# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Approved HRMS leave of practitioners, through the Employee each one is linked to.
HRMS does not record which half of the day a half-day leave covers, so callers only
warn about a half day and refuse a full one."""

import frappe
from frappe import _
from frappe.utils import getdate


def find_leaves(practitioners, start_date, end_date, company=None):
	"""Approved leave touching `start_date` to `end_date`, in `company` when given. Each
	row carries its `practitioner` and `is_half_day`. Empty when HRMS is not installed."""
	if "hrms" not in frappe.get_installed_apps():
		return []
	employees = linked_employees(practitioners)
	if not employees:
		return []
	leaves = frappe.get_all(
		"Leave Application",
		fields=["name", "employee", "half_day", "half_day_date"],
		filters=leave_filters(employees, start_date, end_date, company),
	)
	for leave in leaves:
		leave.practitioner = employees[leave.employee]
		leave.is_half_day = is_half_day_only(leave, start_date, end_date)
	return leaves


def leave_filters(employees, start_date, end_date, company):
	filters = {
		"employee": ["in", list(employees)],
		"status": "Approved",
		"docstatus": 1,
		"from_date": ["<=", getdate(end_date)],
		"to_date": [">=", getdate(start_date)],
	}
	if company:
		filters["company"] = company
	return filters


def is_half_day_only(leave, start_date, end_date):
	if not (leave.half_day and leave.half_day_date):
		return False
	return getdate(start_date) == getdate(end_date) == getdate(leave.half_day_date)


def leave_message(leave):
	if leave.is_half_day:
		return _("{0} is on half-day leave ({1})").format(frappe.bold(leave.practitioner), leave.name)
	return _("{0} is on leave ({1})").format(frappe.bold(leave.practitioner), leave.name)


def linked_employees(practitioners):
	"""Employee → practitioner, for the practitioners linked to an Employee"""
	rows = frappe.get_all(
		"Healthcare Practitioner",
		fields=["name", "employee"],
		filters={"name": ["in", practitioners], "employee": ["is", "set"]},
	)
	return {row.employee: row.name for row in rows}
