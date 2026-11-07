# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Publishing a day: each Tentative case on it becomes Scheduled and gets its Clinical
Procedures. A case that fails its checks stays Tentative, alone, and is reported; the
rest of the day still publishes."""

import frappe
from frappe.utils import getdate


@frappe.whitelist()
def publish_day(date: str, company: str | None = None) -> dict:
	frappe.has_permission("OT Booking", "write", throw=True)
	published, failed = [], []
	for name in tentative_cases(getdate(date), company):
		error = publish_case(name)
		if error:
			failed.append({"name": name, "message": error})
		else:
			published.append(name)
	return {"published": published, "failed": failed}


def tentative_cases(date, company):
	filters = {"scheduled_date": date, "status": "Tentative"}
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
		frappe.local.message_log = frappe.local.message_log[:messages]
		return str(error)
	frappe.db.release_savepoint(savepoint)
	return None
