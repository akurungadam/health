import frappe
from frappe.utils import add_years, get_timestamp, getdate

from healthcare.healthcare.page.patient_progress.patient_progress import (
	get_patient_heatmap_data,
)
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

	def create_medical_record(self, day):
		record = {"patient": PATIENT, "communication_date": day, "subject": "_Test Record"}
		frappe.get_doc({"doctype": "Patient Medical Record", **record}).insert()
