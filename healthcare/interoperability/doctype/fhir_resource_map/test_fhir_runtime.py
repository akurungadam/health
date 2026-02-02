import json

import frappe
from frappe.tests import IntegrationTestCase

from healthcare.interoperability.doctype.fhir_resource_map.fhir_compiler import (
	CompilationMetadata,
	CompiledElement,
	CompiledResource,
	CompiledSource,
	FHIRCompiler,
	ResourceTreeNode,
)
from healthcare.interoperability.doctype.fhir_resource_map.fhir_runtime import (
	FHIRRuntime,
	FrappeSourceResolver,
	ValueResolver,
)

# =============================================================================
# ValueResolver Tests (No database needed)
# =============================================================================


class TestValueResolverFieldExtraction(IntegrationTestCase):
	def test_extract_simple_field(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.id", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "name"

		sources_data = {"primary": {"name": "PAT-001", "dob": "1990-01-15"}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result, "PAT-001")

	def test_extract_nested_field(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.telecom.value", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "contact.phone"

		sources_data = {"primary": {"contact": {"phone": "+1234567890", "email": "test@example.com"}}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result, "+1234567890")

	def test_extract_missing_field_returns_none(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.language", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "language"

		sources_data = {"primary": {"name": "PAT-001"}}

		result = resolver.resolve(element, sources_data)

		self.assertIsNone(result)

	def test_extract_missing_source_returns_none(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.gender", "gender")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "name"

		sources_data = {"primary": {"name": "PAT-001"}}

		result = resolver.resolve(element, sources_data)

		self.assertIsNone(result)


class TestValueResolverFixedValue(IntegrationTestCase):
	def test_fixed_value_string(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.language", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIXED
		element.fixed_value = '"en"'

		sources_data = {"primary": {}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result, "en")

	def test_fixed_value_boolean_true(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.active", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIXED
		element.fixed_value = "true"
		element.transformer = "boolean"

		sources_data = {"primary": {}}

		result = resolver.resolve(element, sources_data)

		self.assertTrue(result)

	def test_fixed_value_json_object(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.maritalStatus", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIXED
		element.fixed_value = '{"coding": [{"code": "M"}]}'

		sources_data = {"primary": {}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result, {"coding": [{"code": "M"}]})

	def test_fixed_value_plain_string(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.language", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIXED
		element.fixed_value = "en"

		sources_data = {"primary": {}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result, "en")


class TestValueResolverExpression(IntegrationTestCase):
	def test_expression_concatenation(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.name.text", "primary")
		element.mapping_type = CompiledElement.MAPPING_EXPRESSION
		element.expression = "doc.get('first_name', '') + ' ' + doc.get('last_name', '')"

		sources_data = {"primary": {"first_name": "John", "last_name": "Doe"}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result, "John Doe")

	def test_expression_conditional(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.gender", "primary")
		element.mapping_type = CompiledElement.MAPPING_EXPRESSION
		element.expression = "'male' if doc.get('sex') == 'Male' else 'female'"

		sources_data = {"primary": {"sex": "Male"}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result, "male")

	def test_expression_invalid_returns_none(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.test", "primary")
		element.mapping_type = CompiledElement.MAPPING_EXPRESSION
		element.expression = "invalid syntax here {{{"

		sources_data = {"primary": {}}

		result = resolver.resolve(element, sources_data)

		self.assertIsNone(result)


class TestValueResolverJson(IntegrationTestCase):
	def test_json_value(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.maritalStatus", "primary")
		element.mapping_type = CompiledElement.MAPPING_JSON
		element.json_value = {"coding": [{"system": "http://example.org", "code": "M"}]}

		sources_data = {"primary": {}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result, {"coding": [{"system": "http://example.org", "code": "M"}]})


class TestValueResolverDefaults(IntegrationTestCase):
	def test_default_applied_when_none(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.language", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "language"
		element.default_value = '"en"'

		sources_data = {"primary": {"language": None}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result, "en")

	def test_default_applied_when_empty_string(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.language", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "language"
		element.default_value = '"en"'

		sources_data = {"primary": {"language": ""}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result, "en")

	def test_default_not_applied_when_value_exists(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.language", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "language"
		element.default_value = '"en"'

		sources_data = {"primary": {"language": "fr"}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result, "fr")


class TestValueResolverTransformers(IntegrationTestCase):
	def test_transformer_string(self):
		resolver = ValueResolver()

		self.assertEqual(resolver._apply_transformer("string", 123), "123")
		self.assertEqual(resolver._apply_transformer("string", True), "True")
		self.assertIsNone(resolver._apply_transformer("string", None))

	def test_transformer_boolean(self):
		resolver = ValueResolver()

		self.assertTrue(resolver._apply_transformer("boolean", True))
		self.assertTrue(resolver._apply_transformer("boolean", "true"))
		self.assertTrue(resolver._apply_transformer("boolean", "1"))
		self.assertTrue(resolver._apply_transformer("boolean", "yes"))
		self.assertFalse(resolver._apply_transformer("boolean", False))
		self.assertFalse(resolver._apply_transformer("boolean", "false"))
		self.assertFalse(resolver._apply_transformer("boolean", "0"))

	def test_transformer_integer(self):
		resolver = ValueResolver()

		self.assertEqual(resolver._apply_transformer("integer", "42"), 42)
		self.assertEqual(resolver._apply_transformer("integer", 42.7), 42)
		self.assertIsNone(resolver._apply_transformer("integer", "not a number"))

	def test_transformer_decimal(self):
		resolver = ValueResolver()

		self.assertEqual(resolver._apply_transformer("decimal", "3.14"), 3.14)
		self.assertEqual(resolver._apply_transformer("decimal", 3), 3.0)
		self.assertIsNone(resolver._apply_transformer("decimal", "not a number"))

	def test_transformer_date(self):
		from datetime import date

		resolver = ValueResolver()

		result = resolver._apply_transformer("date", date(2026, 1, 15))
		self.assertEqual(result, "2026-01-15")

		result = resolver._apply_transformer("date", "2026-01-15 12:00:00")
		self.assertEqual(result, "2026-01-15")

	def test_transformer_datetime(self):
		from datetime import datetime

		resolver = ValueResolver()

		dt = datetime(2026, 1, 15, 12, 30, 45)
		result = resolver._apply_transformer("datetime", dt)
		self.assertIn("2026-01-15", result)

	def test_transformer_code(self):
		resolver = ValueResolver()

		self.assertEqual(resolver._apply_transformer("code", "male"), "male")

	def test_transformer_positiveint(self):
		resolver = ValueResolver()

		self.assertEqual(resolver._apply_transformer("positiveint", "5"), 5)
		self.assertIsNone(resolver._apply_transformer("positiveint", "-1"))

	def test_transformer_unsignedint(self):
		resolver = ValueResolver()

		self.assertEqual(resolver._apply_transformer("unsignedint", "0"), 0)
		self.assertIsNone(resolver._apply_transformer("unsignedint", "-1"))


class TestValueResolverReferences(IntegrationTestCase):
	def test_build_reference_simple(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.managingOrganization", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "organization"
		element.reference_type = "Organization"

		sources_data = {"primary": {"organization": "ORG-001"}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result["reference"], "Organization/ORG-001")
		self.assertEqual(result["type"], "Organization")

	def test_build_reference_with_display(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.managingOrganization", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "organization"
		element.reference_type = "Organization"
		element.reference_display_field = "organization_name"

		sources_data = {"primary": {"organization": "ORG-001", "organization_name": "City Hospital"}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result["reference"], "Organization/ORG-001")
		self.assertEqual(result["display"], "City Hospital")

	def test_build_contained_reference(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.managingOrganization", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "organization"
		element.reference_type = "Organization"
		element.is_contained_reference = True

		sources_data = {"primary": {"organization": "org-1"}}

		result = resolver.resolve(element, sources_data)

		self.assertEqual(result["reference"], "#org-1")
		self.assertNotIn("type", result)

	def test_build_reference_null_value(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.managingOrganization", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "organization"
		element.reference_type = "Organization"

		sources_data = {"primary": {"organization": None}}

		result = resolver.resolve(element, sources_data)

		self.assertIsNone(result)

	def test_build_reference_empty_value(self):
		resolver = ValueResolver()
		element = CompiledElement("Patient.managingOrganization", "primary")
		element.mapping_type = CompiledElement.MAPPING_FIELD
		element.field = "organization"
		element.reference_type = "Organization"

		sources_data = {"primary": {"organization": ""}}

		result = resolver.resolve(element, sources_data)

		self.assertIsNone(result)


# =============================================================================
# Helper to build compiled resources manually (no database)
# =============================================================================


class CompiledResourceBuilder:
	"""Helper to build CompiledResource objects for testing"""

	def __init__(self, resource_type="Patient"):
		self.resource_type = resource_type
		self.sources = []
		self.elements = []
		self.extensions = []
		self.slices = []

	def add_source(self, key, entity, entity_type="document", is_primary=False, link_field=None):
		self.sources.append(
			{
				"key": key,
				"entity": entity,
				"entity_type": entity_type,
				"is_primary": is_primary,
				"link_field": link_field,
			}
		)
		return self

	def add_element(
		self,
		path,
		source_key,
		mapping_type,
		field=None,
		fixed_value=None,
		expression=None,
		transformer=None,
		is_array=False,
		reference_type=None,
		reference_display_field=None,
	):
		self.elements.append(
			{
				"path": path,
				"source_key": source_key,
				"mapping_type": mapping_type,
				"field": field,
				"fixed_value": fixed_value,
				"expression": expression,
				"transformer": transformer,
				"is_array": is_array,
				"reference_type": reference_type,
				"reference_display_field": reference_display_field,
			}
		)
		return self

	def add_extension(
		self,
		path,
		source_key,
		url,
		value_type,
		mapping_type,
		field=None,
		fixed_value=None,
		transformer=None,
		is_modifier=False,
	):
		self.extensions.append(
			{
				"path": path,
				"source_key": source_key,
				"url": url,
				"value_type": value_type,
				"mapping_type": mapping_type,
				"field": field,
				"fixed_value": fixed_value,
				"transformer": transformer,
				"is_modifier": is_modifier,
			}
		)
		return self

	def add_slice(
		self,
		path,
		source_key,
		slice_name,
		slice_of,
		mapping_type,
		field=None,
		fixed_value=None,
		transformer=None,
		pattern_value=None,
	):
		self.slices.append(
			{
				"path": path,
				"source_key": source_key,
				"slice_name": slice_name,
				"slice_of": slice_of,
				"mapping_type": mapping_type,
				"field": field,
				"fixed_value": fixed_value,
				"transformer": transformer,
				"pattern_value": pattern_value,
			}
		)
		return self

	def build(self):
		metadata = CompilationMetadata("R4", None, self.resource_type)
		resource = CompiledResource(metadata)

		# Add sources
		for src in self.sources:
			source = CompiledSource(src["key"], src["entity"], src["entity_type"])
			source.is_primary = src["is_primary"]
			source.link_field = src["link_field"]
			resource.add_source(source)

		# Add elements
		for elem in self.elements:
			element = CompiledElement(elem["path"], elem["source_key"])
			element.mapping_type = elem["mapping_type"]
			element.field = elem["field"]
			element.fixed_value = elem["fixed_value"]
			element.expression = elem["expression"]
			element.transformer = elem["transformer"]
			element.is_array = elem["is_array"]
			element.reference_type = elem["reference_type"]
			element.reference_display_field = elem["reference_display_field"]
			element.parent_path = self._get_parent_path(elem["path"])
			resource.add_element(element)

		# Add extensions
		for ext in self.extensions:
			element = CompiledElement(ext["path"], ext["source_key"])
			element.mapping_type = ext["mapping_type"]
			element.field = ext["field"]
			element.fixed_value = ext["fixed_value"]
			element.transformer = ext["transformer"]
			element.extension_url = ext["url"]
			element.extension_value_type = ext["value_type"]
			element.is_modifier_extension = ext["is_modifier"]
			element.is_array = True
			element.parent_path = self._get_parent_path(ext["path"])
			resource.add_element(element)

		# Add slices
		for slc in self.slices:
			element = CompiledElement(slc["path"], slc["source_key"])
			element.mapping_type = slc["mapping_type"]
			element.field = slc["field"]
			element.fixed_value = slc["fixed_value"]
			element.transformer = slc["transformer"]
			element.slice_name = slc["slice_name"]
			element.slice_of = slc["slice_of"]
			element.pattern_value = slc["pattern_value"]
			element.parent_path = self._get_parent_path(slc["path"])
			resource.add_element(element)

		# Build resource tree
		resource.resource_tree = self._build_tree(resource)

		return resource

	def _get_parent_path(self, path):
		if ":" in path:
			path = path.split(":")[0]
		parts = path.rsplit(".", 1)
		return parts[0] if len(parts) > 1 else self.resource_type

	def _build_tree(self, resource):
		root = ResourceTreeNode(self.resource_type)

		for element in resource.elements:
			if element.is_extension():
				continue

			path = element.path
			if ":" in path:
				path = path.split(":")[0]

			parts = path.split(".")
			if parts[0] == self.resource_type:
				parts = parts[1:]

			current = root
			for i, part in enumerate(parts):
				child = current.find_child(part)
				if child is None:
					child = ResourceTreeNode(part)
					is_last = i == len(parts) - 1
					child.is_array = element.is_array if is_last else False
					child.is_primitive = element.transformer is not None if is_last else False
					current.add_child(child)
				current = child

		return root


# =============================================================================
# FHIRRuntime Tests
# =============================================================================


class TestFHIRRuntimeDirect(IntegrationTestCase):
	"""Test runtime by directly providing sources_data"""

	def _generate(self, compiled, sources_data):
		runtime = FHIRRuntime(None)
		resolved_values = runtime._resolve_values(compiled, sources_data)
		extensions = runtime._resolve_extensions(compiled, sources_data)
		slices = runtime._resolve_slices(compiled, sources_data)
		result = runtime._build_resource(compiled, resolved_values, extensions, slices)
		result = runtime._prune(result)
		return result

	def test_generate_simple_resource(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_element("Patient.id", "primary", "field", field="name", transformer="string")
			.build()
		)

		result = self._generate(compiled, {"primary": {"name": "PAT-001"}})

		self.assertEqual(result["resourceType"], "Patient")
		self.assertEqual(result["id"], "PAT-001")

	def test_generate_with_date_field(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_element("Patient.birthDate", "primary", "field", field="dob", transformer="date")
			.build()
		)

		result = self._generate(compiled, {"primary": {"dob": "1990-05-15"}})

		self.assertEqual(result["birthDate"], "1990-05-15")

	def test_generate_with_fixed_value(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_element("Patient.active", "primary", "fixed", fixed_value="true", transformer="boolean")
			.build()
		)

		result = self._generate(compiled, {"primary": {}})

		self.assertTrue(result["active"])

	def test_generate_with_linked_source(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_source("gender", "Gender", entity_type="direct_link", link_field="sex")
			.add_element("Patient.gender", "gender", "field", field="gender", transformer="code")
			.build()
		)

		result = self._generate(compiled, {"primary": {"sex": "Male"}, "gender": {"gender": "Male"}})

		self.assertEqual(result["gender"], "Male")

	def test_generate_prunes_empty_values(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_element("Patient.id", "primary", "field", field="name", transformer="string")
			.add_element("Patient.language", "primary", "field", field="language", transformer="code")
			.build()
		)

		result = self._generate(compiled, {"primary": {"name": "PAT-001", "language": None}})

		self.assertIn("id", result)
		self.assertNotIn("language", result)

	def test_generate_with_reference(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_element(
				"Patient.managingOrganization",
				"primary",
				"field",
				field="organization",
				reference_type="Organization",
				reference_display_field="organization_name",
			)
			.build()
		)

		# Mark as non-primitive for reference
		ref_node = compiled.resource_tree.find_child("managingOrganization")
		if ref_node:
			ref_node.is_primitive = False

		result = self._generate(
			compiled, {"primary": {"organization": "ORG-001", "organization_name": "City Hospital"}}
		)

		self.assertIn("managingOrganization", result)
		self.assertEqual(result["managingOrganization"]["reference"], "Organization/ORG-001")
		self.assertEqual(result["managingOrganization"]["display"], "City Hospital")

	def test_generate_multiple_elements(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_element("Patient.id", "primary", "field", field="name", transformer="string")
			.add_element("Patient.birthDate", "primary", "field", field="dob", transformer="date")
			.add_element("Patient.active", "primary", "fixed", fixed_value="true", transformer="boolean")
			.build()
		)

		result = self._generate(compiled, {"primary": {"name": "PAT-001", "dob": "1985-03-20"}})

		self.assertEqual(result["id"], "PAT-001")
		self.assertEqual(result["birthDate"], "1985-03-20")
		self.assertTrue(result["active"])


class TestFHIRRuntimeExtensions(IntegrationTestCase):
	def _generate(self, compiled, sources_data):
		runtime = FHIRRuntime(None)
		resolved_values = runtime._resolve_values(compiled, sources_data)
		extensions = runtime._resolve_extensions(compiled, sources_data)
		slices = runtime._resolve_slices(compiled, sources_data)
		result = runtime._build_resource(compiled, resolved_values, extensions, slices)
		result = runtime._prune(result)
		return result

	def test_generate_with_fixed_extension(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_extension(
				"Patient.extension",
				"primary",
				url="http://example.org/test-ext",
				value_type="valueString",
				mapping_type="fixed",
				fixed_value='"test value"',
				transformer="string",
			)
			.build()
		)

		result = self._generate(compiled, {"primary": {}})

		self.assertIn("extension", result)
		self.assertEqual(len(result["extension"]), 1)
		self.assertEqual(result["extension"][0]["url"], "http://example.org/test-ext")
		self.assertEqual(result["extension"][0]["valueString"], "test value")

	def test_generate_with_field_extension(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_extension(
				"Patient.extension",
				"primary",
				url="http://example.org/religion",
				value_type="valueString",
				mapping_type="field",
				field="religion",
				transformer="string",
			)
			.build()
		)

		result = self._generate(compiled, {"primary": {"religion": "Hindu"}})

		self.assertIn("extension", result)
		self.assertEqual(result["extension"][0]["valueString"], "Hindu")

	def test_generate_multiple_extensions(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_extension(
				"Patient.extension",
				"primary",
				url="http://example.org/religion",
				value_type="valueString",
				mapping_type="field",
				field="religion",
				transformer="string",
			)
			.add_extension(
				"Patient.extension",
				"primary",
				url="http://example.org/nationality",
				value_type="valueString",
				mapping_type="field",
				field="nationality",
				transformer="string",
			)
			.build()
		)

		result = self._generate(compiled, {"primary": {"religion": "Hindu", "nationality": "Indian"}})

		self.assertIn("extension", result)
		self.assertEqual(len(result["extension"]), 2)


class TestFHIRRuntimeSlices(IntegrationTestCase):
	def _generate(self, compiled, sources_data):
		runtime = FHIRRuntime(None)
		resolved_values = runtime._resolve_values(compiled, sources_data)
		extensions = runtime._resolve_extensions(compiled, sources_data)
		slices = runtime._resolve_slices(compiled, sources_data)
		result = runtime._build_resource(compiled, resolved_values, extensions, slices)
		result = runtime._prune(result)
		return result

	def test_generate_with_slice(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_slice(
				"Patient.identifier:uid",
				"primary",
				slice_name="uid",
				slice_of="Patient.identifier",
				mapping_type="field",
				field="uid",
				transformer="string",
				pattern_value={"system": "https://uidai.gov.in/aadhaar"},
			)
			.build()
		)

		result = self._generate(compiled, {"primary": {"uid": "123456789012"}})

		self.assertIn("identifier", result)
		self.assertEqual(len(result["identifier"]), 1)
		self.assertEqual(result["identifier"][0]["system"], "https://uidai.gov.in/aadhaar")
		self.assertEqual(result["identifier"][0]["value"], "123456789012")

	def test_generate_with_multiple_slices(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_slice(
				"Patient.identifier:aadhaar",
				"primary",
				slice_name="aadhaar",
				slice_of="Patient.identifier",
				mapping_type="field",
				field="aadhaar",
				transformer="string",
				pattern_value={"system": "https://uidai.gov.in/aadhaar"},
			)
			.add_slice(
				"Patient.identifier:pan",
				"primary",
				slice_name="pan",
				slice_of="Patient.identifier",
				mapping_type="field",
				field="pan",
				transformer="string",
				pattern_value={"system": "https://incometax.gov.in/pan"},
			)
			.build()
		)

		result = self._generate(compiled, {"primary": {"aadhaar": "123456789012", "pan": "ABCDE1234F"}})

		self.assertIn("identifier", result)
		self.assertEqual(len(result["identifier"]), 2)

		systems = [ident["system"] for ident in result["identifier"]]
		self.assertIn("https://uidai.gov.in/aadhaar", systems)
		self.assertIn("https://incometax.gov.in/pan", systems)

	def test_slice_with_complex_pattern(self):
		compiled = (
			CompiledResourceBuilder("Patient")
			.add_source("primary", "Patient", is_primary=True)
			.add_slice(
				"Patient.identifier:aadhaar",
				"primary",
				slice_name="aadhaar",
				slice_of="Patient.identifier",
				mapping_type="field",
				field="uid",
				transformer="string",
				pattern_value={
					"system": "https://uidai.gov.in/aadhaar",
					"type": {"coding": [{"code": "NI", "display": "National Identifier"}]},
				},
			)
			.build()
		)

		result = self._generate(compiled, {"primary": {"uid": "999888777666"}})

		self.assertIn("identifier", result)
		self.assertEqual(result["identifier"][0]["value"], "999888777666")
		self.assertEqual(result["identifier"][0]["system"], "https://uidai.gov.in/aadhaar")
		self.assertEqual(result["identifier"][0]["type"]["coding"][0]["code"], "NI")


# =============================================================================
# End-to-End Tests with Compiler
# =============================================================================


class TestFHIREndToEnd(IntegrationTestCase):
	"""End-to-end tests: compile resource maps, then generate"""

	def setUp(self):
		self.created_resource_maps = []
		self.created_structure_definitions = []

	def tearDown(self):
		self._cleanup()

	def _cleanup(self):
		for name in self.created_resource_maps:
			if frappe.db.exists("FHIR Resource Map", name):
				frappe.delete_doc("FHIR Resource Map", name, force=True)

		for name in self.created_structure_definitions:
			if frappe.db.exists("FHIR Structure Definition", name):
				frappe.delete_doc("FHIR Structure Definition", name, force=True)

		frappe.db.commit()

	def _create_resource_map(self, custom_elements):
		import uuid

		suffix = uuid.uuid4().hex[:8]
		sd_fhir_sd = f"E2ETest{suffix}"

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
		self.created_structure_definitions.append(sd.name)

		doc = frappe.get_doc(
			{
				"doctype": "FHIR Resource Map",
				"resource_type": "Patient",
				"base_structure_definition": sd.name,
				"custom_elements": json.dumps(custom_elements),
			}
		)
		doc.insert(ignore_permissions=True)
		self.created_resource_maps.append(doc.name)
		frappe.db.commit()

		return doc

	def _generate(self, compiled, sources_data):
		runtime = FHIRRuntime(None)
		resolved_values = runtime._resolve_values(compiled, sources_data)
		extensions = runtime._resolve_extensions(compiled, sources_data)
		slices = runtime._resolve_slices(compiled, sources_data)
		result = runtime._build_resource(compiled, resolved_values, extensions, slices)
		result = runtime._prune(result)
		return result

	def _fix_compiled_resource_type(self, compiled):
		"""Fix the resource_type that gets set from structure definition name"""
		compiled.metadata.resource_type = "Patient"
		compiled.resource_tree.name = "Patient"

		# Fix element parent_paths if needed
		for element in compiled.elements:
			if element.parent_path and not element.parent_path.startswith("Patient"):
				parts = element.parent_path.split(".", 1)
				if len(parts) > 1:
					element.parent_path = f"Patient.{parts[1]}"
				else:
					element.parent_path = "Patient"

		# Rebuild tree with correct root name
		new_tree = ResourceTreeNode("Patient")
		for element in compiled.elements:
			if element.is_extension():
				continue
			path = element.path
			if ":" in path:
				path = path.split(":")[0]
			parts = path.split(".")
			if parts[0] != "Patient":
				continue
			parts = parts[1:]
			current = new_tree
			for i, part in enumerate(parts):
				child = current.find_child(part)
				if child is None:
					child = ResourceTreeNode(part)
					is_last = i == len(parts) - 1
					child.is_array = element.is_array if is_last else False
					child.is_primitive = element.transformer is not None if is_last else False
					current.add_child(child)
				current = child

		compiled.resource_tree = new_tree
		return compiled

	def test_compile_and_generate_simple(self):
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
		compiled = compiler.compile()
		compiled = self._fix_compiled_resource_type(compiled)

		result = self._generate(compiled, {"primary": {"name": "PAT-001", "dob": "1985-03-20"}})

		self.assertEqual(result["resourceType"], "Patient")
		self.assertEqual(result["id"], "PAT-001")
		self.assertEqual(result["birthDate"], "1985-03-20")
		self.assertTrue(result["active"])

	def test_compile_store_restore_generate(self):
		"""Test full workflow: compile, serialize, deserialize, generate"""
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
			],
		}

		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)
		compiled = compiler.compile()
		compiled = self._fix_compiled_resource_type(compiled)

		# Serialize
		compiled_json = json.dumps(compiled.to_dict())

		# Deserialize
		restored = CompiledResource.from_dict(json.loads(compiled_json))

		result = self._generate(restored, {"primary": {"name": "PAT-001"}})

		self.assertEqual(result["resourceType"], "Patient")
		self.assertEqual(result["id"], "PAT-001")

	def test_compile_and_generate_with_reference(self):
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
					"path": "Patient.managingOrganization",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "organization",
					"datatype": "Reference",
					"reference_type": "Organization",
					"reference_display_field": "organization_name",
				},
			],
		}

		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)
		compiled = compiler.compile()
		compiled = self._fix_compiled_resource_type(compiled)

		result = self._generate(
			compiled,
			{"primary": {"name": "PAT-001", "organization": "ORG-001", "organization_name": "City Hospital"}},
		)

		self.assertIn("managingOrganization", result)
		self.assertEqual(result["managingOrganization"]["reference"], "Organization/ORG-001")

	def test_compile_and_generate_with_extension(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"extensions": [
				{
					"path": "Patient",
					"url": "http://example.org/birthPlace",
					"value_type": "valueString",
					"source_key": "primary",
					"mapping_type": "fixed",
					"fixed_value": '"Kerala, India"',
				}
			],
		}

		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)
		compiled = compiler.compile()
		compiled = self._fix_compiled_resource_type(compiled)

		result = self._generate(compiled, {"primary": {}})

		self.assertIn("extension", result)
		self.assertEqual(result["extension"][0]["url"], "http://example.org/birthPlace")
		self.assertEqual(result["extension"][0]["valueString"], "Kerala, India")

	def test_compile_and_generate_with_slice(self):
		custom = {
			"sources": [{"key": "primary", "doctype": "Patient", "kind": "document", "is_primary": True}],
			"elements": [],
			"slices": [
				{
					"path": "Patient.identifier",
					"slice_name": "aadhaar",
					"source_key": "primary",
					"mapping_type": "field",
					"field": "uid",
					"datatype": "string",
					"discriminator_value": {
						"system": "https://uidai.gov.in/aadhaar",
						"type": {"coding": [{"code": "NI", "display": "National Identifier"}]},
					},
				}
			],
		}

		resource_map = self._create_resource_map(custom)
		compiler = FHIRCompiler(resource_map)
		compiled = compiler.compile()
		compiled = self._fix_compiled_resource_type(compiled)

		result = self._generate(compiled, {"primary": {"uid": "999888777666"}})

		self.assertIn("identifier", result)
		self.assertEqual(result["identifier"][0]["value"], "999888777666")
		self.assertEqual(result["identifier"][0]["system"], "https://uidai.gov.in/aadhaar")
