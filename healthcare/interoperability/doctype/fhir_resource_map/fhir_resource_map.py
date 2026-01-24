# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import hashlib
import json

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from healthcare.interoperability.doctype.fhir_resource_map.compiler import FHIRMappingCompiler
from healthcare.interoperability.doctype.fhir_resource_map.generator import FHIRResourceGenerator
from healthcare.interoperability.doctype.fhir_resource_map.structure_def_loader import (
	FHIRStructureDefinitionLoader,
)
from healthcare.interoperability.doctype.fhir_resource_map.validator import FHIRMappingValidator
from healthcare.interoperability.doctype.fhir_resource_map.value_resolver import FHIRValueResolver


class FHIRResourceMap(Document):
	def validate(self):
		compiled = self.compile_mapping()

		compiled_json = json.dumps(
			compiled,
			sort_keys=True,
			separators=(",", ":"),
			ensure_ascii=False,
			indent=1,
		)

		self.compiled_mapping = compiled_json
		self.compiled_hash = hashlib.sha256(compiled_json.encode("utf-8")).hexdigest()
		self.compiled_at = now_datetime()

	@frappe.whitelist()
	def compile_mapping(self):
		return FHIRMappingCompiler(resource_map=self).compile()

	def _load_compiled(self):
		if self.compiled_mapping:
			if isinstance(self.compiled_mapping, str):
				return json.loads(self.compiled_mapping)
			return self.compiled_mapping
		return self.compile_mapping()

	@frappe.whitelist()
	def load_structure_definition_elements(self):
		"""
		Return merged SD element rows (base + profiles most-restrictive-wins).
		Same merge used by compiler (repeating_containers).
		"""
		return FHIRStructureDefinitionLoader(resource_map=self).load_merged_elements()


# =========================================================
# API
# =========================================================


@frappe.whitelist()
def validate_fhir_mapping(fhir_resource_map):
	fhir_resource_map = (fhir_resource_map or "").strip()
	if not fhir_resource_map:
		frappe.throw("fhir_resource_map is required")

	resource_map = frappe.get_doc("FHIR Resource Map", fhir_resource_map)

	compiled_map = resource_map.compiled_mapping
	if isinstance(compiled_map, str):
		compiled_map = frappe.parse_json(compiled_map)

	if not compiled_map:
		return {
			"is_valid": False,
			"errors": [
				{"type": "no_compiled_map", "message": "No compiled mapping found. Save the document first."}
			],
			"warnings": [],
			"error_count": 1,
			"warning_count": 0,
		}

	sd_elements = resource_map.load_structure_definition_elements()
	validator = FHIRMappingValidator(compiled_map, sd_elements)
	return validator.validate()


@frappe.whitelist()
def load_structure_definition_elements(fhir_resource_map):
	fhir_resource_map = (fhir_resource_map or "").strip()
	if not fhir_resource_map:
		frappe.throw("fhir_resource_map is required")

	doc = frappe.get_doc("FHIR Resource Map", fhir_resource_map)
	return doc.load_structure_definition_elements()


@frappe.whitelist()
def resolve_fhir_values(fhir_resource_map, primary_name):
	resource_map = frappe.get_doc("FHIR Resource Map", fhir_resource_map)

	compiled_map = resource_map.compiled_mapping
	if isinstance(compiled_map, str):
		compiled_map = frappe.parse_json(compiled_map)

	resolver = FHIRValueResolver(compiled_map, primary_name)
	return resolver.resolve()


@frappe.whitelist()
def build_fhir_resource(fhir_resource_map, primary_name):
	resource_map = frappe.get_doc("FHIR Resource Map", fhir_resource_map)

	compiled_map = resource_map.compiled_mapping
	if isinstance(compiled_map, str):
		compiled_map = frappe.parse_json(compiled_map)

	resolver = FHIRValueResolver(compiled_map, primary_name)
	resolved_values = resolver.resolve()

	generator = FHIRResourceGenerator(compiled_map, resolved_values)
	return generator.generate()
