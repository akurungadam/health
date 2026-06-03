# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import hashlib
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from healthcare.interoperability.doctype.fhir_resource_map.fhir_compiler import compile_fhir_resource_map
from healthcare.interoperability.doctype.fhir_resource_map.fhir_runtime import FHIRRuntime
from healthcare.interoperability.doctype.fhir_resource_map.fhir_sd_loader import (
	FHIRStructureDefinitionLoader,
)


class FHIRResourceMap(Document):
	def autoname(self):
		if self.base_structure_definition:
			self.name = f"{self.resource_type}-{self.base_structure_definition}"
		else:
			self.name = f"{self.resource_type}"

	def validate(self):
		# Compilation is warn-only: it never blocks saving.
		self.compile_mapping()

	def compile_mapping(self):
		try:
			compiled, warnings = compile_fhir_resource_map(self)
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "FHIR Resource Map compilation failed")
			self.status = "Errors"
			frappe.msgprint(
				_("Could not compile mapping: {0}").format(str(e)),
				title=_("Compilation Error"),
				indicator="red",
			)
			return

		compiled_json = json.dumps(compiled, indent=2, sort_keys=True)
		self.compiled_mapping = compiled_json
		self.compiled_hash = hashlib.sha256(compiled_json.encode("utf-8")).hexdigest()
		self.compiled_at = now_datetime()
		self.status = "Warnings" if warnings else "No Errors"

		if warnings:
			frappe.msgprint(
				"<br>".join(frappe.utils.escape_html(w) for w in warnings),
				title=_("Mapping Warnings"),
				indicator="orange",
			)

	def get_elements_from_structure_definitions(self):
		"""Merged SD element rows (base + profiles, most-restrictive-wins)."""
		return FHIRStructureDefinitionLoader(resource_map=self).load_merged_elements()


@frappe.whitelist()
def get_elements_from_structure_definitions(fhir_resource_map):
	fhir_resource_map = (fhir_resource_map or "").strip()
	if not fhir_resource_map:
		frappe.throw(_("fhir_resource_map is required"))

	doc = frappe.get_doc("FHIR Resource Map", fhir_resource_map)
	return doc.get_elements_from_structure_definitions()


@frappe.whitelist()
def generate_fhir_resource(resource_map_name, docname):
	resource_map = frappe.get_doc("FHIR Resource Map", resource_map_name)

	if not resource_map.compiled_mapping:
		frappe.throw(
			_("Resource map '{0}' has no compiled mapping. Save it first.").format(resource_map_name)
		)

	compiled = json.loads(resource_map.compiled_mapping)
	return FHIRRuntime(compiled).generate(docname)
