import frappe

from healthcare.setup import setup_healthcare_status_codes

# FHIR status code -> Healthcare status code (the bare Code Value name)
FHIR_TO_STATUS = {
	"active": "Active",
	"on-hold": "On Hold",
	"cancelled": "Cancelled",
	"completed": "Completed",
	"entered-in-error": "Entered in Error",
	"stopped": "Stopped",
	"draft": "Draft",
	"unknown": "Unknown",
	"ended": "Ended",
	"revoked": "Revoked",
}


def execute():
	setup_healthcare_status_codes()
	# Repoint documents that store the FHIR status (Link to Code Value) to the local code,
	# so documents hold the local status and FHIR is derived at transform time.
	for doctype in ("Medication Request", "Service Request"):
		for name, status in frappe.get_all(
			doctype, filters={"status": ["is", "set"]}, fields=["name", "status"], as_list=True
		):
			local = FHIR_TO_STATUS.get(frappe.db.get_value("Code Value", status, "code_value"))
			if local and frappe.db.exists("Code Value", local):
				frappe.db.set_value(doctype, name, "status", local, update_modified=False)
