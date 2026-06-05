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
	runtime = FHIRRuntime(compiled)
	runtime._load_sources = lambda _pid: runtime.source_docs.update(source_docs)
	return runtime.generate(primary_id)


PRIMARY_ONLY = {"primary": {"doctype": "Patient", "kind": "document", "is_primary": True}}


def element(source="primary", datatype="", is_array=False, **value_spec):
	return {"source": source, "datatype": datatype, "is_array": is_array, "value_spec": value_spec}


def collection_source(doctype, fhir_path, parent="primary", link_fieldname=None):
	return {
		"doctype": doctype,
		"kind": "child_table",
		"is_primary": False,
		"is_collection": True,
		"parent": parent,
		"link_fieldname": link_fieldname,
		"fhir_path": fhir_path,
	}


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

	def test_repeating_backbone_wrapped_as_array(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"array_paths": ["Patient.name"],
			"elements": {
				"Patient.name.family": element(datatype="string", kind="field", fieldname="last_name"),
				"Patient.name.given": element(
					datatype="string", is_array=True, kind="field", fieldname="first_name"
				),
			},
		}
		result = run(compiled, {"primary": {"last_name": "Doe", "first_name": "John"}})

		self.assertEqual(result["name"], [{"family": "Doe", "given": ["John"]}])

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
			"elements": {"Patient.gender": element(datatype="code", kind="field", fieldname="sex")},
		}
		result = run(compiled, {"primary": {"sex": None}})
		self.assertEqual(result, {"resourceType": "Patient"})

	def test_value_map_translates_code(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"elements": {
				"Patient.gender": element(
					datatype="code",
					kind="field",
					fieldname="sex",
					map={"Male": "male", "Female": "female", "*": "unknown"},
				),
			},
		}
		self.assertEqual(run(compiled, {"primary": {"sex": "Male"}})["gender"], "male")
		self.assertEqual(run(compiled, {"primary": {"sex": "Trans"}})["gender"], "unknown")

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

	def test_collection_grouping_simple(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": {
				"primary": {"doctype": "Patient", "kind": "document", "is_primary": True},
				"phones": collection_source("Phone", "Patient.telecom", link_fieldname="phones"),
			},
			"elements": {
				"Patient.telecom.value": element(
					source="phones", datatype="string", kind="field", fieldname="number"
				),
			},
		}
		docs = {"primary": {"name": "P-1"}, "phones": [{"number": "123"}, {"number": "456"}]}
		result = run(compiled, docs)

		self.assertEqual(result["telecom"], [{"value": "123"}, {"value": "456"}])

	def test_collection_grouping_nested_object_per_row(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": {
				"primary": {"doctype": "Patient", "kind": "document", "is_primary": True},
				"contacts": collection_source("Contact", "Patient.contact", link_fieldname="contacts"),
			},
			"elements": {
				"Patient.contact.name.given": element(
					source="contacts", datatype="string", is_array=True, kind="field", fieldname="first_name"
				),
				"Patient.contact.gender": element(
					source="contacts", datatype="code", kind="field", fieldname="sex"
				),
			},
		}
		docs = {
			"primary": {"name": "P-1"},
			"contacts": [
				{"first_name": "Ann", "sex": "female"},
				{"first_name": "Bob", "sex": "male"},
			],
		}
		result = run(compiled, docs)

		self.assertEqual(
			result["contact"],
			[
				{"name": {"given": ["Ann"]}, "gender": "female"},
				{"name": {"given": ["Bob"]}, "gender": "male"},
			],
		)

	def test_dynamic_link_collection_grouping(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": {
				"primary": {"doctype": "Patient", "kind": "document", "is_primary": True},
				"addresses": {
					"doctype": "Address",
					"kind": "dynamic_link",
					"is_primary": False,
					"is_collection": True,
					"parent": "primary",
					"fhir_path": "Patient.address",
				},
			},
			"elements": {
				"Patient.address.city": element(
					source="addresses", datatype="string", kind="field", fieldname="city"
				),
				"Patient.address.line": element(
					source="addresses",
					datatype="string",
					is_array=True,
					kind="field",
					fieldname="address_line1",
				),
			},
		}
		docs = {
			"primary": {"name": "P-1"},
			"addresses": [
				{"city": "Kochi", "address_line1": "1 MG Rd"},
				{"city": "Delhi", "address_line1": "2 CP"},
			],
		}
		result = run(compiled, docs)

		self.assertEqual(
			result["address"],
			[{"city": "Kochi", "line": ["1 MG Rd"]}, {"city": "Delhi", "line": ["2 CP"]}],
		)

	def test_collection_of_references_at_backbone(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": {
				"primary": {"doctype": "Patient", "kind": "document", "is_primary": True},
				"encounters": {
					"doctype": "Patient Encounter",
					"kind": "reverse_link",
					"is_primary": False,
					"is_collection": True,
					"parent": "primary",
					"fhir_path": "Patient.generalPractitioner",
				},
			},
			"elements": {
				"Patient.generalPractitioner": {
					"source": "encounters",
					"datatype": "Reference",
					"is_array": False,
					"reference": {"resource_type": "Practitioner"},
					"value_spec": {"kind": "field", "fieldname": "practitioner"},
				},
			},
		}
		docs = {
			"primary": {"name": "P-1"},
			"encounters": [{"practitioner": "DR-1"}, {"practitioner": "DR-2"}],
		}
		result = run(compiled, docs)

		self.assertEqual(
			result["generalPractitioner"],
			[
				{"reference": "Practitioner/DR-1", "type": "Practitioner"},
				{"reference": "Practitioner/DR-2", "type": "Practitioner"},
			],
		)

	def test_reference_with_type_and_display(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"elements": {
				"Patient.managingOrganization": {
					"source": "primary",
					"datatype": "Reference",
					"is_array": False,
					"reference": {"resource_type": "Organization", "display_field": "org_name"},
					"value_spec": {"kind": "field", "fieldname": "org"},
				},
			},
		}
		docs = {"primary": {"org": "ORG-1", "org_name": "Acme Hospital"}}
		result = run(compiled, docs)

		self.assertEqual(
			result["managingOrganization"],
			{"reference": "Organization/ORG-1", "type": "Organization", "display": "Acme Hospital"},
		)

	def test_extension_built_at_root(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"elements": {},
			"extensions": [
				{
					"host": "Patient",
					"url": "http://example.org/fhir/StructureDefinition/note",
					"value_type": "valueString",
					"source": "primary",
					"is_modifier": False,
					"value_spec": {"kind": "field", "fieldname": "note"},
				}
			],
		}
		result = run(compiled, {"primary": {"note": "fragile"}})

		self.assertEqual(
			result["extension"],
			[{"url": "http://example.org/fhir/StructureDefinition/note", "valueString": "fragile"}],
		)

	def test_slices_with_pattern_on_same_array(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"elements": {},
			"slices": [
				{
					"path": "Patient.identifier",
					"slice_name": "MRN",
					"source": "primary",
					"pattern": {"system": "http://hospital.org/mrn"},
					"elements": [
						{
							"path": "value",
							"datatype": "string",
							"value_spec": {"kind": "field", "fieldname": "mrn"},
						}
					],
				},
				{
					"path": "Patient.identifier",
					"slice_name": "SSN",
					"source": "primary",
					"pattern": {"system": "http://hl7.org/fhir/sid/us-ssn"},
					"elements": [
						{
							"path": "value",
							"datatype": "string",
							"value_spec": {"kind": "field", "fieldname": "ssn"},
						}
					],
				},
			],
		}
		result = run(compiled, {"primary": {"mrn": "MRN-1", "ssn": "111-22-3333"}})

		self.assertEqual(
			result["identifier"],
			[
				{"system": "http://hospital.org/mrn", "value": "MRN-1"},
				{"system": "http://hl7.org/fhir/sid/us-ssn", "value": "111-22-3333"},
			],
		)

	def test_slice_dropped_when_mapped_value_empty(self):
		# an identifier slice whose only value field is blank must not emit a
		# pattern-only identifier (fails ident-1); it is dropped entirely.
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"elements": {},
			"slices": [
				{
					"path": "Patient.identifier",
					"slice_name": "MRN",
					"source": "primary",
					"pattern": {"system": "http://hospital.org/mrn"},
					"elements": [
						{
							"path": "value",
							"datatype": "string",
							"value_spec": {"kind": "field", "fieldname": "uid"},
						}
					],
				}
			],
		}
		# value present -> identifier emitted
		self.assertEqual(
			run(compiled, {"primary": {"uid": "MRN-1"}})["identifier"],
			[{"system": "http://hospital.org/mrn", "value": "MRN-1"}],
		)
		# value blank -> slice dropped, no identifier at all
		self.assertEqual(run(compiled, {"primary": {}}), {"resourceType": "Patient"})

	def test_modifier_extension_field_name(self):
		compiled = {
			"meta": {"resource_type": "Patient"},
			"sources": PRIMARY_ONLY,
			"elements": {},
			"extensions": [
				{
					"url": "http://example.org/mod",
					"value_type": "valueBoolean",
					"source": "primary",
					"is_modifier": True,
					"value_spec": {"kind": "fixed", "value": True},
				}
			],
		}
		result = run(compiled, {"primary": {}})

		self.assertEqual(
			result["modifierExtension"], [{"url": "http://example.org/mod", "valueBoolean": True}]
		)


class TestSourceLoaderChildTable(unittest.TestCase):
	def test_child_table_rows_from_frappe_dict(self):
		# frappe._dict returns None for missing attrs, so an `as_dict` hasattr check
		# wrongly passes; rows must be detected as dicts and used as-is.
		from frappe import _dict

		from healthcare.interoperability.doctype.fhir_resource_map.fhir_source_loader import SourceLoader

		loader = SourceLoader({})
		docs = {"primary": _dict({"phone_numbers": [_dict({"number": "123"})]})}
		source = {"kind": "child_table", "parent": "primary", "link_fieldname": "phone_numbers"}

		self.assertEqual(loader._child_table(source, docs), [{"number": "123"}])


class TestDateTimeTimezone(unittest.TestCase):
	"""A FHIR dateTime/instant with a time must carry a timezone (HL7 validator rule)."""

	def setUp(self):
		from healthcare.interoperability.doctype.fhir_resource_map.fhir_value_resolver import (
			ValueResolver,
		)

		self.resolver = ValueResolver()

	def test_existing_offset_preserved(self):
		self.assertEqual(
			self.resolver.transform("datetime", "2026-06-01T09:30:00+05:30"),
			"2026-06-01T09:30:00+05:30",
		)

	def test_utc_z_normalised(self):
		self.assertEqual(
			self.resolver.transform("datetime", "2026-06-01T09:30:00Z"),
			"2026-06-01T09:30:00+00:00",
		)

	def test_naive_value_gains_a_timezone(self):
		# Offset depends on the site timezone; assert one is present, not which.
		out = self.resolver.transform("datetime", "2026-06-01T09:30:00")
		self.assertRegex(out, r"^2026-06-01T09:30:00(?:[+-]\d{2}:\d{2}|Z)$")

	def test_date_only_stays_date(self):
		self.assertEqual(self.resolver.transform("date", "1990-01-02"), "1990-01-02")

	def test_date_only_value_on_datetime_element_keeps_date_precision(self):
		# A date-only source mapped to a dateTime element must not gain a spurious
		# midnight time + timezone (a date-precision dateTime is valid FHIR).
		self.assertEqual(self.resolver.transform("datetime", "2026-06-01"), "2026-06-01")


if __name__ == "__main__":
	unittest.main()
