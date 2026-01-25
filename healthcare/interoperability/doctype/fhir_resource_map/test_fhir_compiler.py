"""
Tests for FHIR Mapping Compiler - is_array Flag

These tests verify the compiler correctly sets the is_array flag on elements
to distinguish primitive arrays (collect) from backbone arrays (spread).

Key behaviors:
- is_array=True for primitive types (string, integer, etc.) with max="*"
- is_array=False for complex types (HumanName, Address, etc.) with max="*"
- is_array=False for any element with max="1" or no max
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from healthcare.interoperability.doctype.fhir_resource_map.compiler import (
	FHIRMappingCompilationError,
	FHIRMappingCompiler,
)


def make_mock_resource_map(
	primary_doctype="Patient",
	resource_type="Patient",
	base_structure_definition="",
	element_maps=None,
	sources=None,
	profiles=None,
):
	"""Create a mock resource map for testing."""
	mock = MagicMock()
	mock.primary_doctype = primary_doctype
	mock.resource_type = resource_type
	mock.base_structure_definition = base_structure_definition

	mock.get = MagicMock(
		side_effect=lambda key: {
			"element_maps": element_maps or [],
			"sources": sources or [],
			"profiles": profiles or [],
		}.get(key, [])
	)

	return mock


def make_element_map(
	fhir_path, datatype="string", max_card="1", min_card=0, source_key="primary", fieldname="test_field"
):
	"""Create an element map row for testing."""
	return {
		"fhir_path": fhir_path,
		"datatype": datatype,
		"max": max_card,
		"min": min_card,
		"value_pointer": {
			"kind": "field",
			"source_key": source_key,
			"fieldname": fieldname,
		},
	}


# =========================================================
# Primitive Array Tests (is_array=True expected)
# =========================================================


class TestPrimitiveArrayDetection(IntegrationTestCase):
	"""Tests for primitive types with max='*' -> is_array=True."""

	def test_string_array_is_array_true(self):
		"""String with max='*' should have is_array=True (e.g., given names)."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.name.given", datatype="string", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.name.given"]
		self.assertTrue(element["is_array"])

	def test_code_array_is_array_true(self):
		"""Code with max='*' should have is_array=True."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.communication.language.coding.code", datatype="code", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.communication.language.coding.code"]
		self.assertTrue(element["is_array"])

	def test_uri_array_is_array_true(self):
		"""URI with max='*' should have is_array=True."""
		resource_map = make_mock_resource_map(
			resource_type="CapabilityStatement",
			element_maps=[
				make_element_map("CapabilityStatement.instantiates", datatype="uri", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["CapabilityStatement.instantiates"]
		self.assertTrue(element["is_array"])

	def test_integer_array_is_array_true(self):
		"""Integer with max='*' should have is_array=True."""
		resource_map = make_mock_resource_map(
			resource_type="TestResource",
			element_maps=[
				make_element_map("TestResource.scores", datatype="integer", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["TestResource.scores"]
		self.assertTrue(element["is_array"])

	def test_decimal_array_is_array_true(self):
		"""Decimal with max='*' should have is_array=True."""
		resource_map = make_mock_resource_map(
			resource_type="TestResource",
			element_maps=[
				make_element_map("TestResource.measurements", datatype="decimal", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["TestResource.measurements"]
		self.assertTrue(element["is_array"])

	def test_boolean_array_is_array_true(self):
		"""Boolean with max='*' should have is_array=True."""
		resource_map = make_mock_resource_map(
			resource_type="TestResource",
			element_maps=[
				make_element_map("TestResource.flags", datatype="boolean", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["TestResource.flags"]
		self.assertTrue(element["is_array"])

	def test_date_array_is_array_true(self):
		"""Date with max='*' should have is_array=True."""
		resource_map = make_mock_resource_map(
			resource_type="TestResource",
			element_maps=[
				make_element_map("TestResource.importantDates", datatype="date", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["TestResource.importantDates"]
		self.assertTrue(element["is_array"])

	def test_datetime_array_is_array_true(self):
		"""DateTime with max='*' should have is_array=True."""
		resource_map = make_mock_resource_map(
			resource_type="TestResource",
			element_maps=[
				make_element_map("TestResource.timestamps", datatype="dateTime", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["TestResource.timestamps"]
		self.assertTrue(element["is_array"])

	def test_canonical_array_is_array_true(self):
		"""Canonical with max='*' should have is_array=True."""
		resource_map = make_mock_resource_map(
			resource_type="ImplementationGuide",
			element_maps=[
				make_element_map("ImplementationGuide.dependsOn.uri", datatype="canonical", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["ImplementationGuide.dependsOn.uri"]
		self.assertTrue(element["is_array"])

	def test_address_line_is_array_true(self):
		"""Address.line (string, 0..*) should have is_array=True."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.address.line", datatype="string", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.address.line"]
		self.assertTrue(element["is_array"])

	def test_name_prefix_is_array_true(self):
		"""HumanName.prefix (string, 0..*) should have is_array=True."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.name.prefix", datatype="string", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.name.prefix"]
		self.assertTrue(element["is_array"])

	def test_name_suffix_is_array_true(self):
		"""HumanName.suffix (string, 0..*) should have is_array=True."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.name.suffix", datatype="string", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.name.suffix"]
		self.assertTrue(element["is_array"])


# =========================================================
# Complex Type Array Tests (is_array=False expected)
# =========================================================


class TestComplexArrayDetection(IntegrationTestCase):
	"""Tests for complex types with max='*' -> is_array=False."""

	def test_human_name_array_is_array_false(self):
		"""HumanName with max='*' should have is_array=False (spread behavior)."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.name", datatype="HumanName", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.name"]
		self.assertFalse(element["is_array"])

	def test_address_array_is_array_false(self):
		"""Address with max='*' should have is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.address", datatype="Address", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.address"]
		self.assertFalse(element["is_array"])

	def test_contact_point_array_is_array_false(self):
		"""ContactPoint with max='*' should have is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.telecom", datatype="ContactPoint", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.telecom"]
		self.assertFalse(element["is_array"])

	def test_identifier_array_is_array_false(self):
		"""Identifier with max='*' should have is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.identifier", datatype="Identifier", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.identifier"]
		self.assertFalse(element["is_array"])

	def test_codeable_concept_array_is_array_false(self):
		"""CodeableConcept with max='*' should have is_array=False."""
		resource_map = make_mock_resource_map(
			resource_type="Condition",
			element_maps=[
				make_element_map("Condition.category", datatype="CodeableConcept", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Condition.category"]
		self.assertFalse(element["is_array"])

	def test_reference_array_is_array_false(self):
		"""Reference with max='*' should have is_array=False."""
		resource_map = make_mock_resource_map(
			resource_type="Encounter",
			element_maps=[
				make_element_map("Encounter.participant.individual", datatype="Reference", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Encounter.participant.individual"]
		self.assertFalse(element["is_array"])

	def test_coding_array_is_array_false(self):
		"""Coding with max='*' should have is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.maritalStatus.coding", datatype="Coding", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.maritalStatus.coding"]
		self.assertFalse(element["is_array"])

	def test_period_array_is_array_false(self):
		"""Period with max='*' should have is_array=False."""
		resource_map = make_mock_resource_map(
			resource_type="Coverage",
			element_maps=[
				make_element_map("Coverage.class.period", datatype="Period", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Coverage.class.period"]
		self.assertFalse(element["is_array"])

	def test_quantity_array_is_array_false(self):
		"""Quantity with max='*' should have is_array=False."""
		resource_map = make_mock_resource_map(
			resource_type="Observation",
			element_maps=[
				make_element_map("Observation.referenceRange.low", datatype="Quantity", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Observation.referenceRange.low"]
		self.assertFalse(element["is_array"])

	def test_backbone_element_array_is_array_false(self):
		"""BackboneElement with max='*' should have is_array=False."""
		resource_map = make_mock_resource_map(
			resource_type="Observation",
			element_maps=[
				make_element_map("Observation.component", datatype="BackboneElement", max_card="*"),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Observation.component"]
		self.assertFalse(element["is_array"])


# =========================================================
# Non-Array Tests (is_array=False expected)
# =========================================================


class TestNonArrayDetection(IntegrationTestCase):
	"""Tests for elements with max='1' -> is_array=False regardless of type."""

	def test_string_single_is_array_false(self):
		"""String with max='1' should have is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.name.family", datatype="string", max_card="1"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.name.family"]
		self.assertFalse(element["is_array"])

	def test_boolean_single_is_array_false(self):
		"""Boolean with max='1' should have is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.active", datatype="boolean", max_card="1"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.active"]
		self.assertFalse(element["is_array"])

	def test_date_single_is_array_false(self):
		"""Date with max='1' should have is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.birthDate", datatype="date", max_card="1"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.birthDate"]
		self.assertFalse(element["is_array"])

	def test_code_single_is_array_false(self):
		"""Code with max='1' should have is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.gender", datatype="code", max_card="1"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.gender"]
		self.assertFalse(element["is_array"])

	def test_empty_max_is_array_false(self):
		"""Empty max should default to is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.name.text", datatype="string", max_card=""),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.name.text"]
		self.assertFalse(element["is_array"])

	def test_numeric_max_is_array_false(self):
		"""Numeric max (e.g., '3') should have is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.contact", datatype="BackboneElement", max_card="3"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.contact"]
		self.assertFalse(element["is_array"])


# =========================================================
# Mixed Elements Tests
# =========================================================


class TestMixedElementsCompilation(IntegrationTestCase):
	"""Tests for compiling multiple elements with different is_array values."""

	def test_patient_name_elements(self):
		"""Patient name should have mixed is_array values."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.name", datatype="HumanName", max_card="*"),
				make_element_map("Patient.name.use", datatype="code", max_card="1"),
				make_element_map("Patient.name.family", datatype="string", max_card="1"),
				make_element_map("Patient.name.given", datatype="string", max_card="*"),
				make_element_map("Patient.name.prefix", datatype="string", max_card="*"),
				make_element_map("Patient.name.suffix", datatype="string", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		# name itself is complex type -> spread
		self.assertFalse(compiled["elements"]["Patient.name"]["is_array"])
		# use is single code -> no array
		self.assertFalse(compiled["elements"]["Patient.name.use"]["is_array"])
		# family is single string -> no array
		self.assertFalse(compiled["elements"]["Patient.name.family"]["is_array"])
		# given is string array -> collect
		self.assertTrue(compiled["elements"]["Patient.name.given"]["is_array"])
		# prefix is string array -> collect
		self.assertTrue(compiled["elements"]["Patient.name.prefix"]["is_array"])
		# suffix is string array -> collect
		self.assertTrue(compiled["elements"]["Patient.name.suffix"]["is_array"])

	def test_patient_address_elements(self):
		"""Patient address should have mixed is_array values."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.address", datatype="Address", max_card="*"),
				make_element_map("Patient.address.use", datatype="code", max_card="1"),
				make_element_map("Patient.address.line", datatype="string", max_card="*"),
				make_element_map("Patient.address.city", datatype="string", max_card="1"),
				make_element_map("Patient.address.state", datatype="string", max_card="1"),
				make_element_map("Patient.address.postalCode", datatype="string", max_card="1"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		# address itself is complex type -> spread
		self.assertFalse(compiled["elements"]["Patient.address"]["is_array"])
		# use is single code -> no array
		self.assertFalse(compiled["elements"]["Patient.address.use"]["is_array"])
		# line is string array -> collect
		self.assertTrue(compiled["elements"]["Patient.address.line"]["is_array"])
		# city is single string -> no array
		self.assertFalse(compiled["elements"]["Patient.address.city"]["is_array"])
		# state is single string -> no array
		self.assertFalse(compiled["elements"]["Patient.address.state"]["is_array"])
		# postalCode is single string -> no array
		self.assertFalse(compiled["elements"]["Patient.address.postalCode"]["is_array"])

	def test_patient_telecom_elements(self):
		"""Patient telecom - all fields are single values."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.telecom", datatype="ContactPoint", max_card="*"),
				make_element_map("Patient.telecom.system", datatype="code", max_card="1"),
				make_element_map("Patient.telecom.value", datatype="string", max_card="1"),
				make_element_map("Patient.telecom.use", datatype="code", max_card="1"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		# telecom is complex type -> spread
		self.assertFalse(compiled["elements"]["Patient.telecom"]["is_array"])
		# All children are single values -> no array
		self.assertFalse(compiled["elements"]["Patient.telecom.system"]["is_array"])
		self.assertFalse(compiled["elements"]["Patient.telecom.value"]["is_array"])
		self.assertFalse(compiled["elements"]["Patient.telecom.use"]["is_array"])

	def test_observation_component_elements(self):
		"""Observation component with nested arrays."""
		resource_map = make_mock_resource_map(
			resource_type="Observation",
			element_maps=[
				make_element_map("Observation.component", datatype="BackboneElement", max_card="*"),
				make_element_map("Observation.component.code", datatype="CodeableConcept", max_card="1"),
				make_element_map("Observation.component.code.coding", datatype="Coding", max_card="*"),
				make_element_map("Observation.component.code.coding.code", datatype="code", max_card="1"),
				make_element_map(
					"Observation.component.valueQuantity.value", datatype="decimal", max_card="1"
				),
			],
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		# component is BackboneElement -> spread
		self.assertFalse(compiled["elements"]["Observation.component"]["is_array"])
		# code is CodeableConcept -> spread
		self.assertFalse(compiled["elements"]["Observation.component.code"]["is_array"])
		# coding is Coding (complex) -> spread
		self.assertFalse(compiled["elements"]["Observation.component.code.coding"]["is_array"])
		# code inside coding is single -> no array
		self.assertFalse(compiled["elements"]["Observation.component.code.coding.code"]["is_array"])
		# valueQuantity.value is single decimal -> no array
		self.assertFalse(compiled["elements"]["Observation.component.valueQuantity.value"]["is_array"])


# =========================================================
# Edge Cases
# =========================================================


class TestIsArrayEdgeCases(IntegrationTestCase):
	"""Tests for edge cases in is_array detection."""

	def test_no_datatype_is_array_false(self):
		"""Missing datatype should default to is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.custom", datatype="", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.custom"]
		self.assertFalse(element["is_array"])

	def test_unknown_datatype_is_array_false(self):
		"""Unknown datatype should default to is_array=False."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.custom", datatype="UnknownType", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.custom"]
		self.assertFalse(element["is_array"])

	def test_case_insensitive_primitive_detection(self):
		"""Primitive type detection should be case-insensitive."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.test1", datatype="STRING", max_card="*"),
				make_element_map("Patient.test2", datatype="String", max_card="*"),
				make_element_map("Patient.test3", datatype="string", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		# All should be detected as primitive arrays
		self.assertTrue(compiled["elements"]["Patient.test1"]["is_array"])
		self.assertTrue(compiled["elements"]["Patient.test2"]["is_array"])
		self.assertTrue(compiled["elements"]["Patient.test3"]["is_array"])

	def test_fixed_value_elements_get_is_array(self):
		"""Fixed value elements should also get is_array flag."""
		resource_map = make_mock_resource_map(
			element_maps=[
				{
					"fhir_path": "Patient.active",
					"datatype": "boolean",
					"max": "1",
					"value_pointer": {"kind": "fixed", "value": True},
				},
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.active"]
		self.assertFalse(element["is_array"])
		self.assertEqual(element["value_spec"]["kind"], "fixed")

	def test_extension_elements_get_is_array(self):
		"""Extension elements should also get is_array flag."""
		resource_map = make_mock_resource_map(
			element_maps=[
				{
					"fhir_path": "Patient.extension:religion",
					"datatype": "Extension",
					"max": "*",
					"value_pointer": {"kind": "field", "source_key": "primary", "fieldname": "religion"},
					"extension_config": {
						"url": "http://hl7.org/fhir/StructureDefinition/patient-religion",
						"value_datatype": "CodeableConcept",
					},
				},
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		element = compiled["elements"]["Patient.extension:religion"]
		# Extension is complex type -> spread
		self.assertFalse(element["is_array"])


# =========================================================
# Integration with Builder Tests
# =========================================================


class TestCompilerBuilderIntegration(IntegrationTestCase):
	"""Tests to ensure compiler output works with builder."""

	def test_compiled_output_has_is_array_in_all_elements(self):
		"""All compiled elements should have is_array key."""
		resource_map = make_mock_resource_map(
			element_maps=[
				make_element_map("Patient.active", datatype="boolean", max_card="1"),
				make_element_map("Patient.name.family", datatype="string", max_card="1"),
				make_element_map("Patient.name.given", datatype="string", max_card="*"),
				make_element_map("Patient.telecom", datatype="ContactPoint", max_card="*"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		for fhir_path, element in compiled["elements"].items():
			self.assertIn("is_array", element, f"Element {fhir_path} missing is_array key")
			self.assertIsInstance(element["is_array"], bool, f"Element {fhir_path} is_array should be bool")

	def test_complete_patient_compilation(self):
		"""Complete Patient resource should compile with correct is_array flags."""
		resource_map = make_mock_resource_map(
			element_maps=[
				# Scalars
				make_element_map("Patient.active", datatype="boolean", max_card="1"),
				make_element_map("Patient.gender", datatype="code", max_card="1"),
				make_element_map("Patient.birthDate", datatype="date", max_card="1"),
				# Name (complex array with primitive arrays inside)
				make_element_map("Patient.name", datatype="HumanName", max_card="*"),
				make_element_map("Patient.name.use", datatype="code", max_card="1"),
				make_element_map("Patient.name.family", datatype="string", max_card="1"),
				make_element_map("Patient.name.given", datatype="string", max_card="*"),
				# Telecom (complex array, no primitive arrays inside)
				make_element_map("Patient.telecom", datatype="ContactPoint", max_card="*"),
				make_element_map("Patient.telecom.system", datatype="code", max_card="1"),
				make_element_map("Patient.telecom.value", datatype="string", max_card="1"),
				# Address (complex array with primitive array inside)
				make_element_map("Patient.address", datatype="Address", max_card="*"),
				make_element_map("Patient.address.line", datatype="string", max_card="*"),
				make_element_map("Patient.address.city", datatype="string", max_card="1"),
			]
		)

		compiler = FHIRMappingCompiler(resource_map)
		compiled = compiler.compile()

		# Verify is_array flags
		expected_is_array = {
			"Patient.active": False,
			"Patient.gender": False,
			"Patient.birthDate": False,
			"Patient.name": False,  # Complex type -> spread
			"Patient.name.use": False,
			"Patient.name.family": False,
			"Patient.name.given": True,  # Primitive array -> collect
			"Patient.telecom": False,  # Complex type -> spread
			"Patient.telecom.system": False,
			"Patient.telecom.value": False,
			"Patient.address": False,  # Complex type -> spread
			"Patient.address.line": True,  # Primitive array -> collect
			"Patient.address.city": False,
		}

		for fhir_path, expected in expected_is_array.items():
			actual = compiled["elements"][fhir_path]["is_array"]
			self.assertEqual(
				actual, expected, f"Element {fhir_path}: expected is_array={expected}, got {actual}"
			)
