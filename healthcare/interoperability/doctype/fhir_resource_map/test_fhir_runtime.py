# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and Contributors
# See license.txt

"""
DB-free unit tests for FHIRRuntime.

The runtime is fed a hand-written compiled mapping and the source documents are
injected directly (by replacing ``_load_sources``), so no DB reads happen.
"""

import unittest
from datetime import date

from healthcare.interoperability.doctype.fhir_resource_map.fhir_runtime import FHIRRuntime


def run(compiled, source_docs, primary_id="P-1"):
	rt = FHIRRuntime(compiled)
	rt._load_sources = lambda _pid: rt.source_docs.update(source_docs)
	return rt.generate(primary_id)


PRIMARY_ONLY = {"primary": {"doctype": "Patient", "kind": "document", "is_primary": True}}


def element(source="primary", datatype="", is_array=False, **value_spec):
	return {"source": source, "datatype": datatype, "is_array": is_array, "value_spec": value_spec}


class TestFHIRRuntime(unittest.TestCase):
	def test_scalar_fixed_and_field_with_transforms(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"elements": {
				"Patient.active": element(datatype="boolean", kind="fixed", value=True),
				"Patient.gender": element(datatype="code", kind="field", fieldname="sex"),
				"Patient.birthDate": element(datatype="date", kind="field", fieldname="dob"),
			},
		}
		docs = {"primary": {"sex": "male", "dob": date(1990, 1, 2)}}
		result = run(compiled, docs)

		self.assertEqual(result["resourceType"], "Patient")
		self.assertEqual(result["active"], True)
		self.assertEqual(result["gender"], "male")
		self.assertEqual(result["birthDate"], "1990-01-02")

	def test_nested_object_and_primitive_array(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"elements": {
				"Patient.name.family": element(datatype="string", kind="field", fieldname="last_name"),
				"Patient.name.given": element(
					datatype="string", is_array=True, kind="field", fieldname="first_name"
				),
			},
		}
		docs = {"primary": {"last_name": "Doe", "first_name": "John"}}
		result = run(compiled, docs)

		self.assertEqual(result["name"], {"family": "Doe", "given": ["John"]})

	def test_default_applied_when_field_missing(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"elements": {
				"Patient.birthDate": element(
					datatype="date", kind="field", fieldname="dob", default="2000-01-01"
				),
			},
		}
		result = run(compiled, {"primary": {}})
		self.assertEqual(result["birthDate"], "2000-01-01")

	def test_missing_value_is_pruned(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"elements": {
				"Patient.gender": element(datatype="code", kind="field", fieldname="sex"),
			},
		}
		result = run(compiled, {"primary": {"sex": None}})
		self.assertEqual(result, {"resourceType": "Patient"})
		self.assertNotIn("gender", result)

	def test_collection_source_not_grouped_yet(self):
		# iteration 1: an element bound to a list source produces nothing (no crash)
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": {
				"primary": {"doctype": "Patient", "kind": "document", "is_primary": True},
				"phones": {
					"doctype": "Phone",
					"kind": "child_table",
					"is_primary": False,
					"parent": "primary",
					"link_fieldname": "phones",
				},
			},
			"elements": {
				"Patient.telecom.value": element(
					source="phones", datatype="string", kind="field", fieldname="number"
				),
			},
		}
		docs = {"primary": {"name": "P-1"}, "phones": [{"number": "123"}, {"number": "456"}]}
		result = run(compiled, docs)
		self.assertEqual(result, {"resourceType": "Patient"})

	def test_dotted_field_path(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"elements": {
				"Patient.gender": element(datatype="code", kind="field", fieldname="details.sex"),
			},
		}
		result = run(compiled, {"primary": {"details": {"sex": "female"}}})
		self.assertEqual(result["gender"], "female")


if __name__ == "__main__":
	unittest.main()
