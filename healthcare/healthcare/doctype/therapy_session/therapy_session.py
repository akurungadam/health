# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.query_builder import Criterion
from frappe.utils import flt, get_link_to_form, get_time, getdate

from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import (
	get_income_account,
	get_receivable_account,
)
from healthcare.healthcare.doctype.nursing_task.nursing_task import NursingTask
from healthcare.healthcare.doctype.service_request.service_request import (
	update_service_request_status,
)
from healthcare.healthcare.utils import validate_nursing_tasks


class TherapySession(Document):
	def validate(self):
		self.set_exercises_from_therapy_type()
		self.validate_duplicate()
		self.set_total_counts()

	def after_insert(self):
		self.create_nursing_tasks(post_event=False)

	def on_update(self):
		if self.appointment:
			frappe.db.set_value("Patient Appointment", self.appointment, "status", "Closed")

	def on_cancel(self):
		if self.appointment:
			frappe.db.set_value("Patient Appointment", self.appointment, "status", "Open")
		if self.service_request:
			frappe.db.set_value("Service Request", self.service_request, "status", "active-Request Status")

		self.update_sessions_count_in_therapy_plan(on_cancel=True)

	def validate_duplicate(self):
		overlap = next((other.name for other in self.get_same_day_sessions() if self.overlaps(other)), None)
		if overlap:
			overlapping_details = _("Therapy Session overlaps with {0}").format(
				get_link_to_form("Therapy Session", overlap)
			)
			frappe.throw(overlapping_details, title=_("Therapy Sessions Overlapping"))

	def get_same_day_sessions(self):
		session = frappe.qb.DocType("Therapy Session")
		people = [
			session[field] == self.get(field) for field in ("practitioner", "patient") if self.get(field)
		]
		if not people:
			return []
		return (
			frappe.qb.from_(session)
			.select(session.name, session.start_time, session.duration)
			.where(
				(session.start_date == self.start_date)
				& (session.name != self.name)
				& (session.docstatus != 2)
				& session.start_time.isnotnull()
				& Criterion.any(people)
			)
		).run(as_dict=True)

	def overlaps(self, other):
		start, end = self.get_window(self.start_time, self.duration)
		other_start, other_end = self.get_window(other.start_time, other.duration)
		contains = other_start < start and other_end > end
		return contains or start < other_start < end or other_start == start

	def get_window(self, start_time, duration):
		start = datetime.datetime.combine(getdate(self.start_date), get_time(start_time))
		return start, start + datetime.timedelta(minutes=flt(duration))

	def on_submit(self):
		validate_nursing_tasks(self)
		self.update_sessions_count_in_therapy_plan()

		if self.service_request:
			status = "active-Request Status"
			sessions_completed = self.check_sessions_completed()
			if sessions_completed:
				status = "completed-Request Status"

			update_service_request_status(self.service_request, status)

	def create_nursing_tasks(self, post_event=True):
		template = frappe.db.get_value("Therapy Type", self.therapy_type, "nursing_checklist_template")
		if template:
			NursingTask.create_nursing_tasks_from_template(
				template,
				self,
				start_time=frappe.utils.get_datetime(f"{self.start_date} {self.start_time}"),
				post_event=post_event,
			)

	def update_sessions_count_in_therapy_plan(self, on_cancel=False):
		therapy_plan = frappe.get_doc("Therapy Plan", self.therapy_plan)
		for entry in therapy_plan.therapy_plan_details:
			if entry.therapy_type == self.therapy_type:
				if on_cancel:
					entry.sessions_completed -= 1
				else:
					entry.sessions_completed += 1
		therapy_plan.save()

	def set_total_counts(self):
		target_total = 0
		counts_completed = 0
		for entry in self.exercises:
			if entry.counts_target:
				target_total += entry.counts_target
			if entry.counts_completed:
				counts_completed += entry.counts_completed

		self.db_set("total_counts_targeted", target_total)
		self.db_set("total_counts_completed", counts_completed)

	def set_exercises_from_therapy_type(self):
		if self.therapy_type and not self.exercises:
			therapy_type_doc = frappe.get_cached_doc("Therapy Type", self.therapy_type)
			if therapy_type_doc.exercises:
				for exercise in therapy_type_doc.exercises:
					self.append(
						"exercises",
						(frappe.copy_doc(exercise)).as_dict(),
					)

	def before_insert(self):
		if self.service_request:
			therapy_session = frappe.db.exists(
				"Therapy Session",
				{"service_request": self.service_request, "docstatus": 0},
			)
			if therapy_session:
				frappe.throw(
					_("Therapy Session {0} already created from service request {1}").format(
						frappe.bold(get_link_to_form("Therapy Session", therapy_session)),
						frappe.bold(get_link_to_form("Service Request", self.service_request)),
					),
					title=_("Already Exist"),
				)

	def check_sessions_completed(self):
		total_sessions_requested = frappe.db.get_value("Service Request", self.service_request, "quantity")
		sessions = frappe.db.count(
			"Therapy Session", filters={"docstatus": ["!=", 2], "service_request": self.service_request}
		)

		return True if total_sessions_requested == sessions else False


@frappe.whitelist()
def create_therapy_session(source_name, target_doc=None):
	def set_missing_values(source, target):
		therapy_type = frappe.get_doc("Therapy Type", source.therapy_type)
		target.exercises = therapy_type.exercises

	doc = get_mapped_doc(
		"Patient Appointment",
		source_name,
		{
			"Patient Appointment": {
				"doctype": "Therapy Session",
				"field_map": [
					["appointment", "name"],
					["patient", "patient"],
					["patient_age", "patient_age"],
					["gender", "patient_sex"],
					["therapy_type", "therapy_type"],
					["therapy_plan", "therapy_plan"],
					["practitioner", "practitioner"],
					["department", "department"],
					["start_date", "appointment_date"],
					["start_time", "appointment_time"],
					["service_unit", "service_unit"],
					["company", "company"],
					["invoiced", "invoiced"],
				],
			}
		},
		target_doc,
		set_missing_values,
	)

	return doc


@frappe.whitelist()
def invoice_therapy_session(source_name: str, target_doc: Document | str | None = None) -> Document:
	def set_missing_values(source, target):
		target.customer = frappe.db.get_value("Patient", source.patient, "customer")
		target.due_date = getdate()
		target.debit_to = get_receivable_account(source.company)
		item = target.append("items", {})
		item = get_therapy_item(source, item)
		target.set_missing_values(for_validate=True)

	doc = get_mapped_doc(
		"Therapy Session",
		source_name,
		{
			"Therapy Session": {
				"doctype": "Sales Invoice",
				"field_no_map": ["naming_series"],
				"field_map": [
					["patient", "patient"],
					["practitioner", "ref_practitioner"],
					["company", "company"],
					["due_date", "start_date"],
				],
			}
		},
		target_doc,
		set_missing_values,
	)

	return doc


def get_therapy_item(therapy, item):
	item.item_code = frappe.db.get_value("Therapy Type", therapy.therapy_type, "item")
	item.description = _("Therapy Session Charges: {0}").format(therapy.practitioner)
	item.income_account = get_income_account(therapy.practitioner, therapy.company)
	item.cost_center = frappe.get_cached_value("Company", therapy.company, "cost_center")
	item.rate = therapy.rate
	item.amount = therapy.rate
	item.qty = 1
	item.reference_dt = "Therapy Session"
	item.reference_dn = therapy.name
	return item
