# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Rules for a committed list. Adding a case never needs a reason, but on the day of surgery
only an emergency, or an OT Manager, can add one or move one in from another day. Once a case
is published (Scheduled), moving it, rescheduling it or cancelling it needs a reason; a
Tentative case changes freely. The reason is for that one change: once saved it goes to the
timeline and the field is emptied for the next one."""

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, today

from healthcare.healthcare.doctype.ot_booking.conflict_checker import INACTIVE_STATUSES
from healthcare.healthcare.doctype.ot_booking.priority import is_emergency


def validate_day_rules(booking):
	before = booking.get_doc_before_save()
	if not before or (is_surgery_day(booking) and not is_surgery_day(before)):
		validate_same_day_addition(booking)
	elif needs_change_reason(before) and (is_stopped(booking, before) or is_moved(booking, before)):
		validate_reason_given(booking)


def needs_change_reason(booking):
	"""Whether moving or stopping the case needs a reason: only once its day's list is published"""
	return booking.status == "Scheduled"


def validate_same_day_addition(booking):
	if not is_surgery_day(booking) or is_emergency(booking.priority):
		return
	if "OT Manager" not in frappe.get_roles():
		frappe.throw(
			_("Only an emergency case can be added on the day of surgery"), title=_("Day Already Planned")
		)


def is_moved(booking, before):
	return booking.theatre != before.theatre or get_datetime(booking.scheduled_start) != get_datetime(
		before.scheduled_start
	)


def is_stopped(booking, before):
	return booking.status in INACTIVE_STATUSES and before.status not in INACTIVE_STATUSES


def validate_reason_given(booking):
	if not (booking.change_reason or "").strip():
		frappe.throw(_("Give a Change Reason for this change"), title=_("Reason Required"))


def log_change_reason(booking):
	if not booking.change_reason:
		return
	booking.add_comment("Info", _("Change reason: {0}").format(booking.change_reason))
	booking.db_set("change_reason", None, update_modified=False)


def is_surgery_day(booking):
	return getdate(booking.scheduled_start) == getdate(today())
