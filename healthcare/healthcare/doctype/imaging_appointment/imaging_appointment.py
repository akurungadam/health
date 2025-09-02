# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _, generate_hash
from frappe.model.document import Document

from healthcare.healthcare.doctype.imaging_study.imaging_study import build_dicom_hierarchy


class ImagingAppointment(Document):
	def autoname(self):
		self.name = generate_hash(length=16)  # accession number VR SH 16

	def on_update(self):
		if self.status == "In Progress":
			pass  # nothing to do (?)
		elif self.status == "Completed":
			if self.appointment:
				frappe.db.set_value("Patient Appointment", self.appointment, "status", "Closed")

			study = self.create_imaging_study()
			if not study:
				frappe.throw(_("Cannot create Imaging Study. Please check Error Logs for details."))

			self.create_observation(study)

	def create_imaging_study(self):
		if frappe.db.exists("Imaging Study", {"study_instance_uid": self.study_instance_uid}):
			frappe.throw(_(f"Imaging Study already exists for UID {self.study_instance_uid}"))
			return  #  edit?

		if not self.dataset:
			frappe.log_error(f"Dataset not initialized to create study. {self.study_instance_uid}")
			return

		mpps_data = json.loads(self.dataset)
		study = frappe.new_doc("Imaging Study")
		study.patient = self.patient
		study.patient_name = self.patient_name
		study.gender = self.gender
		study.date_of_birth = self.date_of_birth
		study.study_instance_uid = self.study_instance_uid
		study.imaging_appointment = self.name
		study.modality = self.modality
		study.station_ae = self.claimed_by or self.station_ae
		study.competed_on = mpps_data.get("end_time", frappe.utils.now())
		study.performer = mpps_data.get("performer_name", "")
		study.status = "Pending Review"

		study.series = json.dumps(build_dicom_hierarchy(mpps_data), indent=1)
		study.dataset = json.dumps(mpps_data, indent=1)
		study.save(ignore_permissions=True)
		study.reload()
		return study.name

	def create_observation(self, study):
		if not frappe.db.exists("Observation", {"appointment": self.name}):
			obs = frappe.new_doc("Observation")
			obs.imaging_study = study
			obs.patient = self.patient
			obs.observation_template = self.observation_template
			obs.observation_type = "Imaging"
			obs.imaging_appointment = self.name
			obs.study_instance_uid = self.study_instance_uid
			obs.station_ae = self.claimed_by or self.station_ae
			obs.exam_status = self.status
			obs.appointment = self.appointment
			obs.status = "Preliminary"
			obs.save(ignore_permissions=True)
