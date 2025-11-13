# Copyright (c) 2023, healthcare and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form


class DischargeSummary(Document):
	@frappe.whitelist()
	def get_encounter_details(self):
		encounters = frappe.get_all(
			"Patient Encounter", {"inpatient_record": self.inpatient_record}, ["name"], pluck="name"
		)
		all_medication_requests = []
		all_service_requests = []
		for encounter in encounters:
			medication_requests = []
			service_requests = []
			filters = {"patient": self.patient, "docstatus": 1}
			if encounter:
				filters["order_group"] = encounter
			medication_requests = frappe.get_all("Medication Request", filters, ["*"])
			if medication_requests:
				all_medication_requests += medication_requests
			service_requests = frappe.get_all("Service Request", filters, ["*"])
			if service_requests:
				all_service_requests += service_requests
			for service_request in service_requests:
				if service_request.template_dt == "Lab Test Template":
					lab_test = frappe.db.get_value(
						"Lab Test", {"service_request": service_request.name}, "name"
					)
					if lab_test:
						subject = frappe.db.get_value(
							"Patient Medical Record", {"reference_name": lab_test}, "subject"
						)
						if subject:
							service_request["lab_details"] = subject

		return all_medication_requests, all_service_requests

	def validate(self):
		self.validate_encounter_impression()

	def on_submit(self):
		self.db_set("status", "Approved")

	def on_cancel(self):
		self.db_set("status", "Cancelled")

	def validate_encounter_impression(self):
		if frappe.db.exists("Patient Encounter", {"inpatient_record": self.inpatient_record}):
			encounter = frappe.get_last_doc(
				"Patient Encounter", filters={"inpatient_record": self.inpatient_record}
			)
			if encounter:
				if encounter.diagnosis:
					self.diagnosis = []
					for d in encounter.diagnosis:
						self.append("diagnosis", (frappe.copy_doc(d)).as_dict())
				if encounter.symptoms:
					self.chief_complaint = []
					for symptom in encounter.symptoms:
						self.append("chief_complaint", (frappe.copy_doc(symptom)).as_dict())

	def get_order_details(self, template_doc, line_item, medication_request=False):
		qty = 1

		order = frappe.get_doc(
			{
				"doctype": "Medication Request" if medication_request else "Service Request",
				"order_date": self.get("encounter_date", frappe.utils.getdate()),
				"order_time": self.get("encounter_time", frappe.utils.now()),
				"company": self.company,
				"status": "draft-Medication Request Status" if medication_request else "draft-Request Status",
				"patient": self.get("patient"),
				"practitioner": self.discharge_practitioner,
				"source_doc": self.doctype,
				"order_group": self.name,
				"sequence": line_item.get("sequence"),
				"patient_care_type": line_item.get("patient_care_type"),
				"intent": line_item.get("intent"),
				"priority": line_item.get("priority"),
				"quantity": qty,
				"dosage": line_item.get("dosage"),
				"dosage_form": line_item.get("dosage_form"),
				"period": line_item.get("period"),
				"interval": line_item.get("interval"),
				"expected_date": line_item.get("expected_date") or line_item.get("date"),
				"occurrence_date": line_item.get("expected_date") or line_item.get("date"),
				"as_needed": line_item.get("as_needed"),
				"staff_role": template_doc.get("staff_role") if template_doc else "",
				"note": line_item.get("note"),
				"patient_instruction": line_item.get("patient_instruction"),
				"insurance_policy": self.get("insurance_policy"),
				"comment": line_item.get("comments") or line_item.get("lab_test_comment"),
			}
		)

		description = ""
		if not line_item.get("description"):
			if template_doc:
				if template_doc.get("doctype") == "Lab Test Template":
					description = template_doc.get("lab_test_description")
				else:
					description = template_doc.get("description")
		else:
			description = line_item.get("description")

		if template_doc and template_doc.get("doctype") == "Clinical Procedure Template":
			order.update(
				{
					"referred_to_practitioner": line_item.get("practitioner"),
				}
			)

		if medication_request:
			order.update(
				{
					"medication": template_doc.get("name") if template_doc else "",
					"number_of_repeats_allowed": line_item.get("number_of_repeats_allowed"),
					"medication_item": line_item.get("drug_code") if line_item.get("drug_code") else "",
				}
			)
		else:
			order.update(
				{
					"template_dt": template_doc.get("doctype"),
					"template_dn": template_doc.get("name"),
				}
			)

		order.update({"order_description": description})
		return order


@frappe.whitelist()
def has_discharge_summary(inpatient_record):
	if frappe.db.exists("Discharge Summary", {"docstatus": 1, "inpatient_record": inpatient_record}):
		return True

	draft_summary = frappe.db.exists(
		"Discharge Summary", {"docstatus": 0, "inpatient_record": inpatient_record}
	)
	message = (
		_(
			f"A draft Discharge Summary exists. To proceed, please submit: {get_link_to_form('Discharge Summary', draft_summary)}"
		)
		if draft_summary
		else _("Please submit a Discharge Summary to proceed with discharging the patient.")
	)

	frappe.throw(message)
