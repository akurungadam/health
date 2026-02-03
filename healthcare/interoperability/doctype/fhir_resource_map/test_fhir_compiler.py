import json
from datetime import datetime

import frappe
from frappe.tests import IntegrationTestCase

from healthcare.interoperability.doctype.fhir_resource_map.fhir_compiler import (
	CompilationMetadata,
	CompiledElement,
	CompiledResource,
	CompiledSource,
	FHIRCompilationError,
	FHIRCompiler,
	ResourceTreeNode,
)


class TestCompilationMetadata(IntegrationTestCase):
	def test_metadata_creation(self):
		metadata = CompilationMetadata("R4", "http://example.com/profile", "Patient")

		self.assertEqual(metadata.fhir_version, "R4")
		self.assertEqual(metadata.profile_url, "http://example.com/profile")
		self.assertEqual(metadata.resource_type, "Patient")
		self.assertIsNone(metadata.compiled_at)

	def test_metadata_to_dict(self):
		metadata = CompilationMetadata("R4", "http://example.com/profile", "Patient")
		metadata.compiled_at = datetime(2026, 1, 31, 12, 0, 0)

		result = metadata.to_dict()

		self.assertEqual(result["fhir_version"], "R4")
		self.assertEqual(result["profile_url"], "http://example.com/profile")
		self.assertEqual(result["resource_type"], "Patient")
		self.assertIn("2026-01-31", result["compiled_at"])

	def test_metadata_from_dict(self):
		data = {
			"fhir_version": "R4",
			"profile_url": "http://example.com/profile",
			"resource_type": "Patient",
			"compiled_at": "2026-01-31 12:00:00",
		}

		metadata = CompilationMetadata.from_dict(data)

		self.assertEqual(metadata.fhir_version, "R4")
		self.assertEqual(metadata.profile_url, "http://example.com/profile")
		self.assertEqual(metadata.resource_type, "Patient")

	def test_metadata_repr(self):
		metadata = CompilationMetadata("R4", None, "Patient")

		result = repr(metadata)

		self.assertIn("Patient", result)
		self.assertIn("R4", result)


class TestCompiledSource(IntegrationTestCase):
	def test_source_creation(self):
		source = CompiledSource("primary", "Patient", "document")

		self.assertEqual(source.key, "primary")
		self.assertEqual(source.entity, "Patient")
		self.assertEqual(source.entity_type, "document")
		self.assertFalse(source.is_primary)
		self.assertFalse(source.is_collection)
		self.assertEqual(source.filters, {})
		self.assertEqual(source.config, {})

	def test_source_to_dict(self):
		source = CompiledSource("gender", "Gender", "direct_link")
		source.is_primary = False
		source.link_field = "sex"
		source.config = {"some": "config"}

		result = source.to_dict()

		self.assertEqual(result["key"], "gender")
		self.assertEqual(result["entity"], "Gender")
		self.assertEqual(result["entity_type"], "direct_link")
		self.assertEqual(result["link_field"], "sex")
		self.assertEqual(result["config"], {"some": "config"})

	def test_source_from_dict(self):
		data = {
			"key": "gender",
			"entity": "Gender",
			"entity_type": "direct_link",
			"is_primary": False,
			"is_collection": False,
			"link_field": "sex",
			"config": {"some": "config"},
		}

		source = CompiledSource.from_dict(data)

		self.assertEqual(source.key, "gender")
		self.assertEqual(source.entity, "Gender")
		self.assertEqual(source.link_field, "sex")
		self.assertEqual(source.config, {"some": "config"})

	def test_source_from_dict_defaults(self):
		data = {"key": "test", "entity": "Test", "entity_type": "document"}

		source = CompiledSource.from_dict(data)

		self.assertFalse(source.is_primary)
		self.assertFalse(source.is_collection)
		self.assertEqual(source.filters, {})
		self.assertEqual(source.config, {})

	def test_source_repr(self):
		source = CompiledSource("primary", "Patient", "document")

		result = repr(source)

		self.assertIn("primary", result)
		self.assertIn("Patient", result)


class TestCompiledElement(IntegrationTestCase):
	def test_element_creation(self):
		element = CompiledElement("Patient.name", "primary")

		self.assertEqual(element.path, "Patient.name")
		self.assertEqual(element.source_key, "primary")
		self.assertIsNone(element.mapping_type)
		self.assertIsNone(element.field)
		self.assertIsNone(element.expression)
		self.assertIsNone(element.fixed_value)
		self.assertIsNone(element.transformer)
		self.assertFalse(element.is_array)
		self.assertFalse(element.is_required)

	def test_element_has_mapping_false(self):
		element = CompiledElement("Patient.name", "primary")

		self.assertFalse(element.has_mapping())

	def test_element_has_mapping_field(self):
		element = CompiledElement("Patient.name", "primary")
		element.field = "patient_name"

		self.assertTrue(element.has_mapping())

	def test_element_has_mapping_fixed(self):
		element = CompiledElement("Patient.active", "primary")
		element.fixed_value = "true"

		self.assertTrue(element.has_mapping())

	def test_element_has_mapping_expression(self):
		element = CompiledElement("Patient.name.text", "primary")
		element.expression = "doc.first_name + ' ' + doc.last_name"

		self.assertTrue(element.has_mapping())

	def test_element_has_mapping_json(self):
		element = CompiledElement("Patient.identifier.type", "primary")
		element.json_value = {"coding": [{"code": "MRN"}]}

		self.assertTrue(element.has_mapping())

	def test_element_has_default(self):
		element = CompiledElement("Patient.active", "primary")
		self.assertFalse(element.has_default())

		element.default_value = "true"
		self.assertTrue(element.has_default())

	def test_element_has_pattern(self):
		element = CompiledElement("Patient.identifier", "primary")
		self.assertFalse(element.has_pattern())

		element.pattern_value = {"system": "http://example.com"}
		self.assertTrue(element.has_pattern())

	def test_element_to_dict(self):
		element = CompiledElement("Patient.birthDate", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "dob"
		element.transformer = "date"
		element.is_required = True
		element.parent_path = "Patient"

		result = element.to_dict()

		self.assertEqual(result["path"], "Patient.birthDate")
		self.assertEqual(result["source_key"], "primary")
		self.assertEqual(result["mapping_type"], "field")
		self.assertEqual(result["field"], "dob")
		self.assertEqual(result["transformer"], "date")
		self.assertTrue(result["is_required"])
		self.assertEqual(result["parent_path"], "Patient")

	def test_element_from_dict(self):
		data = {
			"path": "Patient.birthDate",
			"source_key": "primary",
			"mapping_type": "field",
			"field": "dob",
			"transformer": "date",
			"is_required": True,
			"is_array": False,
			"parent_path": "Patient",
		}

		element = CompiledElement.from_dict(data)

		self.assertEqual(element.path, "Patient.birthDate")
		self.assertEqual(element.source_key, "primary")
		self.assertEqual(element.mapping_type, "field")
		self.assertEqual(element.field, "dob")
		self.assertEqual(element.transformer, "date")
		self.assertTrue(element.is_required)
		self.assertFalse(element.is_array)

	def test_element_mapping_type_constants(self):
		self.assertEqual(CompiledElement.MAPPING_FIELD, "field")
		self.assertEqual(CompiledElement.MAPPING_FIXED, "fixed")
		self.assertEqual(CompiledElement.MAPPING_EXPRESSION, "expression")
		self.assertEqual(CompiledElement.MAPPING_JSON, "json")


class TestResourceTreeNode(IntegrationTestCase):
	def test_node_creation(self):
		node = ResourceTreeNode("Patient")

		self.assertEqual(node.name, "Patient")
		self.assertFalse(node.is_array)
		self.assertFalse(node.is_primitive)
		self.assertEqual(node.children, [])

	def test_add_child(self):
		parent = ResourceTreeNode("Patient")
		child = ResourceTreeNode("name")

		result = parent.add_child(child)

		self.assertEqual(result, child)
		self.assertEqual(len(parent.children), 1)
		self.assertEqual(parent.children[0].name, "name")

	def test_add_multiple_children(self):
		parent = ResourceTreeNode("Patient")
		child1 = ResourceTreeNode("name")
		child2 = ResourceTreeNode("birthDate")
		child3 = ResourceTreeNode("gender")

		parent.add_child(child1)
		parent.add_child(child2)
		parent.add_child(child3)

		self.assertEqual(len(parent.children), 3)

	def test_find_child_found(self):
		parent = ResourceTreeNode("Patient")
		child1 = ResourceTreeNode("name")
		child2 = ResourceTreeNode("birthDate")
		parent.add_child(child1)
		parent.add_child(child2)

		found = parent.find_child("birthDate")

		self.assertEqual(found, child2)

	def test_find_child_not_found(self):
		parent = ResourceTreeNode("Patient")
		child = ResourceTreeNode("name")
		parent.add_child(child)

		found = parent.find_child("nonexistent")

		self.assertIsNone(found)

	def test_find_by_path_simple(self):
		root = ResourceTreeNode("Patient")
		name = ResourceTreeNode("name")
		root.add_child(name)

		found = root.find_by_path("Patient.name")

		self.assertEqual(found, name)

	def test_find_by_path_nested(self):
		root = ResourceTreeNode("Patient")
		name = ResourceTreeNode("name")
		given = ResourceTreeNode("given")
		root.add_child(name)
		name.add_child(given)

		found = root.find_by_path("Patient.name.given")

		self.assertEqual(found, given)

	def test_find_by_path_deeply_nested(self):
		root = ResourceTreeNode("Patient")
		identifier = ResourceTreeNode("identifier")
		type_node = ResourceTreeNode("type")
		coding = ResourceTreeNode("coding")
		code = ResourceTreeNode("code")

		root.add_child(identifier)
		identifier.add_child(type_node)
		type_node.add_child(coding)
		coding.add_child(code)

		found = root.find_by_path("Patient.identifier.type.coding.code")

		self.assertEqual(found, code)

	def test_find_by_path_not_found(self):
		root = ResourceTreeNode("Patient")
		name = ResourceTreeNode("name")
		root.add_child(name)

		found = root.find_by_path("Patient.birthDate")

		self.assertIsNone(found)

	def test_to_dict_simple(self):
		node = ResourceTreeNode("Patient")
		node.is_array = False
		node.is_primitive = False

		result = node.to_dict()

		self.assertEqual(result["name"], "Patient")
		self.assertFalse(result["is_array"])
		self.assertFalse(result["is_primitive"])
		self.assertNotIn("children", result)

	def test_to_dict_with_children(self):
		root = ResourceTreeNode("Patient")
		name = ResourceTreeNode("name")
		name.is_array = True
		birthDate = ResourceTreeNode("birthDate")
		birthDate.is_primitive = True
		root.add_child(name)
		root.add_child(birthDate)

		result = root.to_dict()

		self.assertEqual(len(result["children"]), 2)
		self.assertEqual(result["children"][0]["name"], "name")
		self.assertTrue(result["children"][0]["is_array"])
		self.assertEqual(result["children"][1]["name"], "birthDate")
		self.assertTrue(result["children"][1]["is_primitive"])

	def test_from_dict_simple(self):
		data = {"name": "Patient", "is_array": False, "is_primitive": False}

		node = ResourceTreeNode.from_dict(data)

		self.assertEqual(node.name, "Patient")
		self.assertFalse(node.is_array)
		self.assertFalse(node.is_primitive)
		self.assertEqual(node.children, [])

	def test_from_dict_with_children(self):
		data = {
			"name": "Patient",
			"is_array": False,
			"is_primitive": False,
			"children": [
				{"name": "name", "is_array": True, "is_primitive": False},
				{"name": "birthDate", "is_array": False, "is_primitive": True},
			],
		}

		node = ResourceTreeNode.from_dict(data)

		self.assertEqual(len(node.children), 2)
		self.assertEqual(node.children[0].name, "name")
		self.assertTrue(node.children[0].is_array)
		self.assertEqual(node.children[1].name, "birthDate")
		self.assertTrue(node.children[1].is_primitive)


class TestCompiledResource(IntegrationTestCase):
	def test_resource_creation(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		resource = CompiledResource(metadata)

		self.assertEqual(resource.metadata, metadata)
		self.assertEqual(resource.sources, [])
		self.assertEqual(resource.elements, [])
		self.assertIsNone(resource.resource_tree)

	def test_add_source(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		resource = CompiledResource(metadata)
		source = CompiledSource("primary", "Patient", "document")

		result = resource.add_source(source)

		self.assertEqual(result, source)
		self.assertEqual(len(resource.sources), 1)

	def test_add_element(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		resource = CompiledResource(metadata)
		element = CompiledElement("Patient.name", "primary")

		result = resource.add_element(element)

		self.assertEqual(result, element)
		self.assertEqual(len(resource.elements), 1)

	def test_get_source_found(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		resource = CompiledResource(metadata)
		source1 = CompiledSource("primary", "Patient", "document")
		source2 = CompiledSource("gender", "Gender", "direct_link")
		resource.add_source(source1)
		resource.add_source(source2)

		found = resource.get_source("gender")

		self.assertEqual(found, source2)

	def test_get_source_not_found(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		resource = CompiledResource(metadata)
		source = CompiledSource("primary", "Patient", "document")
		resource.add_source(source)

		found = resource.get_source("nonexistent")

		self.assertIsNone(found)

	def test_get_primary_source(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		resource = CompiledResource(metadata)
		source1 = CompiledSource("primary", "Patient", "document")
		source1.is_primary = True
		source2 = CompiledSource("gender", "Gender", "direct_link")
		resource.add_source(source1)
		resource.add_source(source2)

		found = resource.get_primary_source()

		self.assertEqual(found, source1)

	def test_get_primary_source_none(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		resource = CompiledResource(metadata)
		source = CompiledSource("gender", "Gender", "direct_link")
		resource.add_source(source)

		found = resource.get_primary_source()

		self.assertIsNone(found)

	def test_get_elements_by_source(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		resource = CompiledResource(metadata)
		element1 = CompiledElement("Patient.name", "primary")
		element2 = CompiledElement("Patient.gender", "gender")
		element3 = CompiledElement("Patient.birthDate", "primary")
		resource.add_element(element1)
		resource.add_element(element2)
		resource.add_element(element3)

		result = resource.get_elements_by_source("primary")

		self.assertEqual(len(result), 2)
		self.assertIn(element1, result)
		self.assertIn(element3, result)

	def test_get_elements_by_parent_path(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		resource = CompiledResource(metadata)
		element1 = CompiledElement("Patient.name.given", "primary")
		element1.parent_path = "Patient.name"
		element2 = CompiledElement("Patient.name.family", "primary")
		element2.parent_path = "Patient.name"
		element3 = CompiledElement("Patient.birthDate", "primary")
		element3.parent_path = "Patient"
		resource.add_element(element1)
		resource.add_element(element2)
		resource.add_element(element3)

		result = resource.get_elements_by_parent_path("Patient.name")

		self.assertEqual(len(result), 2)
		self.assertIn(element1, result)
		self.assertIn(element2, result)

	def test_to_dict(self):
		metadata = CompilationMetadata("R4", "http://example.com", "Patient")
		resource = CompiledResource(metadata)

		source = CompiledSource("primary", "Patient", "document")
		source.is_primary = True
		resource.add_source(source)

		element = CompiledElement("Patient.name", "primary")
		element.mapping_type = "field"
		element.field = "patient_name"
		resource.add_element(element)

		tree = ResourceTreeNode("Patient")
		resource.resource_tree = tree

		result = resource.to_dict()

		self.assertEqual(result["metadata"]["resource_type"], "Patient")
		self.assertEqual(len(result["sources"]), 1)
		self.assertEqual(result["sources"][0]["key"], "primary")
		self.assertEqual(len(result["elements"]), 1)
		self.assertEqual(result["elements"][0]["path"], "Patient.name")
		self.assertEqual(result["resource_tree"]["name"], "Patient")

	def test_from_dict(self):
		data = {
			"metadata": {
				"fhir_version": "R4",
				"profile_url": "http://example.com",
				"resource_type": "Patient",
				"compiled_at": None,
			},
			"sources": [
				{
					"key": "primary",
					"entity": "Patient",
					"entity_type": "document",
					"is_primary": True,
					"is_collection": False,
					"filters": {},
					"config": {},
				}
			],
			"elements": [
				{
					"path": "Patient.name",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "patient_name",
				}
			],
			"resource_tree": {"name": "Patient", "is_array": False, "is_primitive": False},
		}

		resource = CompiledResource.from_dict(data)

		self.assertEqual(resource.metadata.resource_type, "Patient")
		self.assertEqual(len(resource.sources), 1)
		self.assertEqual(resource.sources[0].key, "primary")
		self.assertEqual(len(resource.elements), 1)
		self.assertEqual(resource.elements[0].path, "Patient.name")
		self.assertEqual(resource.resource_tree.name, "Patient")

	def test_to_dict_from_dict_roundtrip(self):
		metadata = CompilationMetadata("R4", "http://example.com", "Patient")
		original = CompiledResource(metadata)

		source = CompiledSource("primary", "Patient", "document")
		source.is_primary = True
		original.add_source(source)

		element = CompiledElement("Patient.birthDate", "primary")
		element.mapping_type = "field"
		element.field = "dob"
		element.transformer = "date"
		element.is_required = True
		element.parent_path = "Patient"
		original.add_element(element)

		tree = ResourceTreeNode("Patient")
		child = ResourceTreeNode("birthDate")
		child.is_primitive = True
		tree.add_child(child)
		original.resource_tree = tree

		data = original.to_dict()
		restored = CompiledResource.from_dict(data)

		self.assertEqual(restored.metadata.fhir_version, "R4")
		self.assertEqual(restored.metadata.resource_type, "Patient")
		self.assertEqual(len(restored.sources), 1)
		self.assertTrue(restored.sources[0].is_primary)
		self.assertEqual(len(restored.elements), 1)
		self.assertEqual(restored.elements[0].transformer, "date")
		self.assertEqual(restored.resource_tree.name, "Patient")
		self.assertEqual(len(restored.resource_tree.children), 1)


class TestFHIRCompiler(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self._create_test_fixtures()

	def _create_test_fixtures(self):
		# Create FHIR Structure Definition if not exists
		if not frappe.db.exists("FHIR Structure Definition", "Patient-R4"):
			frappe.get_doc(
				{
					"doctype": "FHIR Structure Definition",
					"name": "Patient-R4",
					"fhir_sd": "Patient",
					"fhir_version": "R4",
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()

		# Create test FHIR Resource Map
		if frappe.db.exists("FHIR Resource Map", "Patient-Patient-R4"):
			frappe.delete_doc("FHIR Resource Map", "Patient-Patient-R4", force=True)
			frappe.db.commit()

		resource_map = frappe.get_doc(
			{
				"doctype": "FHIR Resource Map",
				"name": "Patient-Patient-R4",
				"resource_type": "Patient",
				"primary_doctype": "Patient",
				"base_structure_definition": "Patient-R4",
				"profiles": [],
				"sources": [
					{
						"source_key": "gender",
						"source_doctype": "Gender",
						"kind": "direct_link",
						"link_fieldname": "sex",
					}
				],
				"element_maps": [
					{
						"fhir_path": "Patient.id",
						"datatype": "string",
						"min": 0,
						"max": "1",
						"is_required": 0,
						"mapping_type": "Frappe Field",
						"frappe_field": "name",
					},
					{
						"fhir_path": "Patient.birthDate",
						"datatype": "date",
						"min": 0,
						"max": "1",
						"is_required": 0,
						"mapping_type": "Frappe Field",
						"frappe_field": "dob",
					},
					{
						"fhir_path": "Patient.gender",
						"datatype": "code",
						"min": 0,
						"max": "1",
						"is_required": 0,
						"mapping_type": "Frappe Field",
						"frappe_field": "name",
						"value_pointer": '{"kind":"field","source_key":"gender","fieldname":"name"}',
					},
					{
						"fhir_path": "Patient.active",
						"datatype": "boolean",
						"min": 0,
						"max": "1",
						"is_required": 0,
						"mapping_type": "Fixed",
						"fixed_value": "true",
					},
					{
						"fhir_path": "Patient.identifier",
						"datatype": "Identifier",
						"min": 1,
						"max": "*",
						"is_required": 0,
					},
					{
						"fhir_path": "Patient.identifier.value",
						"datatype": "string",
						"min": 1,
						"max": "1",
						"is_required": 1,
						"mapping_type": "Frappe Field",
						"frappe_field": "name",
					},
					{
						"fhir_path": "Patient.name.text",
						"datatype": "string",
						"min": 0,
						"max": "1",
						"is_required": 0,
						"mapping_type": "Frappe Field",
						"frappe_field": "patient_name",
					},
					{
						"fhir_path": "Patient.name",
						"datatype": "HumanName",
						"min": 0,
						"max": "*",
						"is_required": 0,
						"mapping_type": "Frappe Field",  # Add mapping so it's included
						"frappe_field": "patient_name",
					},
				],
			}
		)
		resource_map.insert(ignore_permissions=True)
		frappe.db.commit()

	def tearDown(self):
		if frappe.db.exists("FHIR Resource Map", "Patient-Patient-R4"):
			frappe.delete_doc("FHIR Resource Map", "Patient-Patient-R4", force=True)
		frappe.db.commit()
		super().tearDown()

	def test_compile_returns_compiled_resource(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertIsInstance(result, CompiledResource)

	def test_compile_metadata(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertEqual(result.metadata.resource_type, "Patient")
		self.assertEqual(result.metadata.fhir_version, "R4")
		self.assertIsNotNone(result.metadata.compiled_at)

	def test_compile_primary_source(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		primary = result.get_primary_source()
		self.assertIsNotNone(primary)
		self.assertEqual(primary.key, "primary")
		self.assertEqual(primary.entity, "Patient")
		self.assertEqual(primary.entity_type, "document")
		self.assertTrue(primary.is_primary)

	def test_compile_additional_sources(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		gender_source = result.get_source("gender")
		self.assertIsNotNone(gender_source)
		self.assertEqual(gender_source.entity, "Gender")
		self.assertEqual(gender_source.entity_type, "direct_link")
		self.assertEqual(gender_source.link_field, "sex")

	def test_compile_field_mapping_element(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		birth_date = None
		for element in result.elements:
			if element.path == "Patient.birthDate":
				birth_date = element
				break

		self.assertIsNotNone(birth_date)
		self.assertEqual(birth_date.mapping_type, CompiledElement.MAPPING_FIELD)
		self.assertEqual(birth_date.field, "dob")
		self.assertEqual(birth_date.transformer, "date")
		self.assertEqual(birth_date.source_key, "primary")

	def test_compile_fixed_mapping_element(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		active = None
		for element in result.elements:
			if element.path == "Patient.active":
				active = element
				break

		self.assertIsNotNone(active)
		self.assertEqual(active.mapping_type, CompiledElement.MAPPING_FIXED)
		self.assertEqual(active.fixed_value, "true")
		self.assertEqual(active.transformer, "boolean")

	def test_compile_source_key_from_value_pointer(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		gender = None
		for element in result.elements:
			if element.path == "Patient.gender":
				gender = element
				break

		self.assertIsNotNone(gender)
		self.assertEqual(gender.source_key, "gender")

	def test_compile_required_element_included(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		identifier_value = None
		for element in result.elements:
			if element.path == "Patient.identifier.value":
				identifier_value = element
				break

		self.assertIsNotNone(identifier_value)
		self.assertTrue(identifier_value.is_required)

	def test_compile_min_cardinality_element_included(self):
		"""Test that elements with min > 0 are included even without mapping"""
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		# Patient.identifier has min=1, should be included even without mapping
		identifier = None
		for element in result.elements:
			if element.path == "Patient.identifier":
				identifier = element
				break

		self.assertIsNotNone(identifier)

	def test_compile_array_cardinality(self):
		"""Test that max=* sets is_array=True on tree nodes"""
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		tree = result.resource_tree

		# identifier has max=* so should be array
		identifier_node = tree.find_child("identifier")
		self.assertIsNotNone(identifier_node)
		self.assertTrue(identifier_node.is_array)

		# name has max=* so should be array (created via Patient.name.text)
		name_node = tree.find_child("name")
		self.assertIsNotNone(name_node)
		self.assertTrue(name_node.is_array)

		# birthDate has max=1 so should NOT be array
		birth_date_node = tree.find_child("birthDate")
		self.assertIsNotNone(birth_date_node)
		self.assertFalse(birth_date_node.is_array)

	def test_compile_parent_path(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		identifier_value = None
		name_text = None
		for element in result.elements:
			if element.path == "Patient.identifier.value":
				identifier_value = element
			if element.path == "Patient.name.text":
				name_text = element

		self.assertEqual(identifier_value.parent_path, "Patient.identifier")
		self.assertEqual(name_text.parent_path, "Patient.name")

	def test_compile_resource_tree_created(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertIsNotNone(result.resource_tree)
		self.assertEqual(result.resource_tree.name, "Patient")
		self.assertFalse(result.resource_tree.is_array)
		self.assertFalse(result.resource_tree.is_primitive)

	def test_compile_resource_tree_structure(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		tree = result.resource_tree

		# Check top-level children exist
		id_node = tree.find_child("id")
		birth_date_node = tree.find_child("birthDate")
		identifier_node = tree.find_child("identifier")
		name_node = tree.find_child("name")

		self.assertIsNotNone(id_node)
		self.assertIsNotNone(birth_date_node)
		self.assertIsNotNone(identifier_node)
		self.assertIsNotNone(name_node)

	def test_compile_resource_tree_primitives(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		tree = result.resource_tree

		id_node = tree.find_child("id")
		birth_date_node = tree.find_child("birthDate")

		self.assertTrue(id_node.is_primitive)
		self.assertTrue(birth_date_node.is_primitive)

	def test_compile_resource_tree_arrays(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		tree = result.resource_tree

		identifier_node = tree.find_child("identifier")
		name_node = tree.find_child("name")

		self.assertTrue(identifier_node.is_array)
		self.assertTrue(name_node.is_array)

	def test_compile_resource_tree_nested(self):
		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		tree = result.resource_tree

		identifier_value = tree.find_by_path("Patient.identifier.value")
		name_text = tree.find_by_path("Patient.name.text")

		self.assertIsNotNone(identifier_value)
		self.assertIsNotNone(name_text)
		self.assertTrue(identifier_value.is_primitive)
		self.assertTrue(name_text.is_primitive)

	def test_compile_to_dict_serializable(self):
		import json

		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		# Should not raise
		json_str = json.dumps(result.to_dict())

		self.assertIsInstance(json_str, str)
		self.assertIn("Patient", json_str)

	def test_compile_roundtrip(self):
		import json

		resource_map = frappe.get_doc("FHIR Resource Map", "Patient-Patient-R4")
		compiler = FHIRCompiler(resource_map)

		original = compiler.compile()

		json_str = json.dumps(original.to_dict())
		data = json.loads(json_str)
		restored = CompiledResource.from_dict(data)

		self.assertEqual(restored.metadata.resource_type, original.metadata.resource_type)
		self.assertEqual(len(restored.sources), len(original.sources))
		self.assertEqual(len(restored.elements), len(original.elements))


class TestFHIRCompilerTransformers(IntegrationTestCase):
	def test_determine_transformer_string(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._determine_transformer("string"), "string")
		self.assertEqual(compiler._determine_transformer("String"), "string")
		self.assertEqual(compiler._determine_transformer("STRING"), "string")

	def test_determine_transformer_boolean(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._determine_transformer("boolean"), "boolean")

	def test_determine_transformer_integer(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._determine_transformer("integer"), "integer")

	def test_determine_transformer_decimal(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._determine_transformer("decimal"), "decimal")

	def test_determine_transformer_date(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._determine_transformer("date"), "date")

	def test_determine_transformer_datetime(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._determine_transformer("datetime"), "datetime")

	def test_determine_transformer_instant(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._determine_transformer("instant"), "instant")

	def test_determine_transformer_uri(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._determine_transformer("uri"), "uri")

	def test_determine_transformer_code(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._determine_transformer("code"), "code")

	def test_determine_transformer_complex_type_returns_none(self):
		compiler = FHIRCompiler(None)

		self.assertIsNone(compiler._determine_transformer("Identifier"))
		self.assertIsNone(compiler._determine_transformer("HumanName"))
		self.assertIsNone(compiler._determine_transformer("CodeableConcept"))
		self.assertIsNone(compiler._determine_transformer("Reference"))

	def test_determine_transformer_none_input(self):
		compiler = FHIRCompiler(None)

		self.assertIsNone(compiler._determine_transformer(None))
		self.assertIsNone(compiler._determine_transformer(""))


class TestFHIRCompilerCardinality(IntegrationTestCase):
	def test_is_array_star(self):
		compiler = FHIRCompiler(None)

		self.assertTrue(compiler._is_array("*"))

	def test_is_array_multiple(self):
		compiler = FHIRCompiler(None)

		self.assertTrue(compiler._is_array("2"))
		self.assertTrue(compiler._is_array("5"))
		self.assertTrue(compiler._is_array("100"))

	def test_is_array_single(self):
		compiler = FHIRCompiler(None)

		self.assertFalse(compiler._is_array("1"))

	def test_is_array_none(self):
		compiler = FHIRCompiler(None)

		self.assertFalse(compiler._is_array(None))
		self.assertFalse(compiler._is_array(""))


class TestFHIRCompilerParentPath(IntegrationTestCase):
	def test_get_parent_path_simple(self):
		compiler = FHIRCompiler(None)

		result = compiler._get_parent_path("Patient.name")

		self.assertEqual(result, "Patient")

	def test_get_parent_path_nested(self):
		compiler = FHIRCompiler(None)

		result = compiler._get_parent_path("Patient.identifier.type.coding.code")

		self.assertEqual(result, "Patient.identifier.type.coding")

	def test_get_parent_path_root(self):
		compiler = FHIRCompiler(None)

		result = compiler._get_parent_path("Patient")

		self.assertIsNone(result)

	def test_get_parent_path_none(self):
		compiler = FHIRCompiler(None)

		result = compiler._get_parent_path(None)

		self.assertIsNone(result)


class TestFHIRCompilerMappingTypeNormalization(IntegrationTestCase):
	def test_normalize_frappe_field(self):
		compiler = FHIRCompiler(None)

		result = compiler._normalize_mapping_type("Frappe Field")

		self.assertEqual(result, CompiledElement.MAPPING_FIELD)

	def test_normalize_fixed(self):
		compiler = FHIRCompiler(None)

		result = compiler._normalize_mapping_type("Fixed")

		self.assertEqual(result, CompiledElement.MAPPING_FIXED)

	def test_normalize_expression(self):
		compiler = FHIRCompiler(None)

		result = compiler._normalize_mapping_type("Expression")

		self.assertEqual(result, CompiledElement.MAPPING_EXPRESSION)

	def test_normalize_json(self):
		compiler = FHIRCompiler(None)

		result = compiler._normalize_mapping_type("JSON")

		self.assertEqual(result, CompiledElement.MAPPING_JSON)

	def test_normalize_case_insensitive(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._normalize_mapping_type("frappe field"), CompiledElement.MAPPING_FIELD)
		self.assertEqual(compiler._normalize_mapping_type("FIXED"), CompiledElement.MAPPING_FIXED)
		self.assertEqual(compiler._normalize_mapping_type("expression"), CompiledElement.MAPPING_EXPRESSION)
		self.assertEqual(compiler._normalize_mapping_type("json"), CompiledElement.MAPPING_JSON)

	def test_normalize_none(self):
		compiler = FHIRCompiler(None)

		self.assertIsNone(compiler._normalize_mapping_type(None))
		self.assertIsNone(compiler._normalize_mapping_type(""))

	def test_normalize_unknown(self):
		compiler = FHIRCompiler(None)

		self.assertIsNone(compiler._normalize_mapping_type("Unknown"))
		self.assertIsNone(compiler._normalize_mapping_type("Something Else"))


# =============================================================================
# Additional CompiledElement Tests - Extensions and Slices
# =============================================================================


class TestCompiledElementExtensions(IntegrationTestCase):
	def test_element_is_extension_false_by_default(self):
		element = CompiledElement("Patient.extension", "primary")

		self.assertFalse(element.is_extension())

	def test_element_is_extension_true(self):
		element = CompiledElement("Patient.extension", "primary")
		element.extension_url = "http://example.org/ext"

		self.assertTrue(element.is_extension())

	def test_element_extension_fields_to_dict(self):
		element = CompiledElement("Patient.extension", "primary")
		element.extension_url = "http://example.org/religion"
		element.extension_value_type = "valueCodeableConcept"
		element.is_modifier_extension = False

		result = element.to_dict()

		self.assertEqual(result["extension_url"], "http://example.org/religion")
		self.assertEqual(result["extension_value_type"], "valueCodeableConcept")
		self.assertFalse(result["is_modifier_extension"])

	def test_element_modifier_extension(self):
		element = CompiledElement("Patient.modifierExtension", "primary")
		element.extension_url = "http://example.org/modifier"
		element.extension_value_type = "valueBoolean"
		element.is_modifier_extension = True

		result = element.to_dict()

		self.assertTrue(result["is_modifier_extension"])

	def test_element_extension_roundtrip(self):
		original = CompiledElement("Patient.extension", "primary")
		original.extension_url = "http://example.org/test"
		original.extension_value_type = "valueString"
		original.is_modifier_extension = False
		original.mapping_type = "field"
		original.field = "custom_field"

		data = original.to_dict()
		restored = CompiledElement.from_dict(data)

		self.assertEqual(restored.extension_url, original.extension_url)
		self.assertEqual(restored.extension_value_type, original.extension_value_type)
		self.assertEqual(restored.is_modifier_extension, original.is_modifier_extension)
		self.assertTrue(restored.is_extension())


class TestCompiledElementSlices(IntegrationTestCase):
	def test_element_is_slice_false_by_default(self):
		element = CompiledElement("Patient.identifier", "primary")

		self.assertFalse(element.is_slice())

	def test_element_is_slice_true(self):
		element = CompiledElement("Patient.identifier:aadhaar", "primary")
		element.slice_name = "aadhaar"
		element.slice_of = "Patient.identifier"

		self.assertTrue(element.is_slice())

	def test_element_slice_fields_to_dict(self):
		element = CompiledElement("Patient.identifier:aadhaar", "primary")
		element.slice_name = "aadhaar"
		element.slice_of = "Patient.identifier"
		element.pattern_value = {"system": "https://uidai.gov.in/aadhaar"}

		result = element.to_dict()

		self.assertEqual(result["slice_name"], "aadhaar")
		self.assertEqual(result["slice_of"], "Patient.identifier")
		self.assertEqual(result["pattern_value"], {"system": "https://uidai.gov.in/aadhaar"})

	def test_element_slice_with_complex_discriminator(self):
		element = CompiledElement("Patient.identifier:pan", "primary")
		element.slice_name = "pan"
		element.slice_of = "Patient.identifier"
		element.pattern_value = {
			"system": "https://incometax.gov.in/pan",
			"type": {
				"coding": [
					{
						"system": "http://terminology.hl7.org/CodeSystem/v2-0203",
						"code": "TAX",
						"display": "Tax ID",
					}
				]
			},
		}

		result = element.to_dict()

		self.assertEqual(result["pattern_value"]["system"], "https://incometax.gov.in/pan")
		self.assertEqual(result["pattern_value"]["type"]["coding"][0]["code"], "TAX")

	def test_element_slice_roundtrip(self):
		original = CompiledElement("Patient.identifier:mrn", "primary")
		original.slice_name = "mrn"
		original.slice_of = "Patient.identifier"
		original.pattern_value = {"system": "http://hospital.org/mrn"}
		original.mapping_type = "field"
		original.field = "patient_id"
		original.transformer = "string"

		data = original.to_dict()
		restored = CompiledElement.from_dict(data)

		self.assertEqual(restored.slice_name, original.slice_name)
		self.assertEqual(restored.slice_of, original.slice_of)
		self.assertEqual(restored.pattern_value, original.pattern_value)
		self.assertTrue(restored.is_slice())


# =============================================================================
# Compiler Source Kind Normalization Tests
# =============================================================================


class TestFHIRCompilerSourceKind(IntegrationTestCase):
	def test_normalize_document(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._normalize_source_kind("document"), "document")
		self.assertEqual(compiler._normalize_source_kind("Document"), "document")

	def test_normalize_child_table(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._normalize_source_kind("child_table"), "child_table")
		self.assertEqual(compiler._normalize_source_kind("Child_Table"), "child_table")

	def test_normalize_direct_link(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._normalize_source_kind("direct_link"), "direct_link")
		self.assertEqual(compiler._normalize_source_kind("Direct_Link"), "direct_link")

	def test_normalize_reverse_link(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._normalize_source_kind("reverse_link"), "reverse_link")
		self.assertEqual(compiler._normalize_source_kind("Reverse_Link"), "reverse_link")

	def test_normalize_none_defaults_to_document(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._normalize_source_kind(None), "document")

	def test_normalize_empty_defaults_to_document(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._normalize_source_kind(""), "document")

	def test_normalize_unknown_defaults_to_document(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._normalize_source_kind("unknown"), "document")
		self.assertEqual(compiler._normalize_source_kind("something_else"), "document")


# =============================================================================
# Compiler Extension Value Type Transformer Tests
# =============================================================================


class TestFHIRCompilerExtensionValueType(IntegrationTestCase):
	def test_value_string(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueString"), "string")

	def test_value_boolean(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueBoolean"), "boolean")

	def test_value_integer(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueInteger"), "integer")

	def test_value_decimal(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueDecimal"), "decimal")

	def test_value_date(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueDate"), "date")

	def test_value_datetime(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueDateTime"), "datetime")

	def test_value_instant(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueInstant"), "instant")

	def test_value_code(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueCode"), "code")

	def test_value_uri(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueUri"), "uri")

	def test_value_url(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueUrl"), "url")

	def test_value_canonical(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueCanonical"), "canonical")

	def test_value_id(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueId"), "id")

	def test_value_markdown(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueMarkdown"), "markdown")

	def test_value_positive_int(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valuePositiveInt"), "positiveint")

	def test_value_unsigned_int(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer("valueUnsignedInt"), "unsignedint")

	def test_complex_types_return_none(self):
		compiler = FHIRCompiler(None)

		self.assertIsNone(compiler._extension_value_type_to_transformer("valueReference"))
		self.assertIsNone(compiler._extension_value_type_to_transformer("valueCodeableConcept"))
		self.assertIsNone(compiler._extension_value_type_to_transformer("valueIdentifier"))

	def test_none_defaults_to_string(self):
		compiler = FHIRCompiler(None)

		self.assertEqual(compiler._extension_value_type_to_transformer(None), "string")


# =============================================================================
# Compiler Custom Elements Only Mode Tests
# =============================================================================


class TestFHIRCompilerCustomOnly(IntegrationTestCase):
	def setUp(self):
		self.created_structure_definitions = []
		self.created_resource_maps = []

	def tearDown(self):
		self._cleanup_test_data()

	def _cleanup_test_data(self):
		for name in self.created_resource_maps:
			if frappe.db.exists("FHIR Resource Map", name):
				frappe.delete_doc("FHIR Resource Map", name, force=True)

		for name in self.created_structure_definitions:
			if frappe.db.exists("FHIR Structure Definition", name):
				frappe.delete_doc("FHIR Structure Definition", name, force=True)

		self.created_resource_maps = []
		self.created_structure_definitions = []
		frappe.db.commit()

	def _create_resource_map(self, custom_elements):
		import json as json_module
		import uuid

		suffix = uuid.uuid4().hex[:8]
		sd_fhir_sd = f"PatientTest{suffix}"

		sd = frappe.get_doc(
			{
				"doctype": "FHIR Structure Definition",
				"fhir_sd": sd_fhir_sd,
				"fhir_version": "R4",
			}
		)
		sd.flags.ignore_validate = True
		sd.flags.ignore_mandatory = True
		sd.insert(ignore_permissions=True)
		sd_name = sd.name
		self.created_structure_definitions.append(sd_name)

		doc = frappe.get_doc(
			{
				"doctype": "FHIR Resource Map",
				"resource_type": "Patient",
				"base_structure_definition": sd_name,
				"custom_elements": json_module.dumps(custom_elements),
			}
		)
		doc.insert(ignore_permissions=True)
		self.created_resource_maps.append(doc.name)
		frappe.db.commit()

		return doc

	def test_is_custom_only_mode_with_sources(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)
		compiler._custom_elements = compiler._parse_custom_elements()

		self.assertTrue(compiler._is_custom_only_mode())

	def test_is_custom_only_mode_without_sources(self):
		"""When custom_elements has elements but no sources, should NOT be custom-only mode"""
		custom = {
			"elements": [
				{"path": "Patient.id", "source_key": "primary", "mapping_type": "field", "field": "name"}
			],
		}
		resource_map = self._create_resource_map_with_primary(custom)
		compiler = FHIRCompiler(resource_map)
		compiler._custom_elements = compiler._parse_custom_elements()

		self.assertFalse(compiler._is_custom_only_mode())

	def _create_resource_map_with_primary(self, custom_elements, resource_type="Patient"):
		"""Create resource map with primary_doctype set (for non-custom-only mode tests)"""
		import json as json_module
		import uuid

		suffix = uuid.uuid4().hex[:8]
		sd_fhir_sd = f"TestSD{suffix}"

		sd = frappe.get_doc(
			{
				"doctype": "FHIR Structure Definition",
				"fhir_sd": sd_fhir_sd,
				"fhir_version": "R4",
			}
		)
		sd.flags.ignore_validate = True
		sd.flags.ignore_mandatory = True
		sd.insert(ignore_permissions=True)
		sd_name = sd.name
		self.created_structure_definitions.append(sd_name)

		doc = frappe.get_doc(
			{
				"doctype": "FHIR Resource Map",
				"resource_type": resource_type,
				"primary_doctype": "Patient",  # Set primary doctype
				"base_structure_definition": sd_name,
				"custom_elements": json_module.dumps(custom_elements),
			}
		)
		doc.insert(ignore_permissions=True)
		self.created_resource_maps.append(doc.name)
		frappe.db.commit()

		return doc

	def test_compile_custom_sources(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertEqual(len(result.sources), 1)
		primary = result.get_primary_source()
		self.assertIsNotNone(primary)
		self.assertEqual(primary.entity, "Patient")
		self.assertTrue(primary.is_primary)

	def test_compile_custom_multiple_sources(self):
		custom = {
			"sources": [
				{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True},
				{"key": "gender", "doctype": "Gender", "kind": "direct_link", "link_field": "sex"},
			],
			"elements": [],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertEqual(len(result.sources), 2)

		gender_source = result.get_source("gender")
		self.assertIsNotNone(gender_source)
		self.assertEqual(gender_source.entity, "Gender")
		self.assertEqual(gender_source.entity_type, "direct_link")
		self.assertEqual(gender_source.link_field, "sex")

	def test_compile_custom_child_table_source(self):
		custom = {
			"sources": [
				{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True},
				{
					"key": "telecom",
					"doctype": "Patient Telecom",
					"kind": "child_table",
					"link_field": "custom_telecom",
				},
			],
			"elements": [],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		telecom_source = result.get_source("telecom")
		self.assertIsNotNone(telecom_source)
		self.assertEqual(telecom_source.entity_type, "child_table")
		self.assertTrue(telecom_source.is_collection)

	def test_compile_custom_reverse_link_source(self):
		custom = {
			"sources": [
				{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True},
				{
					"key": "appointments",
					"doctype": "Patient Appointment",
					"kind": "reverse_link",
					"link_field": "patient",
				},
			],
			"elements": [],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		appt_source = result.get_source("appointments")
		self.assertIsNotNone(appt_source)
		self.assertEqual(appt_source.entity_type, "reverse_link")
		self.assertTrue(appt_source.is_collection)

	def test_compile_custom_elements(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.id",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "name",
					"datatype": "string",
				},
				{
					"path": "Patient.birthDate",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "dob",
					"datatype": "date",
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertEqual(len(result.elements), 2)

		id_element = None
		birth_date_element = None
		for el in result.elements:
			if el.path == "Patient.id":
				id_element = el
			elif el.path == "Patient.birthDate":
				birth_date_element = el

		self.assertIsNotNone(id_element)
		self.assertEqual(id_element.field, "name")
		self.assertEqual(id_element.transformer, "string")

		self.assertIsNotNone(birth_date_element)
		self.assertEqual(birth_date_element.field, "dob")
		self.assertEqual(birth_date_element.transformer, "date")

	def test_compile_custom_fixed_value(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.active",
					"source_key": "primary",
					"mapping_type": "fixed",
					"fixed_value": "true",
					"datatype": "boolean",
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		active_element = result.elements[0]
		self.assertEqual(active_element.mapping_type, CompiledElement.MAPPING_FIXED)
		self.assertEqual(active_element.fixed_value, "true")
		self.assertEqual(active_element.transformer, "boolean")

	def test_compile_custom_json_value(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.maritalStatus",
					"source_key": "primary",
					"mapping_type": "json",
					"json_value": {"coding": [{"system": "http://example.org", "code": "M"}]},
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		status_element = result.elements[0]
		self.assertEqual(status_element.mapping_type, CompiledElement.MAPPING_JSON)
		self.assertEqual(
			status_element.json_value, {"coding": [{"system": "http://example.org", "code": "M"}]}
		)

	def test_compile_custom_expression(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.name.text",
					"source_key": "primary",
					"mapping_type": "expression",
					"expression": "doc.get('first_name', '') + ' ' + doc.get('last_name', '')",
					"datatype": "string",
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		name_element = result.elements[0]
		self.assertEqual(name_element.mapping_type, CompiledElement.MAPPING_EXPRESSION)
		self.assertIn("first_name", name_element.expression)

	def test_compile_custom_array_element(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.name.given",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "first_name",
					"datatype": "string",
					"is_array": True,
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		given_element = result.elements[0]
		self.assertTrue(given_element.is_array)

	def test_compile_custom_metadata(self):
		custom = {
			"metadata": {
				"fhir_version": "R4",
				"profile_url": "https://example.org/Patient",
			},
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertEqual(result.metadata.fhir_version, "R4")
		self.assertEqual(result.metadata.profile_url, "https://example.org/Patient")

	def test_compile_custom_extension(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"extensions": [
				{
					"path": "Patient",
					"url": "http://example.org/religion",
					"value_type": "valueString",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "religion",
				}
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		ext_elements = [el for el in result.elements if el.is_extension()]
		self.assertEqual(len(ext_elements), 1)
		self.assertEqual(ext_elements[0].extension_url, "http://example.org/religion")
		self.assertEqual(ext_elements[0].extension_value_type, "valueString")

	def test_compile_custom_modifier_extension(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"extensions": [
				{
					"path": "Patient",
					"url": "http://example.org/modifier",
					"value_type": "valueBoolean",
					"source_key": "primary",
					"mapping_type": "fixed",
					"fixed_value": "true",
					"is_modifier": True,
				}
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		ext_elements = [el for el in result.elements if el.is_extension()]
		self.assertEqual(len(ext_elements), 1)
		self.assertTrue(ext_elements[0].is_modifier_extension)
		self.assertIn("modifierExtension", ext_elements[0].path)

	def test_compile_custom_slice(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"slices": [
				{
					"path": "Patient.identifier",
					"slice_name": "aadhaar",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "aadhaar_number",
					"datatype": "string",
					"discriminator_value": {"system": "https://uidai.gov.in/aadhaar"},
				}
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		slice_elements = [el for el in result.elements if el.is_slice()]
		self.assertEqual(len(slice_elements), 1)
		self.assertEqual(slice_elements[0].slice_name, "aadhaar")
		self.assertEqual(slice_elements[0].slice_of, "Patient.identifier")
		self.assertEqual(slice_elements[0].pattern_value, {"system": "https://uidai.gov.in/aadhaar"})

	def test_compile_custom_slice_with_complex_discriminator(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"slices": [
				{
					"path": "Patient.identifier",
					"slice_name": "pan",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "pan_number",
					"datatype": "string",
					"discriminator_value": {
						"system": "https://incometax.gov.in/pan",
						"type": {
							"coding": [
								{
									"system": "http://terminology.hl7.org/CodeSystem/v2-0203",
									"code": "TAX",
									"display": "Tax ID",
								}
							]
						},
					},
				}
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		slice_elements = [el for el in result.elements if el.is_slice()]
		self.assertEqual(len(slice_elements), 1)
		self.assertEqual(slice_elements[0].pattern_value["type"]["coding"][0]["code"], "TAX")

	def test_compile_builds_resource_tree(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.id",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "name",
					"datatype": "string",
				},
				{
					"path": "Patient.name.family",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "last_name",
					"datatype": "string",
				},
				{
					"path": "Patient.name.given",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "first_name",
					"datatype": "string",
					"is_array": True,
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		tree = result.resource_tree
		self.assertIsNotNone(tree)

		# Tree root should match metadata resource type
		self.assertEqual(tree.name, result.metadata.resource_type)

		# Elements are compiled
		self.assertEqual(len(result.elements), 3)

		# Tree has children (structure was built)
		self.assertGreater(len(tree.children), 0)

		# Check that tree contains expected structure by checking element parent paths
		id_element = None
		family_element = None
		given_element = None

		for el in result.elements:
			if el.path == "Patient.id":
				id_element = el
			elif el.path == "Patient.name.family":
				family_element = el
			elif el.path == "Patient.name.given":
				given_element = el

		self.assertIsNotNone(id_element)
		self.assertEqual(id_element.transformer, "string")
		self.assertEqual(id_element.parent_path, "Patient")

		self.assertIsNotNone(family_element)
		self.assertEqual(family_element.transformer, "string")
		self.assertEqual(family_element.parent_path, "Patient.name")

		self.assertIsNotNone(given_element)
		self.assertTrue(given_element.is_array)
		self.assertEqual(given_element.parent_path, "Patient.name")

	def test_compile_validates_source_reference(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.gender",
					"source_key": "nonexistent",
					"mapping_type": "field",
					"field": "gender",
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		gender_elements = [el for el in result.elements if el.path == "Patient.gender"]
		self.assertEqual(len(gender_elements), 0)

	def test_compile_validates_extension_source_reference(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"extensions": [
				{
					"path": "Patient",
					"url": "http://example.org/ext",
					"source_key": "invalid",
					"mapping_type": "field",
					"field": "test",
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		ext_elements = [el for el in result.elements if el.is_extension()]
		self.assertEqual(len(ext_elements), 0)

	def test_compile_validates_slice_source_reference(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"slices": [
				{
					"path": "Patient.identifier",
					"slice_name": "test",
					"source_key": "invalid",
					"mapping_type": "field",
					"field": "test",
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		slice_elements = [el for el in result.elements if el.is_slice()]
		self.assertEqual(len(slice_elements), 0)

	def test_compile_skips_duplicate_source(self):
		custom = {
			"sources": [
				{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True},
				{"key": "primary", "doctype": "Other", "kind": "document"},
			],
			"elements": [],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertEqual(len(result.sources), 1)
		self.assertEqual(result.sources[0].entity, "Patient")

	def test_compile_source_missing_key(self):
		custom = {
			"sources": [{"doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertEqual(len(result.sources), 0)

	def test_compile_source_missing_doctype(self):
		custom = {
			"sources": [{"key": "primary", "kind": "document", "is_primary": True}],
			"elements": [],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertEqual(len(result.sources), 0)

	def test_compile_element_missing_path(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{"source_key": "primary", "mapping_type": "field", "field": "name"},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertEqual(len(result.elements), 0)

	def test_compile_extension_missing_url(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"extensions": [
				{"path": "Patient", "source_key": "primary", "mapping_type": "fixed", "fixed_value": "test"},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		ext_elements = [el for el in result.elements if el.is_extension()]
		self.assertEqual(len(ext_elements), 0)

	def test_compile_extension_missing_path(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"extensions": [
				{
					"url": "http://example.org/ext",
					"source_key": "primary",
					"mapping_type": "fixed",
					"fixed_value": "test",
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		ext_elements = [el for el in result.elements if el.is_extension()]
		self.assertEqual(len(ext_elements), 0)

	def test_compile_slice_missing_path(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"slices": [
				{"slice_name": "test", "source_key": "primary", "mapping_type": "field", "field": "test"},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		slice_elements = [el for el in result.elements if el.is_slice()]
		self.assertEqual(len(slice_elements), 0)

	def test_compile_slice_missing_slice_name(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"slices": [
				{
					"path": "Patient.identifier",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "test",
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		slice_elements = [el for el in result.elements if el.is_slice()]
		self.assertEqual(len(slice_elements), 0)

	def test_compile_sets_compiled_at(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		self.assertIsNotNone(result.metadata.compiled_at)

	def test_compile_json_serializable(self):
		import json as json_module

		custom = {
			"metadata": {"fhir_version": "R4"},
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.id",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "name",
					"datatype": "string",
				},
			],
			"extensions": [
				{
					"path": "Patient",
					"url": "http://example.org/ext",
					"value_type": "valueString",
					"source_key": "primary",
					"mapping_type": "fixed",
					"fixed_value": '"test"',
				},
			],
			"slices": [
				{
					"path": "Patient.identifier",
					"slice_name": "mrn",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "name",
					"datatype": "string",
					"discriminator_value": {"system": "http://example.org"},
				},
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		json_str = json_module.dumps(result.to_dict())
		self.assertIsInstance(json_str, str)

		restored = CompiledResource.from_dict(json_module.loads(json_str))
		# Resource type comes from resource_map.resource_type
		self.assertEqual(restored.metadata.resource_type, resource_map.resource_type)


# =============================================================================
# Reference Element Tests
# =============================================================================


class TestCompiledElementReferences(IntegrationTestCase):
	def test_element_is_reference_false_by_default(self):
		element = CompiledElement("Patient.managingOrganization", "primary")

		self.assertFalse(element.is_reference())

	def test_element_is_reference_true(self):
		element = CompiledElement("Patient.managingOrganization", "primary")
		element.reference_type = "Organization"

		self.assertTrue(element.is_reference())

	def test_element_reference_fields_to_dict(self):
		element = CompiledElement("Patient.managingOrganization", "primary")
		element.reference_type = "Organization"
		element.reference_display_field = "organization_name"
		element.is_contained_reference = False

		result = element.to_dict()

		self.assertEqual(result["reference_type"], "Organization")
		self.assertEqual(result["reference_display_field"], "organization_name")
		self.assertFalse(result["is_contained_reference"])

	def test_element_contained_reference(self):
		element = CompiledElement("Patient.managingOrganization", "primary")
		element.reference_type = "Organization"
		element.is_contained_reference = True

		result = element.to_dict()

		self.assertTrue(result["is_contained_reference"])

	def test_element_reference_roundtrip(self):
		original = CompiledElement("Patient.generalPractitioner", "practitioners")
		original.mapping_type = "field"
		original.field = "practitioner"
		original.reference_type = "Practitioner"
		original.reference_display_field = "practitioner_name"
		original.is_contained_reference = False
		original.is_array = True

		data = original.to_dict()
		restored = CompiledElement.from_dict(data)

		self.assertEqual(restored.reference_type, original.reference_type)
		self.assertEqual(restored.reference_display_field, original.reference_display_field)
		self.assertEqual(restored.is_contained_reference, original.is_contained_reference)
		self.assertTrue(restored.is_reference())


class TestFHIRCompilerReferences(IntegrationTestCase):
	def setUp(self):
		self.created_structure_definitions = []
		self.created_resource_maps = []

	def tearDown(self):
		self._cleanup_test_data()

	def _cleanup_test_data(self):
		for name in self.created_resource_maps:
			if frappe.db.exists("FHIR Resource Map", name):
				frappe.delete_doc("FHIR Resource Map", name, force=True)

		for name in self.created_structure_definitions:
			if frappe.db.exists("FHIR Structure Definition", name):
				frappe.delete_doc("FHIR Structure Definition", name, force=True)

		self.created_resource_maps = []
		self.created_structure_definitions = []
		frappe.db.commit()

	def _create_resource_map(self, custom_elements, primary_doctype=None):
		import json as json_module
		import uuid

		suffix = uuid.uuid4().hex[:8]
		sd_fhir_sd = f"TestSD{suffix}"

		sd = frappe.get_doc(
			{
				"doctype": "FHIR Structure Definition",
				"fhir_sd": sd_fhir_sd,
				"fhir_version": "R4",
			}
		)
		sd.flags.ignore_validate = True
		sd.flags.ignore_mandatory = True
		sd.insert(ignore_permissions=True)
		sd_name = sd.name
		self.created_structure_definitions.append(sd_name)

		doc_data = {
			"doctype": "FHIR Resource Map",
			"resource_type": "Patient",
			"base_structure_definition": sd_name,
			"custom_elements": json_module.dumps(custom_elements),
		}

		if primary_doctype:
			doc_data["primary_doctype"] = primary_doctype

		doc = frappe.get_doc(doc_data)
		doc.insert(ignore_permissions=True)
		self.created_resource_maps.append(doc.name)
		frappe.db.commit()

		return doc

	def test_compile_reference_element(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.managingOrganization",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "organization",
					"datatype": "Reference",
					"reference_type": "Organization",
					"reference_display_field": "organization_name",
				}
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		ref_elements = [el for el in result.elements if el.is_reference()]
		self.assertEqual(len(ref_elements), 1)
		self.assertEqual(ref_elements[0].reference_type, "Organization")
		self.assertEqual(ref_elements[0].reference_display_field, "organization_name")
		self.assertFalse(ref_elements[0].is_contained_reference)

	def test_compile_contained_reference_element(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.managingOrganization",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "organization",
					"datatype": "Reference",
					"reference_type": "Organization",
					"is_contained_reference": True,
				}
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		ref_elements = [el for el in result.elements if el.is_reference()]
		self.assertEqual(len(ref_elements), 1)
		self.assertTrue(ref_elements[0].is_contained_reference)

	def test_compile_array_reference_element(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.generalPractitioner",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "practitioner",
					"datatype": "Reference",
					"reference_type": "Practitioner",
					"is_array": True,
				}
			],
		}
		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		ref_elements = [el for el in result.elements if el.is_reference()]
		self.assertEqual(len(ref_elements), 1)
		self.assertTrue(ref_elements[0].is_array)


class TestFHIRCompilerHybridMode(IntegrationTestCase):
	"""Test that custom_elements extends UI config when primary_doctype is set"""

	def setUp(self):
		self.created_structure_definitions = []
		self.created_resource_maps = []
		self._create_base_fixtures()

	def tearDown(self):
		self._cleanup_test_data()

	def _create_base_fixtures(self):
		if not frappe.db.exists("FHIR Structure Definition", "Patient-R4"):
			frappe.get_doc(
				{
					"doctype": "FHIR Structure Definition",
					"name": "Patient-R4",
					"fhir_sd": "Patient",
					"fhir_version": "R4",
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()

	def _cleanup_test_data(self):
		for name in self.created_resource_maps:
			if frappe.db.exists("FHIR Resource Map", name):
				frappe.delete_doc("FHIR Resource Map", name, force=True)

		for name in self.created_structure_definitions:
			if frappe.db.exists("FHIR Structure Definition", name):
				frappe.delete_doc("FHIR Structure Definition", name, force=True)

		self.created_resource_maps = []
		self.created_structure_definitions = []
		frappe.db.commit()

	def _create_resource_map_with_ui_config(self, custom_elements=None):
		import json as json_module
		import uuid

		suffix = uuid.uuid4().hex[:8]
		name = f"Patient-HybridTest-{suffix}"

		doc_data = {
			"doctype": "FHIR Resource Map",
			"name": name,
			"resource_type": "Patient",
			"primary_doctype": "Patient",
			"base_structure_definition": "Patient-R4",
			"element_maps": [
				{
					"fhir_path": "Patient.id",
					"datatype": "string",
					"min": 0,
					"max": "1",
					"mapping_type": "Frappe Field",
					"frappe_field": "name",
				},
				{
					"fhir_path": "Patient.birthDate",
					"datatype": "date",
					"min": 0,
					"max": "1",
					"mapping_type": "Frappe Field",
					"frappe_field": "dob",
				},
			],
		}

		if custom_elements:
			doc_data["custom_elements"] = json_module.dumps(custom_elements)

		doc = frappe.get_doc(doc_data)
		doc.insert(ignore_permissions=True)
		self.created_resource_maps.append(doc.name)
		frappe.db.commit()

		return doc

	def test_hybrid_mode_detection(self):
		"""When primary_doctype is set, should NOT be custom-only mode even with custom sources"""
		custom = {
			"sources": [
				{"key": "extra", "doctype": "Company", "kind": "direct_link", "link_field": "company"}
			],
			"elements": [],
		}
		resource_map = self._create_resource_map_with_ui_config(custom)
		compiler = FHIRCompiler(resource_map)
		compiler._custom_elements = compiler._parse_custom_elements()

		self.assertFalse(compiler._is_custom_only_mode())

	def test_hybrid_mode_includes_ui_elements(self):
		"""UI-configured elements should be present"""
		custom = {
			"elements": [
				{
					"path": "Patient.active",
					"source_key": "primary",
					"mapping_type": "fixed",
					"fixed_value": "true",
					"datatype": "boolean",
				}
			],
		}
		resource_map = self._create_resource_map_with_ui_config(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		# Check UI elements are present
		id_element = None
		birth_date_element = None
		for el in result.elements:
			if el.path == "Patient.id":
				id_element = el
			elif el.path == "Patient.birthDate":
				birth_date_element = el

		self.assertIsNotNone(id_element)
		self.assertIsNotNone(birth_date_element)

	def test_hybrid_mode_includes_custom_elements(self):
		"""Custom elements should be added to UI elements"""
		custom = {
			"elements": [
				{
					"path": "Patient.active",
					"source_key": "primary",
					"mapping_type": "fixed",
					"fixed_value": "true",
					"datatype": "boolean",
				}
			],
		}
		resource_map = self._create_resource_map_with_ui_config(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		# Check custom element is present
		active_element = None
		for el in result.elements:
			if el.path == "Patient.active":
				active_element = el

		self.assertIsNotNone(active_element)
		self.assertEqual(active_element.mapping_type, CompiledElement.MAPPING_FIXED)

	def test_hybrid_mode_adds_custom_sources(self):
		"""Custom sources should be added to UI sources"""
		custom = {
			"sources": [{"key": "gender", "doctype": "Gender", "kind": "direct_link", "link_field": "sex"}],
			"elements": [],
		}
		resource_map = self._create_resource_map_with_ui_config(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		# Check primary source exists
		primary = result.get_primary_source()
		self.assertIsNotNone(primary)

		# Check custom source exists
		gender_source = result.get_source("gender")
		self.assertIsNotNone(gender_source)
		self.assertEqual(gender_source.entity, "Gender")

	def test_hybrid_mode_adds_custom_extension(self):
		"""Custom extensions should be added"""
		custom = {
			"extensions": [
				{
					"path": "Patient",
					"url": "http://example.org/religion",
					"value_type": "valueString",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "religion",
				}
			],
		}
		resource_map = self._create_resource_map_with_ui_config(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		ext_elements = [el for el in result.elements if el.is_extension()]
		self.assertEqual(len(ext_elements), 1)

	def test_hybrid_mode_adds_custom_reference(self):
		"""Custom reference elements should be added"""
		custom = {
			"elements": [
				{
					"path": "Patient.managingOrganization",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "customer",
					"datatype": "Reference",
					"reference_type": "Customer",
					"reference_display_field": "customer",
				}
			],
		}
		resource_map = self._create_resource_map_with_ui_config(custom)
		compiler = FHIRCompiler(resource_map)

		result = compiler.compile()

		ref_elements = [el for el in result.elements if el.is_reference()]
		self.assertEqual(len(ref_elements), 1)
		self.assertEqual(ref_elements[0].reference_type, "Customer")


# =============================================================================
# Data Classes Tests
# =============================================================================


class TestCompilationMetadata(IntegrationTestCase):
	"""Test CompilationMetadata data class"""

	def test_create_metadata(self):
		metadata = CompilationMetadata("R4", "http://example.org/Patient", "Patient")

		self.assertEqual(metadata.fhir_version, "R4")
		self.assertEqual(metadata.profile_url, "http://example.org/Patient")
		self.assertEqual(metadata.resource_type, "Patient")
		# compiled_at is set by the compiler, not on direct creation
		self.assertIsNone(metadata.compiled_at)

	def test_metadata_serialization(self):
		metadata = CompilationMetadata("R4", "http://example.org/Patient", "Patient")

		data = metadata.to_dict()
		restored = CompilationMetadata.from_dict(data)

		self.assertEqual(restored.fhir_version, "R4")
		self.assertEqual(restored.profile_url, "http://example.org/Patient")
		self.assertEqual(restored.resource_type, "Patient")


class TestCompiledSource(IntegrationTestCase):
	"""Test CompiledSource data class"""

	def test_create_source(self):
		source = CompiledSource("primary", "Patient", "document")

		self.assertEqual(source.key, "primary")
		self.assertEqual(source.entity, "Patient")
		self.assertEqual(source.entity_type, "document")
		self.assertFalse(source.is_primary)
		self.assertFalse(source.is_collection)

	def test_source_serialization(self):
		source = CompiledSource("addresses", "Patient Address", "child_table")
		source.is_collection = True
		source.parent_source_key = "primary"
		source.link_field = "patient_addresses"

		data = source.to_dict()
		restored = CompiledSource.from_dict(data)

		self.assertEqual(restored.key, "addresses")
		self.assertEqual(restored.entity, "Patient Address")
		self.assertEqual(restored.entity_type, "child_table")
		self.assertTrue(restored.is_collection)
		self.assertEqual(restored.parent_source_key, "primary")
		self.assertEqual(restored.link_field, "patient_addresses")

	def test_source_with_filters(self):
		source = CompiledSource("encounters", "Patient Encounter", "reverse_link")
		source.filters = {"status": "completed"}

		data = source.to_dict()
		restored = CompiledSource.from_dict(data)

		self.assertEqual(restored.filters, {"status": "completed"})


class TestCompiledElement(IntegrationTestCase):
	"""Test CompiledElement data class"""

	def test_create_element(self):
		element = CompiledElement("Patient.id", "primary")

		self.assertEqual(element.path, "Patient.id")
		self.assertEqual(element.source_key, "primary")
		self.assertIsNone(element.mapping_type)
		self.assertFalse(element.is_array)

	def test_element_field_mapping(self):
		element = CompiledElement("Patient.birthDate", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "dob"
		element.transformer = "date"

		self.assertEqual(element.mapping_type, "field")
		self.assertEqual(element.field, "dob")
		self.assertEqual(element.transformer, "date")
		self.assertTrue(element.has_mapping())

	def test_element_fixed_mapping(self):
		element = CompiledElement("Patient.active", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIXED
		element.fixed_value = "true"

		self.assertEqual(element.mapping_type, "fixed")
		self.assertEqual(element.fixed_value, "true")
		self.assertTrue(element.has_mapping())

	def test_element_expression_mapping(self):
		element = CompiledElement("Patient.deceasedBoolean", "primary")
		element.mapping_type = CompiledElement.MAPPING_EXPRESSION
		element.expression = "doc.get('status') == 'Deceased'"

		self.assertEqual(element.mapping_type, "expression")
		self.assertEqual(element.expression, "doc.get('status') == 'Deceased'")
		self.assertTrue(element.has_mapping())

	def test_element_json_mapping(self):
		element = CompiledElement("Patient.meta", "primary")
		element.mapping_type = CompiledElement.MAPPING_JSON
		element.json_value = {"profile": ["http://example.org/Patient"]}

		self.assertEqual(element.mapping_type, "json")
		self.assertEqual(element.json_value, {"profile": ["http://example.org/Patient"]})
		self.assertTrue(element.has_mapping())

	def test_element_serialization(self):
		element = CompiledElement("Patient.birthDate", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "dob"
		element.transformer = "date"
		element.is_required = True
		element.parent_path = "Patient"

		data = element.to_dict()
		restored = CompiledElement.from_dict(data)

		self.assertEqual(restored.path, "Patient.birthDate")
		self.assertEqual(restored.source_key, "primary")
		self.assertEqual(restored.mapping_type, "field")
		self.assertEqual(restored.field, "dob")
		self.assertEqual(restored.transformer, "date")
		self.assertTrue(restored.is_required)
		self.assertEqual(restored.parent_path, "Patient")


class TestCompiledElementExtension(IntegrationTestCase):
	"""Test CompiledElement extension support"""

	def test_extension_fields(self):
		element = CompiledElement("Patient.extension", "primary")
		element.extension_url = "http://example.org/ext"
		element.extension_value_type = "string"

		self.assertTrue(element.is_extension())
		self.assertEqual(element.extension_url, "http://example.org/ext")
		self.assertEqual(element.extension_value_type, "string")
		self.assertFalse(element.is_modifier_extension)

	def test_modifier_extension(self):
		element = CompiledElement("Patient.modifierExtension", "primary")
		element.extension_url = "http://example.org/mod-ext"
		element.extension_value_type = "boolean"
		element.is_modifier_extension = True

		self.assertTrue(element.is_extension())
		self.assertTrue(element.is_modifier_extension)

	def test_extension_serialization(self):
		element = CompiledElement("Patient.extension", "primary")
		element.extension_url = "http://example.org/ext"
		element.extension_value_type = "CodeableConcept"
		element.is_modifier_extension = False

		data = element.to_dict()
		restored = CompiledElement.from_dict(data)

		self.assertEqual(restored.extension_url, "http://example.org/ext")
		self.assertEqual(restored.extension_value_type, "CodeableConcept")
		self.assertFalse(restored.is_modifier_extension)


class TestCompiledElementSlice(IntegrationTestCase):
	"""Test CompiledElement slice support"""

	def test_slice_fields(self):
		element = CompiledElement("Patient.identifier", "primary")
		element.slice_name = "mrn"
		element.slice_of = "Patient.identifier"
		element.pattern_value = {"system": "http://example.org/mrn"}

		self.assertTrue(element.is_slice())
		self.assertEqual(element.slice_name, "mrn")
		self.assertEqual(element.slice_of, "Patient.identifier")
		self.assertTrue(element.has_pattern())

	def test_slice_serialization(self):
		element = CompiledElement("Patient.identifier", "primary")
		element.slice_name = "passport"
		element.slice_of = "Patient.identifier"
		element.pattern_value = {
			"type": {"coding": [{"code": "PPN"}]},
			"system": "http://example.org/passport",
		}

		data = element.to_dict()
		restored = CompiledElement.from_dict(data)

		self.assertEqual(restored.slice_name, "passport")
		self.assertEqual(restored.slice_of, "Patient.identifier")
		self.assertEqual(restored.pattern_value["type"]["coding"][0]["code"], "PPN")


class TestCompiledElementReference(IntegrationTestCase):
	"""Test CompiledElement reference support"""

	def test_reference_fields(self):
		element = CompiledElement("Patient.managingOrganization", "primary")
		element.reference_type = "Organization"
		element.reference_display_field = "organization_name"

		self.assertTrue(element.is_reference())
		self.assertEqual(element.reference_type, "Organization")
		self.assertEqual(element.reference_display_field, "organization_name")

	def test_simple_contained_reference(self):
		element = CompiledElement("Patient.generalPractitioner", "primary")
		element.is_contained_reference = True

		self.assertTrue(element.is_reference())
		self.assertTrue(element.is_contained_reference)
		self.assertFalse(element.is_full_contained_reference())

	def test_full_contained_reference(self):
		element = CompiledElement("Patient.managingOrganization", "primary")
		element.reference_type = "Organization"
		element.is_contained_reference = True
		element.contained_resource_map = "Organization-Organization-R4"
		element.contained_id_field = "name"

		self.assertTrue(element.is_reference())
		self.assertTrue(element.is_contained_reference)
		self.assertTrue(element.is_full_contained_reference())
		self.assertEqual(element.contained_resource_map, "Organization-Organization-R4")
		self.assertEqual(element.contained_id_field, "name")

	def test_reference_serialization(self):
		element = CompiledElement("Patient.managingOrganization", "primary")
		element.reference_type = "Organization"
		element.is_contained_reference = True
		element.contained_resource_map = "Organization-Organization-R4"
		element.contained_id_field = "name"

		data = element.to_dict()
		restored = CompiledElement.from_dict(data)

		self.assertEqual(restored.reference_type, "Organization")
		self.assertTrue(restored.is_contained_reference)
		self.assertEqual(restored.contained_resource_map, "Organization-Organization-R4")
		self.assertEqual(restored.contained_id_field, "name")
		self.assertTrue(restored.is_full_contained_reference())


class TestResourceTreeNode(IntegrationTestCase):
	"""Test ResourceTreeNode data class"""

	def test_create_node(self):
		node = ResourceTreeNode("Patient")

		self.assertEqual(node.name, "Patient")
		self.assertFalse(node.is_array)
		self.assertFalse(node.is_primitive)
		self.assertEqual(len(node.children), 0)

	def test_add_child(self):
		root = ResourceTreeNode("Patient")
		child = ResourceTreeNode("name")
		child.is_array = True

		root.add_child(child)

		self.assertEqual(len(root.children), 1)
		self.assertEqual(root.children[0].name, "name")
		self.assertTrue(root.children[0].is_array)

	def test_find_child(self):
		root = ResourceTreeNode("Patient")
		root.add_child(ResourceTreeNode("id"))
		root.add_child(ResourceTreeNode("name"))
		root.add_child(ResourceTreeNode("birthDate"))

		found = root.find_child("name")

		self.assertIsNotNone(found)
		self.assertEqual(found.name, "name")

	def test_find_child_not_found(self):
		root = ResourceTreeNode("Patient")
		root.add_child(ResourceTreeNode("id"))

		found = root.find_child("nonexistent")

		self.assertIsNone(found)

	def test_find_by_path(self):
		root = ResourceTreeNode("Patient")
		name = ResourceTreeNode("name")
		name.is_array = True
		family = ResourceTreeNode("family")
		name.add_child(family)
		root.add_child(name)

		found = root.find_by_path("Patient.name.family")

		self.assertIsNotNone(found)
		self.assertEqual(found.name, "family")

	def test_tree_serialization(self):
		root = ResourceTreeNode("Patient")
		name = ResourceTreeNode("name")
		name.is_array = True
		family = ResourceTreeNode("family")
		family.is_primitive = True
		name.add_child(family)
		root.add_child(name)

		data = root.to_dict()
		restored = ResourceTreeNode.from_dict(data)

		self.assertEqual(restored.name, "Patient")
		self.assertEqual(len(restored.children), 1)
		self.assertEqual(restored.children[0].name, "name")
		self.assertTrue(restored.children[0].is_array)
		self.assertEqual(restored.children[0].children[0].name, "family")
		self.assertTrue(restored.children[0].children[0].is_primitive)


class TestCompiledResource(IntegrationTestCase):
	"""Test CompiledResource data class"""

	def test_create_compiled_resource(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		compiled = CompiledResource(metadata)

		self.assertEqual(compiled.metadata.resource_type, "Patient")
		self.assertEqual(len(compiled.sources), 0)
		self.assertEqual(len(compiled.elements), 0)

	def test_add_source(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		compiled = CompiledResource(metadata)

		source = CompiledSource("primary", "Patient", "document")
		source.is_primary = True
		compiled.add_source(source)

		self.assertEqual(len(compiled.sources), 1)
		self.assertEqual(compiled.sources[0].key, "primary")

	def test_add_element(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		compiled = CompiledResource(metadata)

		element = CompiledElement("Patient.id", "primary")
		compiled.add_element(element)

		self.assertEqual(len(compiled.elements), 1)
		self.assertEqual(compiled.elements[0].path, "Patient.id")

	def test_get_source(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		compiled = CompiledResource(metadata)

		source1 = CompiledSource("primary", "Patient", "document")
		source2 = CompiledSource("gender", "Gender", "direct_link")
		compiled.add_source(source1)
		compiled.add_source(source2)

		found = compiled.get_source("gender")

		self.assertIsNotNone(found)
		self.assertEqual(found.entity, "Gender")

	def test_get_primary_source(self):
		metadata = CompilationMetadata("R4", None, "Patient")
		compiled = CompiledResource(metadata)

		source1 = CompiledSource("primary", "Patient", "document")
		source1.is_primary = True
		source2 = CompiledSource("gender", "Gender", "direct_link")
		compiled.add_source(source1)
		compiled.add_source(source2)

		primary = compiled.get_primary_source()

		self.assertIsNotNone(primary)
		self.assertEqual(primary.key, "primary")

	def test_compiled_resource_serialization(self):
		metadata = CompilationMetadata("R4", "http://example.org/Patient", "Patient")
		compiled = CompiledResource(metadata)

		source = CompiledSource("primary", "Patient", "document")
		source.is_primary = True
		compiled.add_source(source)

		element = CompiledElement("Patient.id", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "name"
		compiled.add_element(element)

		tree = ResourceTreeNode("Patient")
		tree.add_child(ResourceTreeNode("id"))
		compiled.resource_tree = tree

		data = compiled.to_dict()
		restored = CompiledResource.from_dict(data)

		self.assertEqual(restored.metadata.resource_type, "Patient")
		self.assertEqual(len(restored.sources), 1)
		self.assertEqual(len(restored.elements), 1)
		self.assertIsNotNone(restored.resource_tree)
		self.assertEqual(restored.resource_tree.name, "Patient")


# =============================================================================
# Compiler Tests
# =============================================================================


class TestFHIRCompilerCustomElements(IntegrationTestCase):
	"""Test FHIRCompiler with custom_elements JSON"""

	def _create_mock_resource_map(self, custom_elements):
		"""Create a mock resource map object"""

		class MockResourceMap:
			def __init__(self):
				self.name = "Test-Patient-R4"
				self.resource_type = "Patient"
				self.base_structure_definition = None
				self.primary_doctype = None
				self.fhir_element_map = []
				self.fhir_resource_map_source = []
				self.custom_elements = json.dumps(custom_elements) if custom_elements else None

		return MockResourceMap()

	def test_compile_simple_custom_elements(self):
		custom_elements = {
			"metadata": {"fhir_version": "R4", "resource_type": "Patient"},
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{"path": "Patient.id", "source_key": "primary", "mapping_type": "field", "field": "name"}
			],
		}

		resource_map = self._create_mock_resource_map(custom_elements)
		compiler = FHIRCompiler(resource_map)
		result = compiler.compile()

		self.assertEqual(result.metadata.resource_type, "Patient")
		self.assertEqual(len(result.sources), 1)
		self.assertEqual(len(result.elements), 1)
		self.assertEqual(result.elements[0].path, "Patient.id")
		self.assertEqual(result.elements[0].field, "name")

	def test_compile_with_extensions(self):
		custom_elements = {
			"metadata": {"fhir_version": "R4", "resource_type": "Patient"},
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"extensions": [
				{
					"url": "http://example.org/religion",
					"path": "Patient.extension",
					"source_key": "primary",
					"value_type": "string",
					"mapping_type": "field",
					"field": "religion",
				}
			],
		}

		resource_map = self._create_mock_resource_map(custom_elements)
		compiler = FHIRCompiler(resource_map)
		result = compiler.compile()

		extensions = [e for e in result.elements if e.is_extension()]
		self.assertEqual(len(extensions), 1)
		self.assertEqual(extensions[0].extension_url, "http://example.org/religion")
		self.assertEqual(extensions[0].extension_value_type, "string")

	def test_compile_with_slices(self):
		custom_elements = {
			"metadata": {"fhir_version": "R4", "resource_type": "Patient"},
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"slices": [
				{
					"slice_of": "Patient.identifier",
					"slice_name": "mrn",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "mrn",
					"pattern": {"system": "http://example.org/mrn"},
				}
			],
		}

		resource_map = self._create_mock_resource_map(custom_elements)
		compiler = FHIRCompiler(resource_map)
		result = compiler.compile()

		slices = [e for e in result.elements if e.is_slice()]
		self.assertEqual(len(slices), 1)
		self.assertEqual(slices[0].slice_name, "mrn")
		self.assertEqual(slices[0].slice_of, "Patient.identifier")
		self.assertEqual(slices[0].pattern_value["system"], "http://example.org/mrn")

	def test_compile_with_contained_reference(self):
		custom_elements = {
			"metadata": {"fhir_version": "R4", "resource_type": "Patient"},
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.managingOrganization",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "organization",
					"reference_type": "Organization",
					"is_contained_reference": True,
					"contained_resource_map": "Organization-Organization-R4",
					"contained_id_field": "name",
				}
			],
		}

		resource_map = self._create_mock_resource_map(custom_elements)
		compiler = FHIRCompiler(resource_map)
		result = compiler.compile()

		refs = [e for e in result.elements if e.is_reference()]
		self.assertEqual(len(refs), 1)
		self.assertTrue(refs[0].is_contained_reference)
		self.assertTrue(refs[0].is_full_contained_reference())
		self.assertEqual(refs[0].contained_resource_map, "Organization-Organization-R4")

	def test_compile_multiple_sources(self):
		custom_elements = {
			"metadata": {"fhir_version": "R4", "resource_type": "Patient"},
			"sources": [
				{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True},
				{"key": "gender", "doctype": "Gender", "kind": "direct_link", "link_field": "gender"},
				{
					"key": "addresses",
					"doctype": "Patient Address",
					"kind": "child_table",
					"link_field": "addresses",
					"is_collection": True,
				},
			],
			"elements": [
				{"path": "Patient.id", "source_key": "primary", "mapping_type": "field", "field": "name"},
				{
					"path": "Patient.gender",
					"source_key": "gender",
					"mapping_type": "field",
					"field": "fhir_code",
				},
				{
					"path": "Patient.address.city",
					"source_key": "addresses",
					"mapping_type": "field",
					"field": "city",
				},
			],
		}

		resource_map = self._create_mock_resource_map(custom_elements)
		compiler = FHIRCompiler(resource_map)
		result = compiler.compile()

		self.assertEqual(len(result.sources), 3)
		self.assertEqual(len(result.elements), 3)

		gender_source = result.get_source("gender")
		self.assertIsNotNone(gender_source)
		self.assertEqual(gender_source.entity_type, "direct_link")

		addresses_source = result.get_source("addresses")
		self.assertIsNotNone(addresses_source)
		self.assertTrue(addresses_source.is_collection)


class TestFHIRCompilerTransformers(IntegrationTestCase):
	"""Test FHIRCompiler transformer assignment"""

	def _create_mock_resource_map(self, custom_elements):
		class MockResourceMap:
			def __init__(self):
				self.name = "Test-Patient-R4"
				self.resource_type = "Patient"
				self.base_structure_definition = None
				self.primary_doctype = None
				self.fhir_element_map = []
				self.fhir_resource_map_source = []
				self.custom_elements = json.dumps(custom_elements) if custom_elements else None

		return MockResourceMap()

	def test_primitive_transformers(self):
		custom_elements = {
			"metadata": {"fhir_version": "R4", "resource_type": "Patient"},
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [
				{
					"path": "Patient.id",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "name",
					"datatype": "id",
				},
				{
					"path": "Patient.active",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "enabled",
					"datatype": "boolean",
				},
				{
					"path": "Patient.birthDate",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "dob",
					"datatype": "date",
				},
				{
					"path": "Patient.gender",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "sex",
					"datatype": "code",
				},
			],
		}

		resource_map = self._create_mock_resource_map(custom_elements)
		compiler = FHIRCompiler(resource_map)
		result = compiler.compile()

		elements_by_path = {e.path: e for e in result.elements}

		self.assertEqual(elements_by_path["Patient.id"].transformer, "id")
		self.assertEqual(elements_by_path["Patient.active"].transformer, "boolean")
		self.assertEqual(elements_by_path["Patient.birthDate"].transformer, "date")
		self.assertEqual(elements_by_path["Patient.gender"].transformer, "code")


class TestFHIRCompilationError(IntegrationTestCase):
	"""Test FHIRCompilationError"""

	def test_error_creation(self):
		error = FHIRCompilationError("Invalid mapping", path="Patient.invalid", details={"field": "test"})

		self.assertEqual(error.message, "Invalid mapping")
		self.assertEqual(error.path, "Patient.invalid")
		self.assertEqual(error.details["field"], "test")

	def test_error_to_dict(self):
		error = FHIRCompilationError("Missing source", path="Patient.id", details={"source_key": "unknown"})

		data = error.to_dict()

		self.assertEqual(data["message"], "Missing source")
		self.assertEqual(data["path"], "Patient.id")
		self.assertEqual(data["details"]["source_key"], "unknown")
