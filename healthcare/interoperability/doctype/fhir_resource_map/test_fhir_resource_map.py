# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and Contributors
# See license.txt

import json

import frappe
from frappe.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestFHIRResourceMap(IntegrationTestCase):
	"""
	Integration tests for FHIRResourceMap.
	Use this class for testing interactions between multiple components.
	"""

	def setUp(self):
		self.fhir_resource_map_doctype = "FHIR Resource Map"

	def test_compile_includes_sources_and_mapped_only_elements(self):
		fhir_resource_map = self._new_fhir_resource_map_doc()

		# Primary doctype must exist and must have the link field below
		fhir_resource_map.primary_doctype = "Comment"

		# Additional source: direct_link from Comment.reference_doctype -> DocType
		fhir_resource_map.append(
			"sources",
			{
				"source_key": "refdt",
				"source_doctype": "DocType",
				"config": json.dumps(
					{
						"kind": "direct_link",
						"link_fieldname": "reference_doctype",
						"required": 1,
						"cache": 1,
					}
				),
			},
		)

		# Element maps:
		# 1) mapped
		fhir_resource_map.append(
			"element_maps",
			{
				"fhir_path": "meta.profile",
				"datatype": "canonical",
				"min": 0,
				"max": "*",
				"value_pointer": json.dumps(
					{
						"kind": "fixed",
						"value": ["https://example.org/fhir/StructureDefinition/TestProfile"],
					}
				),
			},
		)

		# 2) required but unmapped => must NOT appear in compiled["elements"]
		#    but MUST appear in compiled["missing_required"]
		fhir_resource_map.append(
			"element_maps",
			{
				"fhir_path": "identifier",
				"datatype": "Identifier",
				"min": 1,
				"max": "*",
				"value_pointer": "",
			},
		)

		fhir_resource_map.compile_map()

		compiled = self._read_compiled(fhir_resource_map)

		self.assertIn("sources", compiled)
		self.assertIn("primary", compiled["sources"])
		self.assertEqual(compiled["sources"]["primary"]["doctype"], "Comment")

		# direct_link source should be compiled
		self.assertIn("refdt", compiled["sources"])
		self.assertEqual(compiled["sources"]["refdt"]["kind"], "direct_link")
		self.assertEqual(compiled["sources"]["refdt"]["doctype"], "DocType")
		self.assertEqual(compiled["sources"]["refdt"]["link_fieldname"], "reference_doctype")

		# elements should contain ONLY mapped ones
		self.assertIn("elements", compiled)
		self.assertEqual(len(compiled["elements"]), 1)
		self.assertEqual(compiled["elements"][0]["fhir_path"], "meta.profile")
		self.assertEqual(compiled["elements"][0]["pointer"]["kind"], "fixed")

		# missing_required should contain identifier
		self.assertIn("missing_required", compiled)
		self.assertEqual(len(compiled["missing_required"]), 1)
		self.assertEqual(compiled["missing_required"][0]["fhir_path"], "identifier")

		# counts should exist if you added them
		if "counts" in compiled:
			self.assertEqual(compiled["counts"]["total_rows"], 2)
			self.assertEqual(compiled["counts"]["mapped"], 1)
			self.assertEqual(compiled["counts"]["missing_required"], 1)

	def test_compile_rejects_duplicate_source_keys(self):
		fhir_resource_map = self._new_fhir_resource_map_doc()
		fhir_resource_map.primary_doctype = "Comment"

		fhir_resource_map.append(
			"sources",
			{
				"source_key": "dup",
				"source_doctype": "DocType",
				"config": json.dumps({"kind": "direct_link", "link_fieldname": "reference_doctype"}),
			},
		)
		fhir_resource_map.append(
			"sources",
			{
				"source_key": "dup",
				"source_doctype": "DocType",
				"config": json.dumps({"kind": "direct_link", "link_fieldname": "reference_doctype"}),
			},
		)

		with self.assertRaises(Exception) as context:
			fhir_resource_map.compile_map()

		self.assertIn("Duplicate Source Key", str(context.exception))

	def test_compile_rejects_reserved_primary_source_key(self):
		fhir_resource_map = self._new_fhir_resource_map_doc()
		fhir_resource_map.primary_doctype = "Comment"

		fhir_resource_map.append(
			"sources",
			{
				"source_key": "primary",
				"source_doctype": "DocType",
				"config": json.dumps({"kind": "direct_link", "link_fieldname": "reference_doctype"}),
			},
		)

		with self.assertRaises(Exception) as context:
			fhir_resource_map.compile_map()

		self.assertIn("reserved", str(context.exception).lower())

	def test_compile_rejects_invalid_link_fieldname(self):
		fhir_resource_map = self._new_fhir_resource_map_doc()
		fhir_resource_map.primary_doctype = "Comment"

		# Comment does NOT have a Link field called "nope"
		fhir_resource_map.append(
			"sources",
			{
				"source_key": "badlink",
				"source_doctype": "DocType",
				"config": json.dumps({"kind": "direct_link", "link_fieldname": "nope"}),
			},
		)

		with self.assertRaises(Exception) as context:
			fhir_resource_map.compile_map()

		self.assertIn("not found", str(context.exception).lower())

	# -------------------------
	# Helpers
	# -------------------------

	def _new_fhir_resource_map_doc(self):
		"""
		Creates an UNSAVED doc with required fields filled as best-effort.
		This avoids tests failing due to extra reqd fields you may add later.
		"""
		doc = frappe.new_doc(self.fhir_resource_map_doctype)

		self._fill_required_fields(doc, overrides={"primary_doctype": "Comment"})

		# Make sure child tables exist
		if not getattr(doc, "sources", None):
			doc.set("sources", [])
		if not getattr(doc, "element_maps", None):
			doc.set("element_maps", [])

		return doc

	def _fill_required_fields(self, doc, overrides=None):
		overrides = overrides or {}
		meta = frappe.get_meta(doc.doctype)

		for field in meta.fields:
			if not getattr(field, "reqd", 0):
				continue
			fieldname = field.fieldname
			if not fieldname:
				continue
			if field.fieldtype in ("Section Break", "Column Break", "Tab Break", "HTML", "Button", "Fold"):
				continue
			if doc.get(fieldname):
				continue

			if fieldname in overrides:
				doc.set(fieldname, overrides[fieldname])
				continue

			value = self._default_value_for_field(field)
			if value is not None:
				doc.set(fieldname, value)

	def _default_value_for_field(self, field):
		fieldtype = field.fieldtype
		if fieldtype in ("Data", "Small Text", "Long Text", "Text", "Code"):
			return "Test"
		if fieldtype == "Int":
			return 1
		if fieldtype in ("Float", "Currency", "Percent"):
			return 1.0
		if fieldtype == "Check":
			return 0
		if fieldtype == "Date":
			return "2000-01-01"
		if fieldtype == "Datetime":
			return frappe.utils.now_datetime()
		if fieldtype == "Time":
			return "00:00:00"
		if fieldtype == "Select":
			options = (field.options or "").split("\n")
			options = [o.strip() for o in options if o.strip()]
			return options[0] if options else ""
		if fieldtype == "Link":
			target = (field.options or "").strip()
			if not target:
				return None
			existing = frappe.get_all(target, pluck="name", limit=1)
			return existing[0] if existing else None

		# For anything complex or table fields, don't guess.
		return None

	def _read_compiled(self, fhir_resource_map_doc):
		if not fhir_resource_map_doc.compiled_mapping:
			return {}
		return json.loads(fhir_resource_map_doc.compiled_mapping or "{}")
