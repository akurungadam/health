# Copyright (c) 2015, ESS and Contributors
# See license.txt

import frappe

from healthcare.healthcare.doctype.sample_collection.sample_collection import (
	SampleCollection,
	update_collection_status,
)
from healthcare.tests.utils import HealthcareTestSuite


class TestSampleCollection(HealthcareTestSuite):
	def test_validate_status_handles_all_collection_states(self):
		test_cases = [
			([], "Pending"),
			([frappe._dict({"status": "Open"})], "Pending"),
			([frappe._dict({"status": "Collected"})], "Collected"),
			([frappe._dict({"status": "Collected"}), frappe._dict({"status": "Open"})], "Partly Collected"),
		]

		for child_rows, expected_status in test_cases:
			with self.subTest(child_rows=child_rows, expected_status=expected_status):
				doc = frappe._dict(observation_sample_collection=child_rows, status=None)
				SampleCollection.validate(doc)
				self.assertEqual(doc.status, expected_status)

	def test_update_collection_status_handles_all_collection_states(self):
		test_cases = [
			([], "Pending"),
			([frappe._dict({"status": "Open"})], "Pending"),
			([frappe._dict({"status": "Collected"})], "Collected"),
			([frappe._dict({"status": "Collected"}), frappe._dict({"status": "Open"})], "Partly Collected"),
		]

		for child_rows, expected_status in test_cases:
			with self.subTest(child_rows=child_rows, expected_status=expected_status):
				context = frappe._dict(sample_collection="SC-TEST-0001")
				original_get_all = frappe.db.get_all
				original_set_value = frappe.db.set_value
				set_value_calls = []
				try:
					frappe.db.get_all = lambda *args, **kwargs: child_rows
					frappe.db.set_value = lambda *args: set_value_calls.append(args)
					update_collection_status(context)
					self.assertEqual(
						set_value_calls,
						[("Sample Collection", context.sample_collection, "status", expected_status)],
					)
				finally:
					frappe.db.get_all = original_get_all
					frappe.db.set_value = original_set_value
