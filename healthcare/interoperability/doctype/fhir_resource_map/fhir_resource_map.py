# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import hashlib
import json

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from healthcare.interoperability.doctype.fhir_resource_map.fhir_compiler import (
	CompiledResource,
	FHIRCompiler,
)
from healthcare.interoperability.doctype.fhir_resource_map.fhir_runtime import (
	FHIRRuntime,
	FrappeSourceResolver,
)
from healthcare.interoperability.doctype.fhir_resource_map.fhir_sd_loader import FHIRStructureDefinitionLoader
from healthcare.interoperability.doctype.fhir_resource_map.validator import FHIRMappingValidator
from healthcare.interoperability.fhir_engine.fhir_compiler import compile_fhir_resource_map


class FHIRResourceMap(Document):
	def autoname(self):
		if self.base_structure_definition:
			self.name = f"{self.resource_type}-{self.base_structure_definition}"
		else:
			self.name = f"{self.resource_type}"

	def validate(self):
		self.compile_mapping()
		# pass

	def compile_mapping(self):
		compiled_json, compiled_hash = compile_fhir_resource_map(self)

		self.compiled_mapping = compiled_json
		self.compiled_hash = compiled_hash
		self.compiled_at = now_datetime()

	@frappe.whitelist()
	def load_structure_definition_elements(self):
		"""
		Return merged SD element rows (base + profiles most-restrictive-wins).
		Same merge used by compiler (repeating_containers).
		"""
		return FHIRStructureDefinitionLoader(resource_map=self).load_merged_elements()


@frappe.whitelist()
def load_structure_definition_elements(fhir_resource_map):
	fhir_resource_map = (fhir_resource_map or "").strip()
	if not fhir_resource_map:
		frappe.throw("fhir_resource_map is required")

	doc = frappe.get_doc("FHIR Resource Map", fhir_resource_map)
	return doc.load_structure_definition_elements()


from healthcare.interoperability.fhir_engine.fhir_generator import FHIRRuntimeGenerator


@frappe.whitelist()
def generate_fhir_resource(resource_map_name, docname):
	resource_map = frappe.get_doc("FHIR Resource Map", resource_map_name)

	compiled = json.loads(resource_map.compiled_mapping)

	generator = FHIRRuntimeGenerator(compiled, docname)

	return generator.generate()
