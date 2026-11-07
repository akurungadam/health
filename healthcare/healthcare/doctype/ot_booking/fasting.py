# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""The ward's nil-by-mouth Nursing Task for a Scheduled case whose procedures need fasting.
It starts the longest fasting time any of them needs before the case, follows the case when
it moves, and goes when the case is no longer Scheduled. When the ward completes it, the
booking's fasting is confirmed. The task is the system's, so it is made and cancelled without
the user's own Nursing Task permissions."""

import frappe
from frappe import _
from frappe.utils import add_to_date, flt, format_time, get_datetime

OPEN_TASK_STATUSES = ("Requested", "Received", "Accepted", "Ready", "In Progress", "On Hold")


def sync_fasting_task(booking):
	activity = frappe.db.get_single_value("Healthcare Settings", "ot_fasting_activity")
	if not activity:
		return
	task = current_task(booking.name)
	hours = fasting_hours(booking)
	if booking.status != "Scheduled" or not hours:
		cancel_if_open(task)
	elif not task or start_moved(booking):
		cancel_if_open(task)
		create_task(booking, activity, hours)


def fasting_hours(booking):
	"""The longest fasting any of the case's procedures needs, or 0 when none needs it. A
	procedure with no hours of its own takes the Operation Theatre default."""
	templates = frappe.get_all(
		"Clinical Procedure Template",
		fields=["requires_fasting", "fasting_hours"],
		filters={"name": ["in", [row.procedure_template for row in booking.procedures]]},
	)
	default = flt(frappe.db.get_single_value("Healthcare Settings", "ot_fasting_hours"))
	return max((flt(row.fasting_hours) or default for row in templates if row.requires_fasting), default=0)


def confirm_fasting(task, method=None):
	if task.reference_doctype == "OT Booking" and task.status == "Completed":
		frappe.db.set_value("OT Booking", task.reference_name, "fasting_confirmed", 1)


def current_task(booking):
	"""The booking's latest fasting task that was not cancelled"""
	return frappe.db.get_value(
		"Nursing Task",
		{"reference_doctype": "OT Booking", "reference_name": booking, "status": ["!=", "Cancelled"]},
		["name", "status"],
		as_dict=True,
		order_by="creation desc",
	)


def start_moved(booking):
	before = booking.get_doc_before_save()
	return bool(before) and get_datetime(before.scheduled_start) != get_datetime(booking.scheduled_start)


def cancel_if_open(task):
	if not task or task.status not in OPEN_TASK_STATUSES:
		return
	nursing_task = frappe.get_doc("Nursing Task", task.name)
	nursing_task.flags.ignore_permissions = True
	nursing_task.cancel()


def create_task(booking, activity, hours):
	start = get_datetime(booking.scheduled_start)
	frappe.get_doc(
		{
			"doctype": "Nursing Task",
			"status": "Requested",
			"activity": activity,
			"reference_doctype": "OT Booking",
			"reference_name": booking.name,
			"patient": booking.patient,
			"company": booking.company,
			"service_unit": current_bed(booking),
			"requested_start_time": add_to_date(start, hours=-hours),
			"duration": hours * 3600,
			"description": _("Nil by mouth from {0}, for the case at {1} in {2}").format(
				format_time(add_to_date(start, hours=-hours)), format_time(start), booking.theatre
			),
		}
	).insert(ignore_permissions=True)
	booking.db_set("fasting_confirmed", 0, update_modified=False)


def current_bed(booking):
	if not booking.inpatient_record:
		return None
	return frappe.db.get_value(
		"Inpatient Occupancy", {"parent": booking.inpatient_record, "left": 0}, "service_unit"
	)
