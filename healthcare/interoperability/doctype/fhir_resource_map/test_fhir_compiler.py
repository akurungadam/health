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
		self.assertTrue(any("Invalid JSON" in w for w in warnings))
		self.assertEqual(compiled["meta"]["resource_type"], "Patient")


if __name__ == "__main__":
	unittest.main()
