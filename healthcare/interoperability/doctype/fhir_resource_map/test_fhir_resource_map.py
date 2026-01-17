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

	def test_profiles_most_restrictive_wins(self):
		resource_map = frappe.get_doc(
			{
				"doctype": "FHIR Resource Map",
				"name": "Patient-Minimal",
				"primary_doctype": "Patient",
				"resource_type": "Patient",
				"base_structure_definition": "Patient-R4",
				"sources": [
					{
						"doctype": "FHIR Resource Map Source",
						"kind": "direct_link",
						"source_doctype": "Gender",
						"source_key": "gender",
						"link_fieldname": "sex",
					}
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
		elements = resource_map.get_elements_from_structure_definitions()
		for el in elements:
			resource_map.append("element_maps", el)

		# Do the mapping
		for map in resource_map.element_maps:
			if map.fhir_path == "Patient.birthDate":
				# self.assertEqual(map.min, 0)
				map.value_pointer = json.dumps({"kind": "field", "source_key": "primary", "fieldname": "dob"})
			elif map.fhir_path == "Patient.gender":
				# self.assertEqual(map.min, 0)
				map.value_pointer = json.dumps({"kind": "field", "source_key": "gender", "fieldname": "name"})
		resource_map.save()

		print("Mapping: ", resource_map.compiled_mapping)
