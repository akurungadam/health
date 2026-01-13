# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and Contributors
# See license.txt

import json

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestFHIRResourceMap(IntegrationTestCase):
	"""
	Integration tests for FHIRResourceMap.
	Use this class for testing interactions between multiple components.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

	def test_something(self):
		resource_map = frappe.get_doc(
			{
				"doctype": "FHIR Resource Map",
				"name": "Patient-Minimal",
				"primary_doctype": "Patient",
				"resource_type": "Patient",
				"base_structure_definition": "Patient-R4",
				"sources": [
					{"kind": "direct_link", "doctype": "Gender", "key": "gender", "link_fieldname": "sex"}
				],
				"profiles": [
					{
						"doctype": "FHIR Resource Map Profile",
						"fhir_structure_definition": "Patient-Overlay-Strict-R4-R4",
					}
				],
				"element_maps": [],
			}
		).insert(ignore_permissions=True)

		# Load and overlay elements
		resource_map.get_elements_from_structure_definitions()

		# Do the mapping
		for map in resource_map.element_maps:
			if map.fhir_path == "Patient.birthDate":
				map.value_pointer = {"kind": "field", "source_key": "primary", "fieldname": "dob"}
			elif map.fhir_path == "Patient.gender":
				map.value_pointer = {"kind": "field", "source_key": "primary", "fieldname": "sex"}
		resource_map.save()

		print("Mapping: ", resource_map.compiled_mapping)
