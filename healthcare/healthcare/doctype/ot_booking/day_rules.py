# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Rules for a committed list. On the day of surgery only an emergency can be added, unless
an OT Manager gives a reason. A Scheduled case, or any case on its own day, needs a reason to
move, cancel or postpone. The reason is for that one change: once saved it goes to the
timeline and the field is emptied for the next one."""

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, today

from healthcare.healthcare.doctype.ot_booking.conflict_checker import INACTIVE_STATUSES


def validate_day_rules(booking):
	before = booking.get_doc_before_save()
	if not before:
		validate_same_day_addition(booking)
	elif needs_change_reason(before) and is_moved_or_stopped(booking, before):
		validate_reason_given(booking)


def needs_change_reason(booking):
	return booking.status == "Scheduled" or is_surgery_day(booking)


def validate_same_day_addition(booking):
	if not is_surgery_day(booking) or booking.priority == "Emergency":
		return
	if "OT Manager" not in frappe.get_roles():
		frappe.throw(
			_("Only an emergency case can be added on the day of surgery"), title=_("Day Already Planned")
		)
	validate_reason_given(booking)


def is_moved_or_stopped(booking, before):
	moved = booking.theatre != before.theatre or get_datetime(booking.scheduled_start) != get_datetime(
		before.scheduled_start
	)
	stopped = booking.status in INACTIVE_STATUSES and before.status not in INACTIVE_STATUSES
	return moved or stopped


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
