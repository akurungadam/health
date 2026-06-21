import frappe


def execute():
	"""Backfill an open-ended Patient Registration for every active patient that lacks one."""
	if not frappe.db.table_exists("Patient Registration"):
		return

	registered = frappe.get_all("Patient Registration", pluck="patient")
	patients = frappe.get_all(
		"Patient",
		filters={"status": "Active", "name": ["not in", registered or [""]]},
		fields=["name", "creation"],
	)

	for patient in patients:
		registration = frappe.new_doc("Patient Registration")
		registration.patient = patient.name
		registration.start_date = patient.creation
		registration.valid_till = None
		registration.status = "Active"
		registration.insert(ignore_permissions=True)
