import json
from datetime import datetime

import frappe
from frappe import _
from frappe.query_builder.functions import Avg, Count, Date, Max
from frappe.utils import add_years, get_timespan_date_range, get_timestamp, getdate


@frappe.whitelist()
def get_therapy_sessions_count(patient: str) -> dict:
	frappe.has_permission("Patient", "read", patient, throw=True)
	total = frappe.db.count("Therapy Session", filters={"docstatus": 1, "patient": patient})

	month_start = datetime.today().replace(day=1)
	this_month = frappe.db.count(
		"Therapy Session", filters={"creation": [">", month_start], "docstatus": 1, "patient": patient}
	)

	return {"total_therapy_sessions": total, "therapy_sessions_this_month": this_month}


@frappe.whitelist()
def get_patient_heatmap_data(patient: str, date: str) -> dict:
	frappe.has_permission("Patient", "read", patient, throw=True)
	record = frappe.qb.DocType("Patient Medical Record")
	rows = (
		frappe.qb.from_(record)
		.select(record.communication_date, Count("*"))
		.where(
			(record.communication_date > add_years(date, -1))
			& (record.communication_date < add_years(date, 1))
			& (record.patient == patient)
		)
		.groupby(record.communication_date)
		.orderby(record.communication_date)
	).run()
	return {int(get_timestamp(day)): count for day, count in rows}


@frappe.whitelist()
def get_therapy_sessions_distribution_data(patient: str, field: str) -> dict:
	frappe.has_permission("Patient", "read", patient, throw=True)
	if field == "therapy_type":
		result = frappe.db.get_all(
			"Therapy Session",
			filters={"patient": patient, "docstatus": 1},
			group_by=field,
			order_by=field,
			fields=[field, "count(*)"],
			as_list=True,
		)

	elif field == "exercise_type":
		data = frappe.db.get_all(
			"Therapy Session", filters={"docstatus": 1, "patient": patient}, as_list=True
		)
		therapy_sessions = [entry[0] for entry in data]

		result = frappe.db.get_all(
			"Exercise",
			filters={"parenttype": "Therapy Session", "parent": ["in", therapy_sessions], "docstatus": 1},
			group_by=field,
			order_by=field,
			fields=[field, "count(*)"],
			as_list=True,
		)

	return {
		"labels": [r[0] for r in result if r[0] is not None],
		"datasets": [{"values": [r[1] for r in result]}],
	}


@frappe.whitelist()
def get_therapy_progress_data(patient: str, therapy_type: str, time_span: str) -> dict:
	frappe.has_permission("Patient", "read", patient, throw=True)
	from_date, to_date = get_date_range(time_span)
	session = frappe.qb.DocType("Therapy Session")
	result = (
		frappe.qb.from_(session)
		.select(session.start_date, session.total_counts_targeted, session.total_counts_completed)
		.where(
			session.start_date.between(from_date, to_date)
			& (session.docstatus == 1)
			& (session.therapy_type == therapy_type)
			& (session.patient == patient)
		)
		.orderby(session.start_date)
	).run()

	return {
		"labels": [r[0] for r in result if r[0] is not None],
		"datasets": [
			{"name": _("Targetted"), "values": [r[1] for r in result if r[0] is not None]},
			{"name": _("Completed"), "values": [r[2] for r in result if r[0] is not None]},
		],
	}


@frappe.whitelist()
def get_patient_assessment_data(patient: str, assessment_template: str, time_span: str) -> dict:
	frappe.has_permission("Patient", "read", patient, throw=True)
	from_date, to_date = get_date_range(time_span)
	assessment = frappe.qb.DocType("Patient Assessment")
	result = (
		frappe.qb.from_(assessment)
		.select(assessment.assessment_datetime, assessment.total_score, assessment.total_score_obtained)
		.where(
			Date(assessment.assessment_datetime).between(from_date, to_date)
			& (assessment.docstatus == 1)
			& (assessment.assessment_template == assessment_template)
			& (assessment.patient == patient)
		)
		.orderby(assessment.assessment_datetime)
	).run()

	return {
		"labels": [getdate(r[0]) for r in result if r[0] is not None],
		"datasets": [{"name": _("Score Obtained"), "values": [r[2] for r in result if r[0] is not None]}],
		"max_score": result[0][1] if result else None,
	}


@frappe.whitelist()
def get_therapy_assessment_correlation_data(patient: str, assessment_template: str, time_span: str) -> dict:
	frappe.has_permission("Patient", "read", patient, throw=True)
	from_date, to_date = get_date_range(time_span)
	assessment = frappe.qb.DocType("Patient Assessment")
	therapy = frappe.qb.DocType("Therapy Session")
	result = (
		frappe.qb.from_(assessment)
		.inner_join(therapy)
		.on(assessment.therapy_session == therapy.name)
		.select(
			therapy.therapy_type,
			Count("*"),
			Avg(assessment.total_score_obtained),
			Max(assessment.total_score),
		)
		.where(
			Date(assessment.assessment_datetime).between(from_date, to_date)
			& (assessment.docstatus == 1)
			& (assessment.patient == patient)
			& (assessment.assessment_template == assessment_template)
		)
		.groupby(therapy.therapy_type)
	).run()

	return {
		"labels": [r[0] for r in result if r[0] is not None],
		"datasets": [
			{"name": _("Sessions"), "chartType": "bar", "values": [r[1] for r in result if r[0] is not None]},
			{
				"name": _("Average Score"),
				"chartType": "line",
				"values": [round(r[2], 2) for r in result if r[0] is not None],
			},
		],
		"max_score": result[0][1] if result else None,
	}


@frappe.whitelist()
def get_assessment_parameter_data(patient: str, parameter: str, time_span: str) -> dict:
	frappe.has_permission("Patient", "read", patient, throw=True)
	from_date, to_date = get_date_range(time_span)
	sheet = frappe.qb.DocType("Patient Assessment Sheet")
	assessment = frappe.qb.DocType("Patient Assessment")
	template = frappe.qb.DocType("Patient Assessment Template")
	results = (
		frappe.qb.from_(sheet)
		.inner_join(assessment)
		.on(sheet.parent == assessment.name)
		.inner_join(template)
		.on(template.name == assessment.assessment_template)
		.select(assessment.assessment_datetime, sheet.score, template.scale_max)
		.where(
			Date(assessment.assessment_datetime).between(from_date, to_date)
			& (assessment.docstatus == 1)
			& (sheet.parameter == parameter)
			& (assessment.patient == patient)
		)
		.orderby(assessment.assessment_datetime)
	).run()

	score_percentages = []
	for r in results:
		if r[2] != 0 and r[0] is not None:
			score = round((int(r[1]) / int(r[2])) * 100, 2)
			score_percentages.append(score)

	return {
		"labels": [getdate(r[0]) for r in results if r[0] is not None],
		"datasets": [{"name": _("Score"), "values": score_percentages}],
	}


def get_date_range(time_span):
	try:
		time_span = json.loads(time_span)
		return time_span
	except json.decoder.JSONDecodeError:
		return get_timespan_date_range(time_span.lower())
