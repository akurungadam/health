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
		resource_map.element_maps = []
		for el in elements:
			resource_map.append("element_maps", el)

		# Do the mapping
		for map in resource_map.element_maps:
			if map.fhir_path == "Patient.birthDate":
				self.assertEqual(map.min, 0)
				map.value_pointer = json.dumps({"kind": "field", "source_key": "primary", "fieldname": "dob"})
			elif map.fhir_path == "Patient.gender":
				self.assertEqual(map.min, 1)  #  most restrictive wins, min = 1 in profile
				map.value_pointer = json.dumps({"kind": "field", "source_key": "gender", "fieldname": "name"})
		resource_map.save()
		# print("Mapping: ", resource_map.compiled_mapping)

	def test_generate_fhir_resource_from_compiled_map(self):
		"""End-to-end: compiled map + a real primary doc -> generated FHIR resource.

		Uses the core ``ToDo`` doctype as the primary source so the test stays
		self-contained (no healthcare mandatory-field / Gender coupling).
		"""
		from healthcare.interoperability.doctype.fhir_resource_map.fhir_resource_map import (
			generate_fhir_resource,
		)

		resource_map = frappe.get_doc(
			{
				"doctype": "FHIR Resource Map",
				"resource_type": "Basic",
				"primary_doctype": "ToDo",
				"element_maps": [
					{
						"doctype": "FHIR Resource Element Map",
						"fhir_path": "Basic.id",
						"datatype": "id",
						"max": "1",
						"value_pointer": json.dumps(
							{"kind": "field", "source_key": "primary", "fieldname": "name"}
						),
					},
					{
						"doctype": "FHIR Resource Element Map",
						"fhir_path": "Basic.code.text",
						"datatype": "string",
						"max": "1",
						"value_pointer": json.dumps({"kind": "fixed", "value": "vitals"}),
					},
				],
			}
		).insert(ignore_permissions=True)

		# saving compiled the mapping
		self.assertTrue(resource_map.compiled_mapping)
		self.assertEqual(resource_map.status, "No Errors")

		todo = frappe.get_doc({"doctype": "ToDo", "description": "demo"}).insert(ignore_permissions=True)

		result = generate_fhir_resource(resource_map.name, todo.name)

		self.assertEqual(result["issues"], [])
		resource = result["resource"]
		self.assertEqual(resource["resourceType"], "Basic")
		self.assertEqual(resource["id"], todo.name)
		self.assertEqual(resource["code"], {"text": "vitals"})
