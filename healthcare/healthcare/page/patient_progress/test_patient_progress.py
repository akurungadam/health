import json

import frappe
from frappe.utils import add_years, get_timestamp, getdate, now_datetime

from healthcare.healthcare.page.patient_progress.patient_progress import (
	get_patient_heatmap_data,
	get_therapy_assessment_correlation_data,
)
from healthcare.tests.factories.encounters import create_therapy_plan, create_therapy_session
from healthcare.tests.utils import HealthcareTestSuite

PATIENT = "_Test Patient"


class TestPatientProgress(HealthcareTestSuite):
	def test_heatmap_counts_records_per_day_within_a_year(self):
		today = getdate()
		for day in (today, today, add_years(today, -2)):
			self.create_medical_record(day)

		heatmap = get_patient_heatmap_data(PATIENT, str(today))

		self.assertEqual(heatmap[int(get_timestamp(today))], 2)
		self.assertNotIn(int(get_timestamp(add_years(today, -2))), heatmap)

	def test_correlation_groups_assessments_by_therapy_type(self):
		plan = create_therapy_plan()
		session = create_therapy_session(plan.patient, "Basic Rehab", plan.name, 30, start_time="09:00:00")
		for score in ("2", "4"):
			self.create_assessment(session.name, score)

		span = json.dumps([str(getdate()), str(getdate())])
		data = get_therapy_assessment_correlation_data(PATIENT, "_Test Assessment Template", span)

		self.assertEqual(data["labels"], ["Basic Rehab"])
		self.assertEqual(data["datasets"][0]["values"], [2])
		self.assertEqual(data["datasets"][1]["values"], [3])

	def create_medical_record(self, day):
		record = {"patient": PATIENT, "communication_date": day, "subject": "_Test Record"}
		frappe.get_doc({"doctype": "Patient Medical Record", **record}).insert()

	def create_assessment(self, therapy_session, score):
		assessment = frappe.new_doc("Patient Assessment")
		assessment.update(
			{
				"patient": PATIENT,
				"therapy_session": therapy_session,
				"assessment_template": "_Test Assessment Template",
				"assessment_datetime": now_datetime(),
				"total_score": 5,
			}
		)
		assessment.append("assessment_sheet", {"parameter": "_Test Mobility", "score": score})
		assessment.insert().submit()
