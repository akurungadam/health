# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""An OT Booking's priority is a code of the Priority code system, the same one a Service
Request and a Clinical Procedure use: STAT, ASAP, Urgent or Routine. Only STAT is an emergency,
which may be added on the day of surgery and is only warned about a holiday, a block or leave."""

import frappe
from frappe import _

PRIORITY_CODE_SYSTEM = "Priority"
EMERGENCY_CODE = "STAT"
DEFAULT_CODE = "Routine"


def is_emergency(priority):
	return priority_code(priority) == EMERGENCY_CODE.upper()


def priority_code(priority):
	"""The code of a Priority Code Value, upper-cased, such as STAT"""
	if not priority:
		return ""
	return (frappe.db.get_value("Code Value", priority, "code_value", cache=True) or "").upper()


def add_priority(rows):
	"""Each row's priority code as written, such as STAT, and whether it is an emergency"""
	for row in rows:
		row.priority_label = priority_label(row.priority)
		row.is_emergency = is_emergency(row.priority)


def priority_label(priority):
	if not priority:
		return ""
	return frappe.db.get_value("Code Value", priority, "code_value", cache=True) or ""


def priority_named(code):
	"""The Priority Code Value whose code is `code`, such as STAT or Routine"""
	return frappe.db.get_value("Code Value", {"code_system": PRIORITY_CODE_SYSTEM, "code_value": code})


def set_priority(booking):
	if not booking.priority:
		booking.priority = priority_named(DEFAULT_CODE)
	elif frappe.db.get_value("Code Value", booking.priority, "code_system") != PRIORITY_CODE_SYSTEM:
		frappe.throw(
			_("Priority {0} is not a code of the {1} code system").format(
				frappe.bold(booking.priority), PRIORITY_CODE_SYSTEM
			)
		)
