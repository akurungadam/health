"""
Comprehensive Tests for FHIRValueResolver

These tests define the expected behavior of the value resolver.
They validate that resolved output conforms to the specification.

The resolver should:
1. Load source documents (primary, direct_link, reverse_link)
2. Resolve element values from sources based on compiled mappings
3. Return a flat dict: {element_path: resolved_value}
4. Coerce values to appropriate FHIR datatypes
5. Handle child tables and dot notation field access
"""

import frappe
from frappe.tests import IntegrationTestCase

from healthcare.interoperability.doctype.fhir_resource_map.value_resolver import FHIRValueResolver

# =========================================================
# Test Fixtures
# =========================================================


def create_test_patient(name, data):
	"""Create a test patient document."""
	if frappe.db.exists("Patient", name):
		frappe.delete_doc("Patient", name, force=True)

	doc = frappe.new_doc("Patient")
	doc.name = name
	for key, value in data.items():
		doc.set(key, value)
	doc.insert(ignore_permissions=True)
	return doc


def make_compiled_map(
	resource_type="Patient",
	primary_doctype="Patient",
	sources=None,
	elements=None,
	element_order=None,
):
	"""Factory to create compiled map structure for testing."""
	if sources is None:
		sources = {
			"primary": {
				"source_key": "primary",
				"kind": "primary",
				"doctype": primary_doctype,
			}
		}

	return {
		"compiled_version": "fhir-map-compiled/v1",
		"meta": {
			"resource_type": resource_type,
			"primary_doctype": primary_doctype,
		},
		"sources": sources,
		"elements": elements or {},
		"element_order": element_order or list((elements or {}).keys()),
	}


# =========================================================
# Fixed Value Resolution Tests
# =========================================================


class TestFixedValueResolution(IntegrationTestCase):
	"""Tests for resolving fixed/constant values."""

	def test_fixed_string_value(self):
		"""Fixed string values should be returned as-is."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {"kind": "fixed", "value": "test_value"},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.active"], "test_value")

	def test_fixed_boolean_true(self):
		"""Fixed boolean true should resolve to True."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {"kind": "fixed", "value": True},
					"datatype": "boolean",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertIs(resolver.resolved_values["Patient.active"], True)

	def test_fixed_boolean_false(self):
		"""Fixed boolean false should resolve to False."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {"kind": "fixed", "value": False},
					"datatype": "boolean",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertIs(resolver.resolved_values["Patient.active"], False)

	def test_fixed_integer_value(self):
		"""Fixed integer values should be returned as integers."""
		compiled = make_compiled_map(
			elements={
				"Patient.multipleBirthInteger": {
					"value_spec": {"kind": "fixed", "value": 2},
					"datatype": "integer",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.multipleBirthInteger"], 2)
		self.assertIsInstance(resolver.resolved_values["Patient.multipleBirthInteger"], int)

	def test_fixed_decimal_value(self):
		"""Fixed decimal values should be returned as floats."""
		compiled = make_compiled_map(
			elements={
				"Observation.valueQuantity.value": {
					"value_spec": {"kind": "fixed", "value": 98.6},
					"datatype": "decimal",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Observation.valueQuantity.value"], 98.6)
		self.assertIsInstance(resolver.resolved_values["Observation.valueQuantity.value"], float)

	def test_fixed_null_value_excluded(self):
		"""Fixed null values should not appear in resolved output."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {"kind": "fixed", "value": None},
					"datatype": "boolean",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertNotIn("Patient.active", resolver.resolved_values)

	def test_fixed_dict_value_preserved(self):
		"""Fixed dict values should be preserved as-is."""
		fixed_value = {"system": "http://example.org", "code": "ABC"}
		compiled = make_compiled_map(
			elements={
				"Patient.identifier.type": {
					"value_spec": {"kind": "fixed", "value": fixed_value},
					"datatype": "CodeableConcept",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.identifier.type"], fixed_value)

	def test_fixed_list_value_preserved(self):
		"""Fixed list values should be preserved as-is."""
		fixed_value = ["value1", "value2"]
		compiled = make_compiled_map(
			elements={
				"Patient.name.given": {
					"value_spec": {"kind": "fixed", "value": fixed_value},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.name.given"], fixed_value)


# =========================================================
# Field Value Resolution Tests
# =========================================================


class TestFieldValueResolution(IntegrationTestCase):
	"""Tests for resolving values from document fields."""

	def test_simple_field_resolution(self):
		"""Simple field values should be resolved from source document."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "last_name",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "last_name": "Smith"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.name.family"], "Smith")

	def test_missing_field_excluded(self):
		"""Missing fields should not appear in resolved output."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "nonexistent_field",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "last_name": "Smith"}}
		resolver._resolve_elements()

		self.assertNotIn("Patient.name.family", resolver.resolved_values)

	def test_empty_string_field_resolved(self):
		"""Empty string fields should be resolved (not excluded)."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "last_name",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "last_name": ""}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.name.family"], "")

	def test_zero_value_resolved(self):
		"""Zero values should be resolved (not treated as null)."""
		compiled = make_compiled_map(
			elements={
				"Observation.valueQuantity.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "measurement",
					},
					"datatype": "decimal",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "measurement": 0}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Observation.valueQuantity.value"], 0.0)

	def test_false_boolean_resolved(self):
		"""False boolean values should be resolved (not treated as null)."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "is_active",
					},
					"datatype": "boolean",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "is_active": False}}
		resolver._resolve_elements()

		self.assertIs(resolver.resolved_values["Patient.active"], False)

	def test_missing_source_key_excluded(self):
		"""Elements with missing source_key should be excluded."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"value_spec": {
						"kind": "field",
						"source_key": "nonexistent_source",
						"fieldname": "last_name",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "last_name": "Smith"}}
		resolver._resolve_elements()

		self.assertNotIn("Patient.name.family", resolver.resolved_values)


# =========================================================
# Dot Notation Field Access Tests
# =========================================================


class TestDotNotationFieldAccess(IntegrationTestCase):
	"""Tests for nested field access using dot notation."""

	def test_single_level_nested_field(self):
		"""Single level nested fields should resolve correctly."""
		compiled = make_compiled_map(
			elements={
				"Patient.address.city": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "address.city",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {
			"primary": {
				"name": "dummy",
				"address": {"city": "New York", "state": "NY"},
			}
		}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.address.city"], "New York")

	def test_multi_level_nested_field(self):
		"""Multi-level nested fields should resolve correctly."""
		compiled = make_compiled_map(
			elements={
				"Patient.contact.address.city": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "emergency_contact.address.city",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {
			"primary": {
				"name": "dummy",
				"emergency_contact": {
					"name": "Jane",
					"address": {"city": "Boston", "state": "MA"},
				},
			}
		}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.contact.address.city"], "Boston")

	def test_missing_intermediate_field(self):
		"""Missing intermediate fields should result in exclusion."""
		compiled = make_compiled_map(
			elements={
				"Patient.address.city": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "address.city",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertNotIn("Patient.address.city", resolver.resolved_values)

	def test_null_intermediate_field(self):
		"""Null intermediate fields should result in exclusion."""
		compiled = make_compiled_map(
			elements={
				"Patient.address.city": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "address.city",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "address": None}}
		resolver._resolve_elements()

		self.assertNotIn("Patient.address.city", resolver.resolved_values)


# =========================================================
# Child Table Resolution Tests
# =========================================================


class TestChildTableResolution(IntegrationTestCase):
	"""Tests for resolving values from child tables (list of dicts)."""

	def test_child_table_single_field(self):
		"""Single field from child table should return list of values."""
		compiled = make_compiled_map(
			elements={
				"Patient.telecom.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "phone_numbers.number",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {
			"primary": {
				"name": "dummy",
				"phone_numbers": [
					{"number": "555-1234", "type": "home"},
					{"number": "555-5678", "type": "work"},
				],
			}
		}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.telecom.value"], ["555-1234", "555-5678"])

	def test_child_table_with_none_values(self):
		"""Child table with some None values should filter them out."""
		compiled = make_compiled_map(
			elements={
				"Patient.telecom.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "phone_numbers.number",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {
			"primary": {
				"name": "dummy",
				"phone_numbers": [
					{"number": "555-1234", "type": "home"},
					{"number": None, "type": "work"},
					{"type": "mobile"},  # number field missing entirely
				],
			}
		}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.telecom.value"], ["555-1234"])

	def test_empty_child_table_excluded(self):
		"""Empty child tables should result in exclusion."""
		compiled = make_compiled_map(
			elements={
				"Patient.telecom.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "phone_numbers.number",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {
			"primary": {
				"name": "dummy",
				"phone_numbers": [],
			}
		}
		resolver._resolve_elements()

		self.assertNotIn("Patient.telecom.value", resolver.resolved_values)

	def test_child_table_all_none_excluded(self):
		"""Child table where all values are None should be excluded."""
		compiled = make_compiled_map(
			elements={
				"Patient.telecom.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "phone_numbers.number",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {
			"primary": {
				"name": "dummy",
				"phone_numbers": [
					{"number": None},
					{"type": "work"},
				],
			}
		}
		resolver._resolve_elements()

		self.assertNotIn("Patient.telecom.value", resolver.resolved_values)

	def test_nested_child_table_field(self):
		"""Nested field within child table rows should resolve correctly."""
		compiled = make_compiled_map(
			elements={
				"Patient.contact.address.city": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "contacts.address.city",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {
			"primary": {
				"name": "dummy",
				"contacts": [
					{"name": "Jane", "address": {"city": "Boston"}},
					{"name": "John", "address": {"city": "Chicago"}},
				],
			}
		}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.contact.address.city"], ["Boston", "Chicago"])


# =========================================================
# Reverse Link Source Tests
# =========================================================


class TestReverseLinkResolution(IntegrationTestCase):
	"""Tests for resolving values from reverse link sources."""

	def test_reverse_link_single_field(self):
		"""Reverse link source should return list of values from linked docs."""
		sources = {
			"primary": {"kind": "primary", "doctype": "Patient"},
			"encounters": {
				"kind": "reverse_link",
				"doctype": "Encounter",
				"link_fieldname": "patient",
			},
		}
		compiled = make_compiled_map(
			sources=sources,
			elements={
				"Encounter.status": {
					"value_spec": {
						"kind": "field",
						"source_key": "encounters",
						"fieldname": "status",
					},
					"datatype": "code",
				}
			},
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {
			"primary": {"name": "PAT-001"},
			"encounters": [
				{"name": "ENC-001", "status": "finished"},
				{"name": "ENC-002", "status": "in-progress"},
			],
		}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Encounter.status"], ["finished", "in-progress"])

	def test_reverse_link_empty_list(self):
		"""Empty reverse link should result in exclusion."""
		sources = {
			"primary": {"kind": "primary", "doctype": "Patient"},
			"encounters": {
				"kind": "reverse_link",
				"doctype": "Encounter",
				"link_fieldname": "patient",
			},
		}
		compiled = make_compiled_map(
			sources=sources,
			elements={
				"Encounter.status": {
					"value_spec": {
						"kind": "field",
						"source_key": "encounters",
						"fieldname": "status",
					},
					"datatype": "code",
				}
			},
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {
			"primary": {"name": "PAT-001"},
			"encounters": [],
		}
		resolver._resolve_elements()

		self.assertNotIn("Encounter.status", resolver.resolved_values)

	def test_reverse_link_with_child_tables(self):
		"""Reverse link docs with child tables should flatten values."""
		sources = {
			"primary": {"kind": "primary", "doctype": "Patient"},
			"encounters": {
				"kind": "reverse_link",
				"doctype": "Encounter",
				"link_fieldname": "patient",
			},
		}
		compiled = make_compiled_map(
			sources=sources,
			elements={
				"Encounter.diagnosis.code": {
					"value_spec": {
						"kind": "field",
						"source_key": "encounters",
						"fieldname": "diagnoses.code",
					},
					"datatype": "code",
				}
			},
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {
			"primary": {"name": "PAT-001"},
			"encounters": [
				{
					"name": "ENC-001",
					"diagnoses": [
						{"code": "J06.9"},
						{"code": "R50.9"},
					],
				},
				{
					"name": "ENC-002",
					"diagnoses": [
						{"code": "K21.0"},
					],
				},
			],
		}
		resolver._resolve_elements()

		self.assertEqual(
			resolver.resolved_values["Encounter.diagnosis.code"],
			["j06.9", "r50.9", "k21.0"],  # Note: code type lowercases
		)


# =========================================================
# Type Coercion Tests
# =========================================================


class TestTypeCoercion(IntegrationTestCase):
	"""Tests for FHIR datatype coercion."""

	def test_coerce_to_boolean_from_string_true(self):
		"""String 'true' should coerce to boolean True."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "is_active",
					},
					"datatype": "boolean",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "is_active": "true"}}
		resolver._resolve_elements()

		self.assertIs(resolver.resolved_values["Patient.active"], True)

	def test_coerce_to_boolean_from_string_yes(self):
		"""String 'yes' should coerce to boolean True."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "is_active",
					},
					"datatype": "boolean",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "is_active": "yes"}}
		resolver._resolve_elements()

		self.assertIs(resolver.resolved_values["Patient.active"], True)

	def test_coerce_to_boolean_from_string_1(self):
		"""String '1' should coerce to boolean True."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "is_active",
					},
					"datatype": "boolean",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "is_active": "1"}}
		resolver._resolve_elements()

		self.assertIs(resolver.resolved_values["Patient.active"], True)

	def test_coerce_to_boolean_from_string_false(self):
		"""String 'false' should coerce to boolean False."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "is_active",
					},
					"datatype": "boolean",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "is_active": "false"}}
		resolver._resolve_elements()

		self.assertIs(resolver.resolved_values["Patient.active"], False)

	def test_coerce_to_boolean_from_int_1(self):
		"""Integer 1 should coerce to boolean True."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "is_active",
					},
					"datatype": "boolean",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "is_active": 1}}
		resolver._resolve_elements()

		self.assertIs(resolver.resolved_values["Patient.active"], True)

	def test_coerce_to_boolean_from_int_0(self):
		"""Integer 0 should coerce to boolean False."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "is_active",
					},
					"datatype": "boolean",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "is_active": 0}}
		resolver._resolve_elements()

		self.assertIs(resolver.resolved_values["Patient.active"], False)

	def test_coerce_to_integer(self):
		"""String number should coerce to integer."""
		compiled = make_compiled_map(
			elements={
				"Patient.multipleBirthInteger": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "birth_order",
					},
					"datatype": "integer",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "birth_order": "3"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.multipleBirthInteger"], 3)
		self.assertIsInstance(resolver.resolved_values["Patient.multipleBirthInteger"], int)

	def test_coerce_to_decimal(self):
		"""String number should coerce to decimal (float)."""
		compiled = make_compiled_map(
			elements={
				"Observation.valueQuantity.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "temperature",
					},
					"datatype": "decimal",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "temperature": "98.6"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Observation.valueQuantity.value"], 98.6)
		self.assertIsInstance(resolver.resolved_values["Observation.valueQuantity.value"], float)

	def test_coerce_to_code_lowercase(self):
		"""Code values should be lowercased and stripped."""
		compiled = make_compiled_map(
			elements={
				"Patient.gender": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "sex",
					},
					"datatype": "code",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "sex": "  Male  "}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.gender"], "male")

	def test_coerce_to_string(self):
		"""Non-string values should coerce to string."""
		compiled = make_compiled_map(
			elements={
				"Patient.identifier.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "patient_id",
					},
					"datatype": "string",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "patient_id": 12345}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.identifier.value"], "12345")
		self.assertIsInstance(resolver.resolved_values["Patient.identifier.value"], str)

	def test_coerce_date_to_string(self):
		"""Date values should be stringified."""
		from datetime import date

		compiled = make_compiled_map(
			elements={
				"Patient.birthDate": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "dob",
					},
					"datatype": "date",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "dob": date(1990, 5, 15)}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.birthDate"], "1990-05-15")

	def test_coerce_to_reference_wrapper(self):
		"""Reference datatype should wrap value in display."""
		compiled = make_compiled_map(
			elements={
				"Patient.generalPractitioner": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "practitioner_name",
					},
					"datatype": "Reference",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "practitioner_name": "Dr. Smith"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.generalPractitioner"], {"display": "Dr. Smith"})

	def test_coerce_to_codeable_concept_wrapper(self):
		"""CodeableConcept datatype should wrap value in text."""
		compiled = make_compiled_map(
			elements={
				"Patient.maritalStatus": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "marital_status",
					},
					"datatype": "CodeableConcept",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "marital_status": "Married"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.maritalStatus"], {"text": "Married"})

	def test_no_datatype_preserves_value(self):
		"""Missing datatype should preserve original value."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "last_name",
					},
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "last_name": "Smith"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.name.family"], "Smith")

	def test_invalid_integer_coercion_preserves_value(self):
		"""Invalid integer coercion should preserve original value."""
		compiled = make_compiled_map(
			elements={
				"Patient.multipleBirthInteger": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "birth_order",
					},
					"datatype": "integer",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "birth_order": "not a number"}}
		resolver._resolve_elements()

		self.assertEqual(resolver.resolved_values["Patient.multipleBirthInteger"], "not a number")

	def test_comma_separated_datatype_uses_first(self):
		"""Comma-separated datatypes should use first type for coercion."""
		compiled = make_compiled_map(
			elements={
				"Patient.deceased": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "is_deceased",
					},
					"datatype": "boolean, dateTime",
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "is_deceased": "true"}}
		resolver._resolve_elements()

		self.assertIs(resolver.resolved_values["Patient.deceased"], True)


# =========================================================
# Element Order Tests
# =========================================================


class TestElementOrder(IntegrationTestCase):
	"""Tests for element resolution order."""

	def test_elements_resolved_in_specified_order(self):
		"""Elements should be resolved in element_order sequence."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"value_spec": {"kind": "fixed", "value": "Smith"},
				},
				"Patient.active": {
					"value_spec": {"kind": "fixed", "value": True},
				},
				"Patient.gender": {
					"value_spec": {"kind": "fixed", "value": "male"},
				},
			},
			element_order=["Patient.active", "Patient.gender", "Patient.name.family"],
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()
		result = resolver.resolved_values

		# All elements should be resolved
		self.assertEqual(len(result), 3)
		self.assertIn("Patient.name.family", result)
		self.assertIn("Patient.active", result)
		self.assertIn("Patient.gender", result)

	def test_missing_element_order_uses_keys(self):
		"""Missing element_order should use elements dict keys."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {"kind": "fixed", "value": True},
				},
			},
			element_order=None,
		)
		compiled.pop("element_order", None)

		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()
		result = resolver.resolved_values

		self.assertEqual(result["Patient.active"], True)


# =========================================================
# Validation Tests
# =========================================================


class TestRequiredValidation(IntegrationTestCase):
	"""Tests for required element validation."""

	def test_missing_required_element_error(self):
		"""Missing required element should generate error."""
		compiled = make_compiled_map(
			elements={
				"Patient.identifier.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "patient_id",
					},
					"min": 1,
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}  # No patient_id
		resolver._resolve_elements()

		errors = resolver.validate_required()

		self.assertEqual(len(errors), 1)
		self.assertEqual(errors[0]["type"], "missing_required")
		self.assertEqual(errors[0]["path"], "Patient.identifier.value")

	def test_present_required_element_no_error(self):
		"""Present required element should not generate error."""
		compiled = make_compiled_map(
			elements={
				"Patient.identifier.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "patient_id",
					},
					"min": 1,
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "patient_id": "PAT-001"}}
		resolver._resolve_elements()

		errors = resolver.validate_required()

		self.assertEqual(len(errors), 0)

	def test_empty_list_required_element_error(self):
		"""Empty list for required element should generate error."""
		compiled = make_compiled_map(
			elements={
				"Patient.identifier.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "identifiers.value",
					},
					"min": 1,
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "identifiers": []}}
		resolver._resolve_elements()

		errors = resolver.validate_required()

		self.assertEqual(len(errors), 1)

	def test_optional_element_no_error(self):
		"""Missing optional element (min=0) should not generate error."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "last_name",
					},
					"min": 0,
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}  # No last_name
		resolver._resolve_elements()

		errors = resolver.validate_required()

		self.assertEqual(len(errors), 0)

	def test_multiple_missing_required_elements(self):
		"""Multiple missing required elements should generate multiple errors."""
		compiled = make_compiled_map(
			elements={
				"Patient.identifier.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "patient_id",
					},
					"min": 1,
				},
				"Patient.name.family": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "last_name",
					},
					"min": 1,
				},
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		errors = resolver.validate_required()

		self.assertEqual(len(errors), 2)
		paths = [e["path"] for e in errors]
		self.assertIn("Patient.identifier.value", paths)
		self.assertIn("Patient.name.family", paths)


# =========================================================
# Accessor Method Tests
# =========================================================


class TestAccessorMethods(IntegrationTestCase):
	"""Tests for resolver accessor methods."""

	def test_get_source_returns_loaded_source(self):
		"""get_source should return loaded source document."""
		compiled = make_compiled_map()
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "field": "value"}}

		source = resolver.get_source("primary")

		self.assertEqual(source["name"], "dummy")
		self.assertEqual(source["field"], "value")

	def test_get_source_returns_none_for_missing(self):
		"""get_source should return None for missing source."""
		compiled = make_compiled_map()
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}

		source = resolver.get_source("nonexistent")

		self.assertIsNone(source)

	def test_get_value_returns_resolved_value(self):
		"""get_value should return resolved value."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {"kind": "fixed", "value": True},
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		value = resolver.get_value("Patient.active")

		self.assertIs(value, True)

	def test_get_value_returns_none_for_missing(self):
		"""get_value should return None for missing element."""
		compiled = make_compiled_map()
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		value = resolver.get_value("Patient.nonexistent")

		self.assertIsNone(value)


# =========================================================
# Edge Cases and Error Handling Tests
# =========================================================


class TestEdgeCases(IntegrationTestCase):
	"""Tests for edge cases and error handling."""

	def test_empty_compiled_map(self):
		"""Empty compiled map should return empty result."""
		resolver = FHIRValueResolver({}, "dummy")
		result = resolver.resolve()

		self.assertEqual(result, {})

	def test_none_compiled_map(self):
		"""None compiled map should return empty result."""
		resolver = FHIRValueResolver(None, "dummy")
		result = resolver.resolve()

		self.assertEqual(result, {})

	def test_empty_elements(self):
		"""Empty elements should return empty result."""
		compiled = make_compiled_map(elements={})
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		result = resolver.resolve()

		self.assertEqual(result, {})

	def test_unsupported_value_spec_kind(self):
		"""Unsupported value_spec kind should be excluded."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {
					"value_spec": {"kind": "unsupported_kind", "value": True},
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertNotIn("Patient.active", resolver.resolved_values)

	def test_missing_value_spec(self):
		"""Missing value_spec should be excluded."""
		compiled = make_compiled_map(elements={"Patient.active": {}})
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertNotIn("Patient.active", resolver.resolved_values)

	def test_none_value_spec(self):
		"""None value_spec should be excluded."""
		compiled = make_compiled_map(elements={"Patient.active": {"value_spec": None}})
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()

		self.assertNotIn("Patient.active", resolver.resolved_values)

	def test_field_spec_missing_source_key(self):
		"""Field spec missing source_key should be excluded."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"value_spec": {
						"kind": "field",
						"fieldname": "last_name",
					},
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "last_name": "Smith"}}
		resolver._resolve_elements()

		self.assertNotIn("Patient.name.family", resolver.resolved_values)

	def test_field_spec_missing_fieldname(self):
		"""Field spec missing fieldname should be excluded."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
					},
				}
			}
		)
		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy", "last_name": "Smith"}}
		resolver._resolve_elements()

		self.assertNotIn("Patient.name.family", resolver.resolved_values)


# =========================================================
# Integration Tests
# =========================================================


class TestResolverIntegration(IntegrationTestCase):
	"""Integration tests for complete resolution scenarios."""

	def test_complete_patient_resolution(self):
		"""Test realistic Patient resource resolution."""
		compiled = make_compiled_map(
			resource_type="Patient",
			primary_doctype="Patient",
			elements={
				"Patient.active": {
					"value_spec": {"kind": "fixed", "value": True},
					"datatype": "boolean",
				},
				"Patient.name.family": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "last_name",
					},
					"datatype": "string",
				},
				"Patient.name.given": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "first_name",
					},
					"datatype": "string",
				},
				"Patient.gender": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "sex",
					},
					"datatype": "code",
				},
				"Patient.birthDate": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "dob",
					},
					"datatype": "date",
				},
			},
			element_order=[
				"Patient.active",
				"Patient.birthDate",
				"Patient.gender",
				"Patient.name.family",
				"Patient.name.given",
			],
		)

		resolver = FHIRValueResolver(compiled, "PAT-001")
		resolver.source_data = {
			"primary": {
				"name": "PAT-001",
				"first_name": "John",
				"last_name": "Doe",
				"sex": "Male",
				"dob": "1990-05-15",
			}
		}
		resolver._resolve_elements()
		result = resolver.resolved_values

		expected = {
			"Patient.active": True,
			"Patient.name.family": "Doe",
			"Patient.name.given": "John",
			"Patient.gender": "male",
			"Patient.birthDate": "1990-05-15",
		}
		self.assertEqual(result, expected)

	def test_mixed_fixed_and_field_values(self):
		"""Test resolution with mixed fixed and field values."""
		compiled = make_compiled_map(
			elements={
				"Observation.status": {
					"value_spec": {"kind": "fixed", "value": "final"},
					"datatype": "code",
				},
				"Observation.valueQuantity.value": {
					"value_spec": {
						"kind": "field",
						"source_key": "primary",
						"fieldname": "measurement",
					},
					"datatype": "decimal",
				},
				"Observation.valueQuantity.unit": {
					"value_spec": {"kind": "fixed", "value": "kg"},
					"datatype": "string",
				},
			}
		)

		resolver = FHIRValueResolver(compiled, "OBS-001")
		resolver.source_data = {
			"primary": {
				"name": "OBS-001",
				"measurement": 75.5,
			}
		}
		resolver._resolve_elements()
		result = resolver.resolved_values

		self.assertEqual(result["Observation.status"], "final")
		self.assertEqual(result["Observation.valueQuantity.value"], 75.5)
		self.assertEqual(result["Observation.valueQuantity.unit"], "kg")

	def test_resolution_output_is_flat_dict(self):
		"""Verify resolver output is flat dict, not nested."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"value_spec": {"kind": "fixed", "value": "Doe"},
				},
				"Patient.name.given": {
					"value_spec": {"kind": "fixed", "value": "John"},
				},
				"Patient.address.city": {
					"value_spec": {"kind": "fixed", "value": "Boston"},
				},
			}
		)

		resolver = FHIRValueResolver(compiled, "dummy")
		resolver.source_data = {"primary": {"name": "dummy"}}
		resolver._resolve_elements()
		result = resolver.resolved_values

		# Should be flat keys, not nested structure
		self.assertIn("Patient.name.family", result)
		self.assertIn("Patient.name.given", result)
		self.assertIn("Patient.address.city", result)

		# Values should be simple, not nested
		self.assertEqual(result["Patient.name.family"], "Doe")
		self.assertEqual(result["Patient.name.given"], "John")
		self.assertEqual(result["Patient.address.city"], "Boston")

		# Should NOT have nested structure
		self.assertNotIn("Patient", result)
		self.assertNotIn("name", result)
