# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Publishing a day: each Tentative case on it becomes Scheduled and gets its Clinical
Procedures. A case that fails its checks stays Tentative, alone, and is reported; the
rest of the day still publishes."""

import frappe
from frappe.utils import getdate

from healthcare.healthcare.doctype.ot_booking.board import get_theatres
from healthcare.healthcare.doctype.ot_booking.refusal import refusal_text


@frappe.whitelist()
def publish_day(date: str, company: str | None = None, department: str | None = None) -> dict:
	"""Publishes only the cases the board shows: the company's, in the department's theatres"""
	frappe.has_permission("OT Booking", "write", throw=True)
	company = company or frappe.defaults.get_user_default("Company")
	published, failed = [], []
	for name in tentative_cases(getdate(date), company, department):
		error = publish_case(name)
		if error:
			failed.append({"name": name, "message": error})
		else:
			published.append(name)
	return {"published": published, "failed": failed}


def tentative_cases(date, company, department):
	theatres = list(get_theatres(company, department))
	if not theatres:
		return []
	filters = {"scheduled_date": date, "status": "Tentative", "theatre": ["in", theatres]}
	if company:
		filters["company"] = company
	return frappe.get_list("OT Booking", filters=filters, order_by="scheduled_start", pluck="name", limit=0)


def publish_case(name):
	"""The case's error message, or None once it is published"""
	savepoint = f"publish_{frappe.scrub(name)}"
	messages = len(frappe.local.message_log)
	frappe.db.savepoint(savepoint)
	try:
		booking = frappe.get_doc("OT Booking", name)
		booking.status = "Scheduled"
		booking.save()
		booking.create_clinical_procedures()
	except frappe.ValidationError as error:
		frappe.db.rollback(save_point=savepoint)
		# the failure is reported in the result, not again as a message on the response
		return refusal_text(error, messages)
	frappe.db.release_savepoint(savepoint)
	return None
