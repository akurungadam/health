# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from math import ceil

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, now_datetime, time_diff_in_hours, today

from healthcare.healthcare.doctype.observation.observation import (
	add_observation,
	record_observation_result,
)


class EmergencyRecord(Document):
	_DOCTYPE_NAME = "Emergency Record"

	def validate(self):
		self.set_patient_age()
		self.set_consultation_defaults()
		self.validate_occupancy_dates()

	def set_patient_age(self):
		if not self.patient:
			return
		age = frappe.get_cached_doc("Patient", self.patient).calculate_age()
		self.patient_age = age.get("age_in_string") if age else None

	def set_consultation_defaults(self):
		if not self.attending_practitioner:
			return
		practitioner = frappe.get_cached_doc("Healthcare Practitioner", self.attending_practitioner)
		if not self.get("consultation_item"):
			self.consultation_item = practitioner.op_consulting_charge_item
		if not self.get("consultation_charge"):
			self.consultation_charge = practitioner.op_consulting_charge

	def validate_occupancy_dates(self):
		for entry in self.occupancies:
			if (
				entry.check_in
				and entry.check_out
				and get_datetime(entry.check_in) > get_datetime(entry.check_out)
			):
				frappe.throw(_("Row #{0}: Check Out cannot be before Check In").format(entry.idx))

	@frappe.whitelist()
	def record_triage(self, triage_level):
		self.triage_level = triage_level
		self.triage_datetime = now_datetime()
		if self.status == "Registered":
			self.status = "Triaged"
		self.save()

	@frappe.whitelist()
	def assign_bed(self, service_unit, check_in=None):
		self.occupy_service_unit(service_unit, check_in or now_datetime())
		self.service_unit = service_unit
		if self.status in ("Registered", "Triaged"):
			self.status = "In Treatment"
		self.save()

	@frappe.whitelist()
	def transfer_bed(self, service_unit, check_in=None):
		self.release_current_bed(now_datetime())
		self.assign_bed(service_unit, check_in)

	@frappe.whitelist()
	def release_bed(self):
		self.release_current_bed(now_datetime())
		self.service_unit = None
		self.save()

	def occupy_service_unit(self, service_unit, check_in):
		if frappe.get_cached_value("Healthcare Service Unit", service_unit, "occupancy_status") != "Vacant":
			frappe.throw(
				_("Service Unit {0} is already occupied. Please choose a vacant one.").format(
					frappe.bold(service_unit)
				),
				title=_("Service Unit Occupied"),
			)
		self.append("occupancies", {"service_unit": service_unit, "check_in": check_in})
		frappe.db.set_value("Healthcare Service Unit", service_unit, "occupancy_status", "Occupied")

	def release_current_bed(self, check_out):
		for entry in self.occupancies:
			if not entry.left:
				entry.left = 1
				entry.check_out = check_out
				frappe.db.set_value(
					"Healthcare Service Unit", entry.service_unit, "occupancy_status", "Vacant"
				)

	@frappe.whitelist()
	def get_occupancy_billable_items(self):
		item_hours = {}
		for occupancy in self.occupancies:
			unit_type = self.get_billable_service_unit_type(occupancy.service_unit)
			if not unit_type:
				continue
			check_out = get_datetime(occupancy.check_out) if occupancy.check_out else now_datetime()
			hours = flt(time_diff_in_hours(check_out, get_datetime(occupancy.check_in)), 2)
			detail = item_hours.setdefault(
				unit_type.item,
				{"item": unit_type.item, "uom": unit_type.uom, "rate": unit_type.rate, "hours": 0},
			)
			detail["hours"] += hours
			detail["no_of_hours"] = unit_type.no_of_hours
			detail["minimum_billable_qty"] = unit_type.minimum_billable_qty

		items = []
		for detail in item_hours.values():
			qty = occupancy_qty(detail["hours"], detail["no_of_hours"], detail["minimum_billable_qty"])
			if qty > 0:
				items.append(
					{"item_code": detail["item"], "qty": qty, "rate": detail["rate"], "uom": detail["uom"]}
				)
		return items

	def get_billable_service_unit_type(self, service_unit):
		service_unit_type = frappe.db.get_value("Healthcare Service Unit", service_unit, "service_unit_type")
		if not service_unit_type:
			return None
		unit_type = frappe.get_cached_doc("Healthcare Service Unit Type", service_unit_type)
		if not unit_type.is_billable or not unit_type.item:
			return None
		return unit_type

	@frappe.whitelist()
	def add_vital_signs(self, vitals):
		vitals = json.loads(vitals) if isinstance(vitals, str) else vitals
		results = [self.create_vital_observation(vital) for vital in vitals]
		record_observation_result(json.dumps(results))
		return results

	def create_vital_observation(self, vital):
		template = frappe.get_cached_doc("Observation Template", vital.get("template"))
		observation = add_observation(
			patient=self.patient,
			template=template.name,
			data_type=template.permitted_data_type,
			doc=self.doctype,
			docname=self.name,
			practitioner=self.triage_practitioner or self.attending_practitioner,
			company=self.company,
		)
		return {"observation": observation, "result": vital.get("result")}

	@frappe.whitelist()
	def get_vital_signs(self):
		return frappe.get_all(
			"Observation",
			filters={
				"reference_doctype": self.doctype,
				"reference_docname": self.name,
				"observation_category": "Vital Signs",
				"status": ["!=", "Cancelled"],
			},
			fields=["observation_template", "result_data", "permitted_unit", "posting_date"],
			order_by="creation desc",
		)

	@frappe.whitelist()
	def set_disposition(self, disposition, notes=None):
		self.disposition = disposition
		self.disposition_notes = notes
		self.disposition_datetime = now_datetime()
		if disposition == "Admitted":
			self.admit_to_inpatient()
		self.release_current_bed(now_datetime())
		self.service_unit = None
		self.status = "Closed"
		self.save()

	def admit_to_inpatient(self):
		patient = frappe.get_doc("Patient", self.patient)
		record = frappe.new_doc("Inpatient Record")
		record.update(
			{
				"patient": patient.name,
				"patient_name": patient.patient_name,
				"gender": patient.sex,
				"blood_group": patient.blood_group,
				"dob": patient.dob,
				"mobile": patient.mobile,
				"email": patient.email,
				"phone": patient.phone,
				"primary_practitioner": self.attending_practitioner,
				"medical_department": self.medical_department,
				"company": self.company,
				"admission_instruction": self.chief_complaint,
				"scheduled_date": today(),
				"status": "Admission Scheduled",
			}
		)
		record.insert(ignore_permissions=True)
		self.inpatient_record = record.name


def occupancy_qty(hours, no_of_hours, minimum_billable_qty):
	blocks = ceil(hours / no_of_hours) if no_of_hours else hours
	return max(blocks, minimum_billable_qty or 0)


@frappe.whitelist()
def get_active_triage(patient):
	records = frappe.get_all(
		"Emergency Record",
		filters={"patient": patient, "status": ["not in", ["Closed", "Cancelled"]]},
		fields=["name", "triage_level"],
		order_by="arrival_datetime desc",
		limit=1,
	)
	if not records or not records[0].triage_level:
		return None

	color, code = frappe.db.get_value("Triage Level", records[0].triage_level, ["color", "code"]) or (
		None,
		None,
	)
	return {
		"emergency_record": records[0].name,
		"triage_level": records[0].triage_level,
		"color": color,
		"code": code,
	}
