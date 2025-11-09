# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EmergencyRecord(Document):
	def after_insert(self):
		if self.patient:
			patient_doc = frappe.get_doc("Patient", self.patient)
			if not patient_doc.emergency_record:
				patient_doc.db_set("emergency_record", self.name)
				patient_doc.notify_update()

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
				"practitioner": self.practitioner,
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
	def add_clinical_note(self, note, note_type=None):
		clinical_note_doc = frappe.new_doc("Clinical Note")
		clinical_note_doc.patient = self.patient
		clinical_note_doc.reference_doc = "Emergency Record"
		clinical_note_doc.reference_name = self.name
		clinical_note_doc.note = note
		clinical_note_doc.clinical_note_type = note_type
		clinical_note_doc.practitioner = self.practitioner
		clinical_note_doc.insert()

	@frappe.whitelist()
	def edit_clinical_note(self, note, note_name):
		clinical_note_doc = frappe.get_doc("Clinical Note", note_name)
		clinical_note_doc.note = note
		clinical_note_doc.save()

	@frappe.whitelist()
	def delete_clinical_note(self, note_name):
		if frappe.db.exists("Clinical Note", note_name):
			frappe.delete_doc("Clinical Note", note_name)

	@frappe.whitelist()
	def get_clinical_notes(self, patient):
		return frappe.get_all(
			"Clinical Note",
			{
				"patient": patient,
			},
			["posting_date", "note", "name", "practitioner", "user", "clinical_note_type"],
		)
