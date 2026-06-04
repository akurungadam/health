# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and Contributors
# See license.txt

"""
DB-free unit tests for FHIRCompiler.

The compiler is fed a lightweight fake resource-map object (SimpleNamespace)
instead of a real Document, so these tests need no fixtures or DB inserts.
``frappe.db.exists`` (used only by warn-only source validation) is patched so
results don't depend on which doctypes are installed.
"""

import json
import unittest
from types import SimpleNamespace
from unittest import mock

from healthcare.interoperability.doctype.fhir_resource_map.fhir_compiler import FHIRCompiler


def element_row(fhir_path, value_pointer=None, datatype="", max="1", min=0, **kwargs):
	return SimpleNamespace(
		fhir_path=fhir_path,
		value_pointer=json.dumps(value_pointer) if value_pointer is not None else None,
		datatype=datatype,
		max=max,
		min=min,
		mapping_type=kwargs.get("mapping_type"),
		source_name=kwargs.get("source_name"),
		frappe_field=kwargs.get("frappe_field"),
		fixed_value=kwargs.get("fixed_value"),
		expression=kwargs.get("expression"),
		default_value=kwargs.get("default_value"),
	)


def source_row(source_key, source_doctype, kind="document", link_fieldname=None, config=None):
	return SimpleNamespace(
		source_key=source_key,
		source_doctype=source_doctype,
		kind=kind,
		link_fieldname=link_fieldname,
		config=config,
	)


def resource_map(**kwargs):
	return SimpleNamespace(
		resource_type=kwargs.get("resource_type", "Patient"),
		primary_doctype=kwargs.get("primary_doctype", "Patient"),
		base_structure_definition=kwargs.get("base_structure_definition"),  # None -> no DB / no SD index
		custom_elements=kwargs.get("custom_elements"),
		profiles=kwargs.get("profiles", []),
		sources=kwargs.get("sources", []),
		element_maps=kwargs.get("element_maps", []),
	)


class TestFHIRCompiler(unittest.TestCase):
	def compile(self, rm):
		with mock.patch("frappe.db.exists", return_value=True):
			return FHIRCompiler(rm).compile()

	def test_meta_and_primary_source(self):
		rm = resource_map()
		compiled, _ = self.compile(rm)

		self.assertEqual(compiled["meta"]["resource_type"], "Patient")
		self.assertEqual(compiled["meta"]["primary_doctype"], "Patient")
		self.assertEqual(compiled["sources"]["primary"]["doctype"], "Patient")
		self.assertTrue(compiled["sources"]["primary"]["is_primary"])
		self.assertEqual(compiled["sources"]["primary"]["kind"], "document")

	def test_field_pointer_and_linked_source(self):
		rm = resource_map(
			sources=[source_row("gender", "Gender", kind="direct_link", link_fieldname="sex")],
			element_maps=[
				element_row(
					"Patient.gender",
					{"kind": "field", "source_key": "gender", "fieldname": "name"},
					datatype="code",
					min=1,
				),
			],
		)
		compiled, _ = self.compile(rm)

		gender_source = compiled["sources"]["gender"]
		self.assertEqual(gender_source["kind"], "direct_link")
		self.assertEqual(gender_source["link_fieldname"], "sex")
		self.assertEqual(gender_source["parent"], "primary")

		el = compiled["elements"]["Patient.gender"]
		self.assertEqual(el["source"], "gender")
		self.assertEqual(el["value_spec"], {"kind": "field", "fieldname": "name"})
		self.assertFalse(el["is_array"])
		self.assertTrue(el["is_required"])

	def test_field_pointer_carries_value_map(self):
		rm = resource_map(
			element_maps=[
				element_row(
					"Patient.gender",
					{
						"kind": "field",
						"source_key": "primary",
						"fieldname": "sex",
						"map": {"Male": "male", "Female": "female", "*": "unknown"},
					},
					datatype="code",
				),
			]
		)
		compiled, _ = self.compile(rm)
		self.assertEqual(
			compiled["elements"]["Patient.gender"]["value_spec"],
			{
				"kind": "field",
				"fieldname": "sex",
				"map": {"Male": "male", "Female": "female", "*": "unknown"},
			},
		)

	def test_reference_pointer_from_ui_row(self):
		# a UI-authored reference: datatype Reference + pointer carrying reference_type/display_field
		rm = resource_map(
			element_maps=[
				element_row(
					"Patient.managingOrganization",
					{
						"kind": "field",
						"source_key": "primary",
						"fieldname": "org",
						"reference_type": "Organization",
						"display_field": "org_name",
					},
					datatype="Reference",
				),
			]
		)
		compiled, _ = self.compile(rm)
		element = compiled["elements"]["Patient.managingOrganization"]
		self.assertEqual(element["datatype"], "Reference")
		self.assertEqual(element["value_spec"], {"kind": "field", "fieldname": "org"})
		self.assertEqual(element["reference"], {"resource_type": "Organization", "display_field": "org_name"})

	def test_fixed_pointer(self):
		rm = resource_map(
			element_maps=[
				element_row("Patient.active", {"kind": "fixed", "value": True}, datatype="boolean"),
			]
		)
		compiled, _ = self.compile(rm)
		self.assertEqual(
			compiled["elements"]["Patient.active"]["value_spec"], {"kind": "fixed", "value": True}
		)

	def test_is_array_from_max_star(self):
		rm = resource_map(
			element_maps=[
				element_row(
					"Patient.name.given",
					{"kind": "field", "source_key": "primary", "fieldname": "first_name"},
					datatype="string",
					max="*",
				),
			]
		)
		compiled, _ = self.compile(rm)
		self.assertTrue(compiled["elements"]["Patient.name.given"]["is_array"])

	def test_column_fallback_when_no_pointer(self):
		# no value_pointer -> compiler falls back to legacy columns and cleans the "field|Label" form
		rm = resource_map(
			element_maps=[
				element_row(
					"Patient.birthDate",
					value_pointer=None,
					datatype="date",
					mapping_type="Frappe Field",
					frappe_field="dob|DOB (dob)",
					source_name="primary",
				),
			]
		)
		compiled, _ = self.compile(rm)
		el = compiled["elements"]["Patient.birthDate"]
		self.assertEqual(el["value_spec"], {"kind": "field", "fieldname": "dob"})
		self.assertEqual(el["source"], "primary")

	def test_unmapped_row_is_skipped(self):
		rm = resource_map(element_maps=[element_row("Patient.gender", value_pointer=None)])
		compiled, _ = self.compile(rm)
		self.assertNotIn("Patient.gender", compiled["elements"])

	def test_custom_elements_override_and_add(self):
		rm = resource_map(
			element_maps=[
				element_row(
					"Patient.gender",
					{"kind": "field", "source_key": "primary", "fieldname": "sex"},
					datatype="code",
				),
			],
			custom_elements=json.dumps(
				{
					"sources": [{"key": "org", "doctype": "Organization", "kind": "document"}],
					"elements": [
						# overrides the UI mapping for Patient.gender
						{
							"path": "Patient.gender",
							"datatype": "code",
							"value_spec": {"kind": "fixed", "value": "other"},
						},
						# adds a brand new element
						{
							"path": "Patient.managingOrganization",
							"source": "org",
							"datatype": "Reference",
							"value_spec": {"kind": "field", "fieldname": "name"},
						},
					],
				}
			),
		)
		compiled, _ = self.compile(rm)

		self.assertIn("org", compiled["sources"])
		self.assertEqual(
			compiled["elements"]["Patient.gender"]["value_spec"], {"kind": "fixed", "value": "other"}
		)
		self.assertEqual(compiled["elements"]["Patient.managingOrganization"]["source"], "org")

	def test_warning_on_unknown_source(self):
		rm = resource_map(
			element_maps=[
				element_row(
					"Patient.gender",
					{"kind": "field", "source_key": "ghost", "fieldname": "x"},
					datatype="code",
				),
			]
		)
		_, warnings = self.compile(rm)
		self.assertTrue(any("unknown source" in w and "ghost" in w for w in warnings))

	def test_invalid_custom_json_warns_not_raises(self):
		rm = resource_map(custom_elements="{not valid json")
		compiled, warnings = self.compile(rm)
		self.assertTrue(any("not valid JSON" in w for w in warnings))
		self.assertEqual(compiled["meta"]["resource_type"], "Patient")

	def test_collection_source_backbone_computed(self):
		rm = resource_map(
			sources=[source_row("phones", "Phone", kind="child_table", link_fieldname="phones")],
			element_maps=[
				element_row(
					"Patient.telecom.value",
					{"kind": "field", "source_key": "phones", "fieldname": "number"},
					datatype="string",
				),
			],
		)
		compiled, _ = self.compile(rm)

		phones = compiled["sources"]["phones"]
		self.assertTrue(phones["is_collection"])
		self.assertEqual(phones["fhir_path"], "Patient.telecom")
		self.assertEqual(compiled["elements"]["Patient.telecom.value"]["source"], "phones")

	def test_explicit_source_fhir_path_is_honoured(self):
		rm = resource_map(
			custom_elements=json.dumps(
				{
					"sources": [
						{
							"key": "encounters",
							"doctype": "Patient Encounter",
							"kind": "reverse_link",
							"link_fieldname": "patient",
							"fhir_path": "Patient.generalPractitioner",
						}
					],
					"elements": [
						{
							"path": "Patient.generalPractitioner",
							"source": "encounters",
							"datatype": "Reference",
							"reference": {"resource_type": "Practitioner"},
							"value_spec": {"kind": "field", "fieldname": "practitioner"},
						}
					],
				}
			),
		)
		compiled, _ = self.compile(rm)
		self.assertEqual(compiled["sources"]["encounters"]["fhir_path"], "Patient.generalPractitioner")

	def test_dynamic_link_source_is_collection_with_backbone(self):
		rm = resource_map(
			sources=[source_row("addresses", "Address", kind="dynamic_link")],
			element_maps=[
				element_row(
					"Patient.address.city",
					{"kind": "field", "source_key": "addresses", "fieldname": "city"},
					datatype="string",
				),
			],
		)
		compiled, _ = self.compile(rm)

		addresses = compiled["sources"]["addresses"]
		self.assertEqual(addresses["kind"], "dynamic_link")
		self.assertTrue(addresses["is_collection"])
		self.assertEqual(addresses["fhir_path"], "Patient.address")

	def test_linked_source_is_not_collection(self):
		rm = resource_map(
			sources=[source_row("gender", "Gender", kind="direct_link", link_fieldname="sex")],
		)
		compiled, _ = self.compile(rm)
		self.assertFalse(compiled["sources"]["gender"]["is_collection"])

	def test_reference_config_from_custom(self):
		rm = resource_map(
			custom_elements=json.dumps(
				{
					"elements": [
						{
							"path": "Patient.managingOrganization",
							"datatype": "Reference",
							"reference": {"resource_type": "Organization", "display_field": "org_name"},
							"value_spec": {"kind": "field", "fieldname": "org"},
						}
					]
				}
			),
		)
		compiled, _ = self.compile(rm)
		element = compiled["elements"]["Patient.managingOrganization"]
		self.assertEqual(element["datatype"], "Reference")
		self.assertEqual(element["reference"], {"resource_type": "Organization", "display_field": "org_name"})

	def test_extensions_compiled_from_custom(self):
		rm = resource_map(
			custom_elements=json.dumps(
				{
					"extensions": [
						{
							"url": "http://example.org/fhir/StructureDefinition/note",
							"value_type": "valueString",
							"value_spec": {"kind": "field", "fieldname": "note"},
						}
					]
				}
			),
		)
		compiled, _ = self.compile(rm)
		self.assertEqual(len(compiled["extensions"]), 1)
		extension = compiled["extensions"][0]
		self.assertEqual(extension["host"], "Patient")
		self.assertEqual(extension["source"], "primary")
		self.assertEqual(extension["value_type"], "valueString")

	def test_slices_compiled_from_custom(self):
		rm = resource_map(
			custom_elements=json.dumps(
				{
					"slices": [
						{
							"path": "Patient.identifier",
							"slice_name": "MRN",
							"pattern": {"system": "http://hospital.org/mrn"},
							"elements": [
								{
									"path": "value",
									"datatype": "string",
									"value_spec": {"kind": "field", "fieldname": "mrn"},
								}
							],
						}
					]
				}
			),
		)
		compiled, _ = self.compile(rm)

		self.assertEqual(len(compiled["slices"]), 1)
		compiled_slice = compiled["slices"][0]
		self.assertEqual(compiled_slice["path"], "Patient.identifier")
		self.assertEqual(compiled_slice["slice_name"], "MRN")
		self.assertEqual(compiled_slice["pattern"], {"system": "http://hospital.org/mrn"})
		self.assertEqual(compiled_slice["elements"][0]["path"], "value")

	def test_array_paths_explicit_and_excludes_collection(self):
		rm = resource_map(
			sources=[source_row("phones", "Phone", kind="child_table", link_fieldname="phones")],
			element_maps=[
				element_row(
					"Patient.telecom.value",
					{"kind": "field", "source_key": "phones", "fieldname": "number"},
					datatype="string",
				),
			],
			custom_elements=json.dumps({"arrays": ["Patient.name"]}),
		)
		compiled, _ = self.compile(rm)

		self.assertIn("Patient.name", compiled["array_paths"])
		# the collection backbone already produces a list, so it must not be wrapped again
		self.assertNotIn("Patient.telecom", compiled["array_paths"])

	def test_choice_expansion_helper(self):
		from healthcare.interoperability.doctype.fhir_resource_map.fhir_validator import MappingValidator

		validator = MappingValidator({"Patient.deceased[x]": {"min": 0, "max": "1"}})
		self.assertTrue(validator._is_choice_expansion("Patient.deceasedBoolean"))
		self.assertFalse(validator._is_choice_expansion("Patient.gender"))

	def test_required_satisfied_by_child_or_slice(self):
		from healthcare.interoperability.doctype.fhir_resource_map.fhir_validator import MappingValidator

		sd_index = {"Patient.identifier": {"min": 1, "max": "*"}}
		validator = MappingValidator(sd_index)

		# satisfied by a slice under the required path
		by_slice = {
			"elements": {},
			"sources": {},
			"slices": [{"path": "Patient.identifier", "elements": [{"path": "value"}]}],
		}
		self.assertEqual([w for w in validator.validate(by_slice) if "Required" in w], [])

		# satisfied by a mapped child element
		by_child = {
			"elements": {"Patient.identifier.value": {"source": "primary"}},
			"sources": {"primary": {"doctype": "Patient"}},
			"slices": [],
		}
		with mock.patch("frappe.db.exists", return_value=True):
			required_warnings = [w for w in validator.validate(by_child) if "Required" in w]
		self.assertEqual(required_warnings, [])

	def test_required_satisfied_by_slice_pattern(self):
		from healthcare.interoperability.doctype.fhir_resource_map.fhir_validator import MappingValidator

		# the profile requires the coding leaves; the slice pattern supplies them
		sd_index = {
			"Patient.identifier": {"min": 1, "max": "*"},
			"Patient.identifier.type.coding.system": {"min": 1, "max": "1"},
			"Patient.identifier.type.coding.code": {"min": 1, "max": "1"},
		}
		compiled = {
			"elements": {},
			"sources": {},
			"slices": [
				{
					"path": "Patient.identifier",
					"pattern": {"type": {"coding": [{"system": "s", "code": "MR"}]}},
					"elements": [{"path": "value", "value_spec": {"kind": "field", "fieldname": "mrn"}}],
				}
			],
		}
		required = [w for w in MappingValidator(sd_index).validate(compiled) if "Required" in w]
		self.assertEqual(required, [])

	def test_complex_datatype_internals_not_flagged_unknown(self):
		from healthcare.interoperability.doctype.fhir_resource_map.fhir_validator import MappingValidator

		sd_index = {
			"Patient.maritalStatus": {"min": 0, "max": "1", "datatype": "CodeableConcept"},
			"Patient.gender": {"min": 0, "max": "1", "datatype": "code"},
		}
		compiled = {
			"elements": {
				"Patient.maritalStatus.coding.code": {"source": "primary"},  # into a complex type -> OK
				"Patient.bogus": {"source": "primary"},  # truly unknown -> warns
			},
			"sources": {"primary": {"doctype": "Patient"}},
			"slices": [],
		}
		with mock.patch("frappe.db.exists", return_value=True):
			warnings = MappingValidator(sd_index).validate(compiled)

		unknown = [w for w in warnings if "not in the merged StructureDefinition" in w]
		self.assertTrue(any("Patient.bogus" in w for w in unknown))
		self.assertFalse(any("maritalStatus" in w for w in unknown))

	def test_complex_datatype_mapped_as_scalar_warns(self):
		from healthcare.interoperability.doctype.fhir_resource_map.fhir_validator import MappingValidator

		compiled = {
			"elements": {
				# CodeableConcept fed a bare field -> warns
				"Patient.maritalStatus": {
					"source": "primary",
					"datatype": "CodeableConcept",
					"value_spec": {"kind": "field", "fieldname": "marital_status"},
				},
				# same type authored as an object -> fine
				"Observation.code": {
					"source": "primary",
					"datatype": "CodeableConcept",
					"value_spec": {"kind": "json", "value": {"text": "BP"}},
				},
				# a Reference builds its own object -> fine
				"Patient.managingOrganization": {
					"source": "primary",
					"datatype": "Reference",
					"value_spec": {"kind": "field", "fieldname": "org"},
				},
				# a primitive sub-element -> fine
				"Patient.name.family": {
					"source": "primary",
					"datatype": "string",
					"value_spec": {"kind": "field", "fieldname": "last_name"},
				},
			},
			"sources": {"primary": {"doctype": "Patient"}},
			"slices": [],
		}
		with mock.patch("frappe.db.exists", return_value=True):
			warnings = MappingValidator({}).validate(compiled)

		scalar_warnings = [w for w in warnings if "complex datatype" in w]
		self.assertTrue(any("Patient.maritalStatus" in w for w in scalar_warnings))
		self.assertFalse(any("Observation.code" in w for w in scalar_warnings))
		self.assertFalse(any("managingOrganization" in w for w in scalar_warnings))
		self.assertFalse(any("Patient.name.family" in w for w in scalar_warnings))

	def test_complex_datatype_from_sd_index_when_element_datatype_blank(self):
		from healthcare.interoperability.doctype.fhir_resource_map.fhir_validator import MappingValidator

		# element carries no datatype; the SD index supplies it
		sd_index = {"Patient.maritalStatus": {"min": 0, "max": "1", "datatype": "CodeableConcept"}}
		compiled = {
			"elements": {
				"Patient.maritalStatus": {
					"source": "primary",
					"datatype": "",
					"value_spec": {"kind": "field", "fieldname": "marital_status"},
				}
			},
			"sources": {"primary": {"doctype": "Patient"}},
			"slices": [],
		}
		with mock.patch("frappe.db.exists", return_value=True):
			warnings = MappingValidator(sd_index).validate(compiled)
		self.assertTrue(any("complex datatype" in w and "maritalStatus" in w for w in warnings))

	def test_required_child_of_unmapped_optional_backbone_not_flagged(self):
		from healthcare.interoperability.doctype.fhir_resource_map.fhir_validator import MappingValidator

		# Patient.link is optional (min 0); its children are required only when link is present
		sd_index = {
			"Patient.link": {"min": 0, "max": "*"},
			"Patient.link.other": {"min": 1, "max": "1"},
			"Patient.link.type": {"min": 1, "max": "1"},
		}
		compiled = {"elements": {}, "sources": {}, "slices": []}
		required = [w for w in MappingValidator(sd_index).validate(compiled) if "Required" in w]
		self.assertEqual(required, [])


if __name__ == "__main__":
	unittest.main()
