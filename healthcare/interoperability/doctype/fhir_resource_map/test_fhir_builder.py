"""
Tests for FHIR Resource Builder

These tests verify the key improvement: proper handling of primitive arrays vs backbone arrays.

Key behaviors:
1. is_array=True + list value → collect into array at path (primitive arrays like `given`)
2. is_array=False + list value → spread across parent indexes (backbone arrays like `name`)
3. Single values work regardless of is_array flag
"""

import frappe
from frappe.tests import IntegrationTestCase

from healthcare.interoperability.doctype.fhir_resource_map.builder import (
	FHIRResourceBuilder,
	FHIRResourceCleaner,
	build_fhir_resource,
)


def make_compiled_map(
	resource_type="Patient",
	elements=None,
	element_order=None,
	meta_id=None,
):
	"""Factory to create compiled map structure for testing."""
	meta = {"resource_type": resource_type}
	if meta_id:
		meta["id"] = meta_id

	return {
		"compiled_version": "fhir-map-compiled/v1",
		"meta": meta,
		"elements": elements or {},
		"element_order": element_order or list((elements or {}).keys()),
	}


# =========================================================
# Primitive Array Collection Tests (is_array=True)
# =========================================================


class TestPrimitiveArrayCollection(IntegrationTestCase):
	"""Tests for is_array=True - collecting list values into arrays."""

	def test_collect_given_names_into_array(self):
		"""Given names should collect into single array within name object."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.given": {
					"path": "name[0].given[0]",
					"is_array": True,
				}
			}
		)

		resolved = {"Patient.name.given": ["John", "William", "Robert"]}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(result["name"][0]["given"], ["John", "William", "Robert"])

	def test_collect_address_lines_into_array(self):
		"""Address lines should collect into array."""
		compiled = make_compiled_map(
			elements={
				"Patient.address.line": {
					"path": "address[0].line[0]",
					"is_array": True,
				}
			}
		)

		resolved = {"Patient.address.line": ["123 Main St", "Apt 4B"]}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(result["address"][0]["line"], ["123 Main St", "Apt 4B"])

	def test_collect_preserves_parent_structure(self):
		"""Collecting primitives should work alongside scalar values."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"path": "name[0].family",
					"is_array": False,
				},
				"Patient.name.given": {
					"path": "name[0].given[0]",
					"is_array": True,
				},
			}
		)

		resolved = {
			"Patient.name.family": "Smith",
			"Patient.name.given": ["John", "William"],
		}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(result["name"][0]["family"], "Smith")
		self.assertEqual(result["name"][0]["given"], ["John", "William"])

	def test_collect_single_value_with_is_array_true(self):
		"""Single value with is_array=True should be wrapped in array (correct FHIR behavior)."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.given": {
					"path": "name[0].given[0]",
					"is_array": True,
				}
			}
		)

		resolved = {
			"Patient.name.given": "John"  # Single value, not list
		}

		result = build_fhir_resource(compiled, resolved)

		# Single value should be wrapped in array (given is always array in FHIR)
		self.assertEqual(result["name"][0]["given"], ["John"])

	def test_collect_prefix_suffix_arrays(self):
		"""Name prefix and suffix should also collect."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.prefix": {
					"path": "name[0].prefix[0]",
					"is_array": True,
				},
				"Patient.name.suffix": {
					"path": "name[0].suffix[0]",
					"is_array": True,
				},
			}
		)

		resolved = {
			"Patient.name.prefix": ["Dr", "Prof"],
			"Patient.name.suffix": ["MD", "PhD"],
		}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(result["name"][0]["prefix"], ["Dr", "Prof"])
		self.assertEqual(result["name"][0]["suffix"], ["MD", "PhD"])


# =========================================================
# Backbone Array Spreading Tests (is_array=False)
# =========================================================


class TestBackboneArraySpreading(IntegrationTestCase):
	"""Tests for is_array=False - spreading list values across container indexes."""

	def test_spread_telecom_values(self):
		"""Telecom values should spread across telecom[0], telecom[1], etc."""
		compiled = make_compiled_map(
			elements={
				"Patient.telecom.value": {
					"path": "telecom[0].value",
					"is_array": False,
				}
			}
		)

		resolved = {"Patient.telecom.value": ["555-1234", "555-5678"]}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(len(result["telecom"]), 2)
		self.assertEqual(result["telecom"][0]["value"], "555-1234")
		self.assertEqual(result["telecom"][1]["value"], "555-5678")

	def test_spread_multiple_fields_align(self):
		"""Multiple fields should align by index when spread."""
		compiled = make_compiled_map(
			elements={
				"Patient.telecom.system": {
					"path": "telecom[0].system",
					"is_array": False,
				},
				"Patient.telecom.value": {
					"path": "telecom[0].value",
					"is_array": False,
				},
				"Patient.telecom.use": {
					"path": "telecom[0].use",
					"is_array": False,
				},
			}
		)

		resolved = {
			"Patient.telecom.system": ["phone", "email"],
			"Patient.telecom.value": ["555-1234", "test@example.com"],
			"Patient.telecom.use": ["home", "work"],
		}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(len(result["telecom"]), 2)

		self.assertEqual(result["telecom"][0]["system"], "phone")
		self.assertEqual(result["telecom"][0]["value"], "555-1234")
		self.assertEqual(result["telecom"][0]["use"], "home")

		self.assertEqual(result["telecom"][1]["system"], "email")
		self.assertEqual(result["telecom"][1]["value"], "test@example.com")
		self.assertEqual(result["telecom"][1]["use"], "work")

	def test_spread_identifiers(self):
		"""Identifiers should spread correctly."""
		compiled = make_compiled_map(
			elements={
				"Patient.identifier.system": {
					"path": "identifier[0].system",
					"is_array": False,
				},
				"Patient.identifier.value": {
					"path": "identifier[0].value",
					"is_array": False,
				},
			}
		)

		resolved = {
			"Patient.identifier.system": ["http://hospital.org/mrn", "http://govt.org/ssn"],
			"Patient.identifier.value": ["12345", "999-99-9999"],
		}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(len(result["identifier"]), 2)
		self.assertEqual(result["identifier"][0]["system"], "http://hospital.org/mrn")
		self.assertEqual(result["identifier"][0]["value"], "12345")
		self.assertEqual(result["identifier"][1]["system"], "http://govt.org/ssn")
		self.assertEqual(result["identifier"][1]["value"], "999-99-9999")

	def test_default_is_array_false(self):
		"""Missing is_array should default to False (spread behavior)."""
		compiled = make_compiled_map(
			elements={
				"Patient.telecom.value": {
					"path": "telecom[0].value",
					# No is_array specified
				}
			}
		)

		resolved = {"Patient.telecom.value": ["555-1234", "555-5678"]}

		result = build_fhir_resource(compiled, resolved)

		# Should spread, not collect
		self.assertEqual(len(result["telecom"]), 2)
		self.assertEqual(result["telecom"][0]["value"], "555-1234")
		self.assertEqual(result["telecom"][1]["value"], "555-5678")

	def test_spread_names(self):
		"""Multiple name entries should spread across name array."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.use": {
					"path": "name[0].use",
					"is_array": False,
				},
				"Patient.name.family": {
					"path": "name[0].family",
					"is_array": False,
				},
			}
		)

		resolved = {
			"Patient.name.use": ["official", "nickname"],
			"Patient.name.family": ["Smith", "Smitty"],
		}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(len(result["name"]), 2)
		self.assertEqual(result["name"][0]["use"], "official")
		self.assertEqual(result["name"][0]["family"], "Smith")
		self.assertEqual(result["name"][1]["use"], "nickname")
		self.assertEqual(result["name"][1]["family"], "Smitty")


# =========================================================
# Mixed Array Handling Tests
# =========================================================


class TestMixedArrayHandling(IntegrationTestCase):
	"""Tests for mixed primitive and backbone arrays in same resource."""

	def test_complete_patient_name(self):
		"""Complete name with scalar fields and primitive array fields."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.use": {
					"path": "name[0].use",
					"is_array": False,
				},
				"Patient.name.family": {
					"path": "name[0].family",
					"is_array": False,
				},
				"Patient.name.given": {
					"path": "name[0].given[0]",
					"is_array": True,
				},
				"Patient.name.prefix": {
					"path": "name[0].prefix[0]",
					"is_array": True,
				},
			}
		)

		resolved = {
			"Patient.name.use": "official",
			"Patient.name.family": "Smith",
			"Patient.name.given": ["John", "William"],
			"Patient.name.prefix": ["Dr"],
		}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(result["name"][0]["use"], "official")
		self.assertEqual(result["name"][0]["family"], "Smith")
		self.assertEqual(result["name"][0]["given"], ["John", "William"])
		self.assertEqual(result["name"][0]["prefix"], ["Dr"])

	def test_complete_address(self):
		"""Complete address with line array and scalar fields."""
		compiled = make_compiled_map(
			elements={
				"Patient.address.use": {
					"path": "address[0].use",
					"is_array": False,
				},
				"Patient.address.line": {
					"path": "address[0].line[0]",
					"is_array": True,
				},
				"Patient.address.city": {
					"path": "address[0].city",
					"is_array": False,
				},
				"Patient.address.state": {
					"path": "address[0].state",
					"is_array": False,
				},
				"Patient.address.postalCode": {
					"path": "address[0].postalCode",
					"is_array": False,
				},
			}
		)

		resolved = {
			"Patient.address.use": "home",
			"Patient.address.line": ["123 Main St", "Suite 100"],
			"Patient.address.city": "Boston",
			"Patient.address.state": "MA",
			"Patient.address.postalCode": "02101",
		}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(result["address"][0]["use"], "home")
		self.assertEqual(result["address"][0]["line"], ["123 Main St", "Suite 100"])
		self.assertEqual(result["address"][0]["city"], "Boston")
		self.assertEqual(result["address"][0]["state"], "MA")
		self.assertEqual(result["address"][0]["postalCode"], "02101")

	def test_observation_with_components(self):
		"""Observation with component spreading and value arrays."""
		compiled = make_compiled_map(
			resource_type="Observation",
			elements={
				"Observation.component.code.text": {
					"path": "component[0].code.text",
					"is_array": False,
				},
				"Observation.component.valueQuantity.value": {
					"path": "component[0].valueQuantity.value",
					"is_array": False,
				},
				"Observation.component.valueQuantity.unit": {
					"path": "component[0].valueQuantity.unit",
					"is_array": False,
				},
			},
		)

		resolved = {
			"Observation.component.code.text": ["Systolic", "Diastolic"],
			"Observation.component.valueQuantity.value": [120, 80],
			"Observation.component.valueQuantity.unit": ["mmHg", "mmHg"],
		}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(len(result["component"]), 2)
		self.assertEqual(result["component"][0]["code"]["text"], "Systolic")
		self.assertEqual(result["component"][0]["valueQuantity"]["value"], 120)
		self.assertEqual(result["component"][1]["code"]["text"], "Diastolic")
		self.assertEqual(result["component"][1]["valueQuantity"]["value"], 80)


# =========================================================
# Single Value Handling Tests
# =========================================================


class TestSingleValueHandling(IntegrationTestCase):
	"""Tests for single (non-list) values."""

	def test_single_value_with_is_array_true(self):
		"""Single value should be wrapped in array with is_array=True."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.given": {
					"path": "name[0].given[0]",
					"is_array": True,
				}
			}
		)

		resolved = {"Patient.name.given": "John"}

		result = build_fhir_resource(compiled, resolved)

		# Single value wrapped in array (correct FHIR behavior)
		self.assertEqual(result["name"][0]["given"], ["John"])

	def test_single_value_with_is_array_false(self):
		"""Single value should work with is_array=False."""
		compiled = make_compiled_map(
			elements={
				"Patient.telecom.value": {
					"path": "telecom[0].value",
					"is_array": False,
				}
			}
		)

		resolved = {"Patient.telecom.value": "555-1234"}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(result["telecom"][0]["value"], "555-1234")

	def test_simple_scalar_fields(self):
		"""Simple scalar fields without array paths."""
		compiled = make_compiled_map(
			elements={
				"Patient.active": {"path": "active", "is_array": False},
				"Patient.gender": {"path": "gender", "is_array": False},
				"Patient.birthDate": {"path": "birthDate", "is_array": False},
			}
		)

		resolved = {
			"Patient.active": True,
			"Patient.gender": "male",
			"Patient.birthDate": "1990-01-15",
		}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(result["active"], True)
		self.assertEqual(result["gender"], "male")
		self.assertEqual(result["birthDate"], "1990-01-15")


# =========================================================
# Edge Cases
# =========================================================


class TestEdgeCases(IntegrationTestCase):
	"""Tests for edge cases and boundary conditions."""

	def test_empty_list_creates_nothing(self):
		"""Empty list should not create array."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.given": {
					"path": "name[0].given[0]",
					"is_array": True,
				}
			}
		)

		resolved = {"Patient.name.given": []}

		result = build_fhir_resource(compiled, resolved)

		# Empty list cleaned up
		self.assertNotIn("name", result)

	def test_none_value_skipped(self):
		"""None values should be skipped."""
		compiled = make_compiled_map(
			elements={
				"Patient.name.family": {
					"path": "name[0].family",
					"is_array": False,
				}
			}
		)

		resolved = {"Patient.name.family": None}

		result = build_fhir_resource(compiled, resolved)

		self.assertNotIn("name", result)

	def test_dict_value_merged(self):
		"""Dict values should be merged into container."""
		compiled = make_compiled_map(
			elements={
				"Patient.name": {
					"path": "name[0]",
					"is_array": False,
				}
			}
		)

		resolved = {"Patient.name": {"family": "Smith", "given": ["John"]}}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(result["name"][0]["family"], "Smith")
		self.assertEqual(result["name"][0]["given"], ["John"])

	def test_nested_array_paths(self):
		"""Paths with multiple array indexes."""
		compiled = make_compiled_map(
			elements={
				"Patient.contact.name.given": {
					"path": "contact[0].name.given[0]",
					"is_array": True,
				}
			}
		)

		resolved = {"Patient.contact.name.given": ["Jane", "Mary"]}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(result["contact"][0]["name"]["given"], ["Jane", "Mary"])

	def test_deeply_nested_path(self):
		"""Deeply nested path structures - spreading happens at first array index."""
		compiled = make_compiled_map(
			elements={
				"Patient.contact.telecom.value": {
					"path": "contact[0].telecom[0].value",
					"is_array": False,
				}
			}
		)

		resolved = {"Patient.contact.telecom.value": ["555-1234", "555-5678"]}

		result = build_fhir_resource(compiled, resolved)

		# Spreading happens at first [0] (contact), so we get contact[0] and contact[1]
		# each with their own telecom[0]
		self.assertEqual(len(result["contact"]), 2)
		self.assertEqual(result["contact"][0]["telecom"][0]["value"], "555-1234")
		self.assertEqual(result["contact"][1]["telecom"][0]["value"], "555-5678")


# =========================================================
# Complete Resource Integration Tests
# =========================================================


class TestCompleteResources(IntegrationTestCase):
	"""Integration tests with complete FHIR resources."""

	def test_complete_patient(self):
		"""Complete Patient resource with multiple element types."""
		compiled = make_compiled_map(
			meta_id="patient-123",
			elements={
				"Patient.active": {"path": "active", "is_array": False},
				"Patient.gender": {"path": "gender", "is_array": False},
				"Patient.birthDate": {"path": "birthDate", "is_array": False},
				"Patient.name.use": {"path": "name[0].use", "is_array": False},
				"Patient.name.family": {"path": "name[0].family", "is_array": False},
				"Patient.name.given": {"path": "name[0].given[0]", "is_array": True},
				"Patient.telecom.system": {"path": "telecom[0].system", "is_array": False},
				"Patient.telecom.value": {"path": "telecom[0].value", "is_array": False},
				"Patient.telecom.use": {"path": "telecom[0].use", "is_array": False},
				"Patient.address.use": {"path": "address[0].use", "is_array": False},
				"Patient.address.line": {"path": "address[0].line[0]", "is_array": True},
				"Patient.address.city": {"path": "address[0].city", "is_array": False},
			},
		)

		resolved = {
			"Patient.active": True,
			"Patient.gender": "male",
			"Patient.birthDate": "1990-01-15",
			"Patient.name.use": "official",
			"Patient.name.family": "Smith",
			"Patient.name.given": ["John", "William"],
			"Patient.telecom.system": ["phone", "email"],
			"Patient.telecom.value": ["555-1234", "john@example.com"],
			"Patient.telecom.use": ["home", "work"],
			"Patient.address.use": "home",
			"Patient.address.line": ["123 Main St", "Apt 4B"],
			"Patient.address.city": "Boston",
		}

		result = build_fhir_resource(compiled, resolved)

		# Verify structure
		self.assertEqual(result["resourceType"], "Patient")
		self.assertEqual(result["id"], "patient-123")
		self.assertEqual(result["active"], True)
		self.assertEqual(result["gender"], "male")

		# Name with given array collected
		self.assertEqual(result["name"][0]["family"], "Smith")
		self.assertEqual(result["name"][0]["given"], ["John", "William"])

		# Telecom spread across entries
		self.assertEqual(len(result["telecom"]), 2)
		self.assertEqual(result["telecom"][0]["system"], "phone")
		self.assertEqual(result["telecom"][1]["system"], "email")

		# Address with line array collected
		self.assertEqual(result["address"][0]["line"], ["123 Main St", "Apt 4B"])
		self.assertEqual(result["address"][0]["city"], "Boston")

	def test_complete_observation(self):
		"""Complete Observation with component spreading."""
		compiled = make_compiled_map(
			resource_type="Observation",
			meta_id="obs-bp-001",
			elements={
				"Observation.status": {"path": "status", "is_array": False},
				"Observation.code.coding.system": {"path": "code.coding[0].system", "is_array": False},
				"Observation.code.coding.code": {"path": "code.coding[0].code", "is_array": False},
				"Observation.code.coding.display": {"path": "code.coding[0].display", "is_array": False},
				"Observation.component.code.text": {"path": "component[0].code.text", "is_array": False},
				"Observation.component.valueQuantity.value": {
					"path": "component[0].valueQuantity.value",
					"is_array": False,
				},
				"Observation.component.valueQuantity.unit": {
					"path": "component[0].valueQuantity.unit",
					"is_array": False,
				},
			},
		)

		resolved = {
			"Observation.status": "final",
			"Observation.code.coding.system": "http://loinc.org",
			"Observation.code.coding.code": "85354-9",
			"Observation.code.coding.display": "Blood pressure panel",
			"Observation.component.code.text": ["Systolic BP", "Diastolic BP"],
			"Observation.component.valueQuantity.value": [120, 80],
			"Observation.component.valueQuantity.unit": ["mmHg", "mmHg"],
		}

		result = build_fhir_resource(compiled, resolved)

		self.assertEqual(result["resourceType"], "Observation")
		self.assertEqual(result["status"], "final")
		self.assertEqual(result["code"]["coding"][0]["code"], "85354-9")

		# Components spread
		self.assertEqual(len(result["component"]), 2)
		self.assertEqual(result["component"][0]["code"]["text"], "Systolic BP")
		self.assertEqual(result["component"][0]["valueQuantity"]["value"], 120)
		self.assertEqual(result["component"][1]["code"]["text"], "Diastolic BP")
		self.assertEqual(result["component"][1]["valueQuantity"]["value"], 80)


# =========================================================
# Cleaner Tests
# =========================================================


class TestFHIRResourceCleaner(IntegrationTestCase):
	"""Tests for FHIRResourceCleaner."""

	def test_removes_none_values(self):
		"""Should remove None values."""
		cleaner = FHIRResourceCleaner()
		resource = {"name": None, "active": True}
		result = cleaner.clean(resource)
		self.assertEqual(result, {"active": True})

	def test_removes_empty_dicts(self):
		"""Should remove empty dicts."""
		cleaner = FHIRResourceCleaner()
		resource = {"name": {}, "active": True}
		result = cleaner.clean(resource)
		self.assertEqual(result, {"active": True})

	def test_removes_empty_lists(self):
		"""Should remove empty lists."""
		cleaner = FHIRResourceCleaner()
		resource = {"name": [], "active": True}
		result = cleaner.clean(resource)
		self.assertEqual(result, {"active": True})

	def test_recursive_cleaning(self):
		"""Should clean recursively."""
		cleaner = FHIRResourceCleaner()
		resource = {
			"name": [{"family": "Smith", "given": []}],
			"telecom": [{}],
			"active": True,
		}
		result = cleaner.clean(resource)
		self.assertEqual(
			result,
			{
				"name": [{"family": "Smith"}],
				"active": True,
			},
		)

	def test_preserves_valid_data(self):
		"""Should preserve valid data."""
		cleaner = FHIRResourceCleaner()
		resource = {
			"name": [{"family": "Smith", "given": ["John"]}],
			"active": True,
		}
		result = cleaner.clean(resource)
		self.assertEqual(result, resource)

	def test_remove_empty_strings_option(self):
		"""Should optionally remove empty strings."""
		cleaner = FHIRResourceCleaner(remove_empty_strings=True)
		resource = {"name": "", "active": True}
		result = cleaner.clean(resource)
		self.assertEqual(result, {"active": True})

	def test_keep_empty_strings_by_default(self):
		"""Should keep empty strings by default."""
		cleaner = FHIRResourceCleaner()
		resource = {"name": "", "active": True}
		result = cleaner.clean(resource)
		self.assertEqual(result, {"name": "", "active": True})
