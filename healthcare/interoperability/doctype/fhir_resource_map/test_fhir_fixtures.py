"""
Test Fixtures for FHIR Resource Generator Tests

Run this to set up required test data in the database.
"""

import json

import frappe


def setup_fhir_test_fixtures():
	"""Set up all required test fixtures for FHIR tests."""
	setup_primitive_datatypes()
	setup_complex_datatypes()
	setup_structure_definitions()
	frappe.db.commit()
	print("FHIR test fixtures created successfully!")


def setup_primitive_datatypes():
	"""Create primitive FHIR datatype records."""
	primitives = [
		{"datatype": "string", "is_primitive": 1, "regex": None},
		{"datatype": "boolean", "is_primitive": 1, "regex": None},
		{"datatype": "integer", "is_primitive": 1, "regex": r"^[0]|[-+]?[1-9][0-9]*$"},
		{
			"datatype": "decimal",
			"is_primitive": 1,
			"regex": r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$",
		},
		{
			"datatype": "date",
			"is_primitive": 1,
			"regex": r"^([0-9]([0-9]([0-9][1-9]|[1-9]0)|[1-9]00)|[1-9]000)(-(0[1-9]|1[0-2])(-(0[1-9]|[1-2][0-9]|3[0-1]))?)?$",
		},
		{"datatype": "dateTime", "is_primitive": 1, "regex": None},
		{"datatype": "instant", "is_primitive": 1, "regex": None},
		{
			"datatype": "time",
			"is_primitive": 1,
			"regex": r"^([01][0-9]|2[0-3]):[0-5][0-9]:([0-5][0-9]|60)(\.[0-9]+)?$",
		},
		{"datatype": "code", "is_primitive": 1, "regex": r"^[^\s]+(\s[^\s]+)*$"},
		{"datatype": "uri", "is_primitive": 1, "regex": None},
		{"datatype": "url", "is_primitive": 1, "regex": None},
		{"datatype": "canonical", "is_primitive": 1, "regex": None},
		{"datatype": "id", "is_primitive": 1, "regex": r"^[A-Za-z0-9\-\.]{1,64}$"},
		{"datatype": "oid", "is_primitive": 1, "regex": r"^urn:oid:[0-2](\.(0|[1-9][0-9]*))+$"},
		{
			"datatype": "uuid",
			"is_primitive": 1,
			"regex": r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
		},
		{"datatype": "markdown", "is_primitive": 1, "regex": None},
		{"datatype": "base64Binary", "is_primitive": 1, "regex": None},
		{"datatype": "positiveInt", "is_primitive": 1, "regex": r"^[1-9][0-9]*$"},
		{"datatype": "unsignedInt", "is_primitive": 1, "regex": r"^[0]|([1-9][0-9]*)$"},
		{"datatype": "xhtml", "is_primitive": 1, "regex": None},
	]

	for p in primitives:
		if not frappe.db.exists("FHIR Datatype", p["datatype"]):
			doc = frappe.get_doc(
				{
					"doctype": "FHIR Datatype",
					"datatype": p["datatype"],
					"is_primitive": p["is_primitive"],
					"regex": p.get("regex"),
				}
			)
			doc.insert(ignore_permissions=True)
			print(f"  Created primitive: {p['datatype']}")


def setup_complex_datatypes():
	"""Create complex FHIR datatype records with their elements."""

	complex_types = [
		{
			"datatype": "Identifier",
			"is_primitive": 0,
			"elements": [
				{"element_name": "use", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "type", "datatype": "CodeableConcept", "min": 0, "max": "1"},
				{"element_name": "system", "datatype": "uri", "min": 0, "max": "1"},
				{"element_name": "value", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "period", "datatype": "Period", "min": 0, "max": "1"},
				{"element_name": "assigner", "datatype": "Reference", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "CodeableConcept",
			"is_primitive": 0,
			"elements": [
				{"element_name": "coding", "datatype": "Coding", "min": 0, "max": "*"},
				{"element_name": "text", "datatype": "string", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "Coding",
			"is_primitive": 0,
			"elements": [
				{"element_name": "system", "datatype": "uri", "min": 0, "max": "1"},
				{"element_name": "version", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "code", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "display", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "userSelected", "datatype": "boolean", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "HumanName",
			"is_primitive": 0,
			"elements": [
				{"element_name": "use", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "text", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "family", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "given", "datatype": "string", "min": 0, "max": "*"},
				{"element_name": "prefix", "datatype": "string", "min": 0, "max": "*"},
				{"element_name": "suffix", "datatype": "string", "min": 0, "max": "*"},
				{"element_name": "period", "datatype": "Period", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "Address",
			"is_primitive": 0,
			"elements": [
				{"element_name": "use", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "type", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "text", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "line", "datatype": "string", "min": 0, "max": "*"},
				{"element_name": "city", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "district", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "state", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "postalCode", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "country", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "period", "datatype": "Period", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "ContactPoint",
			"is_primitive": 0,
			"elements": [
				{"element_name": "system", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "value", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "use", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "rank", "datatype": "positiveInt", "min": 0, "max": "1"},
				{"element_name": "period", "datatype": "Period", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "Reference",
			"is_primitive": 0,
			"elements": [
				{"element_name": "reference", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "type", "datatype": "uri", "min": 0, "max": "1"},
				{"element_name": "identifier", "datatype": "Identifier", "min": 0, "max": "1"},
				{"element_name": "display", "datatype": "string", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "Period",
			"is_primitive": 0,
			"elements": [
				{"element_name": "start", "datatype": "dateTime", "min": 0, "max": "1"},
				{"element_name": "end", "datatype": "dateTime", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "Quantity",
			"is_primitive": 0,
			"elements": [
				{"element_name": "value", "datatype": "decimal", "min": 0, "max": "1"},
				{"element_name": "comparator", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "unit", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "system", "datatype": "uri", "min": 0, "max": "1"},
				{"element_name": "code", "datatype": "code", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "Range",
			"is_primitive": 0,
			"elements": [
				{"element_name": "low", "datatype": "Quantity", "min": 0, "max": "1"},
				{"element_name": "high", "datatype": "Quantity", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "Ratio",
			"is_primitive": 0,
			"elements": [
				{"element_name": "numerator", "datatype": "Quantity", "min": 0, "max": "1"},
				{"element_name": "denominator", "datatype": "Quantity", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "Attachment",
			"is_primitive": 0,
			"elements": [
				{"element_name": "contentType", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "language", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "data", "datatype": "base64Binary", "min": 0, "max": "1"},
				{"element_name": "url", "datatype": "url", "min": 0, "max": "1"},
				{"element_name": "size", "datatype": "unsignedInt", "min": 0, "max": "1"},
				{"element_name": "hash", "datatype": "base64Binary", "min": 0, "max": "1"},
				{"element_name": "title", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "creation", "datatype": "dateTime", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "Annotation",
			"is_primitive": 0,
			"elements": [
				{"element_name": "authorReference", "datatype": "Reference", "min": 0, "max": "1"},
				{"element_name": "authorString", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "time", "datatype": "dateTime", "min": 0, "max": "1"},
				{"element_name": "text", "datatype": "markdown", "min": 1, "max": "1"},
			],
		},
		{
			"datatype": "Age",
			"is_primitive": 0,
			"elements": [
				{"element_name": "value", "datatype": "decimal", "min": 0, "max": "1"},
				{"element_name": "comparator", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "unit", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "system", "datatype": "uri", "min": 0, "max": "1"},
				{"element_name": "code", "datatype": "code", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "Duration",
			"is_primitive": 0,
			"elements": [
				{"element_name": "value", "datatype": "decimal", "min": 0, "max": "1"},
				{"element_name": "comparator", "datatype": "code", "min": 0, "max": "1"},
				{"element_name": "unit", "datatype": "string", "min": 0, "max": "1"},
				{"element_name": "system", "datatype": "uri", "min": 0, "max": "1"},
				{"element_name": "code", "datatype": "code", "min": 0, "max": "1"},
			],
		},
		{
			"datatype": "Money",
			"is_primitive": 0,
			"elements": [
				{"element_name": "value", "datatype": "decimal", "min": 0, "max": "1"},
				{"element_name": "currency", "datatype": "code", "min": 0, "max": "1"},
			],
		},
	]

	for ct in complex_types:
		if not frappe.db.exists("FHIR Datatype", ct["datatype"]):
			doc = frappe.get_doc(
				{
					"doctype": "FHIR Datatype",
					"datatype": ct["datatype"],
					"is_primitive": ct["is_primitive"],
				}
			)

			for el in ct.get("elements", []):
				doc.append(
					"elements",
					{
						"element_name": el["element_name"],
						"datatype": el["datatype"],
						"min": el.get("min", 0),
						"max": el.get("max", "*"),
					},
				)

			doc.insert(ignore_permissions=True)
			print(f"  Created complex type: {ct['datatype']}")


def setup_structure_definitions():
	"""Create basic structure definitions for testing."""

	# Patient Structure Definition
	if not frappe.db.exists("FHIR Structure Definition", "Patient-R4"):
		patient_sd = frappe.get_doc(
			{
				"doctype": "FHIR Structure Definition",
				"fhir_sd": "Patient",
				"sd_type": "Patient",
				"kind": "Resource",
			}
		)

		patient_elements = [
			{"path": "Patient", "datatype": "", "min": 0, "max": "*"},
			{"path": "Patient.id", "datatype": "id", "min": 0, "max": "1"},
			{"path": "Patient.meta", "datatype": "Meta", "min": 0, "max": "1"},
			{"path": "Patient.identifier", "datatype": "Identifier", "min": 0, "max": "*"},
			{"path": "Patient.active", "datatype": "boolean", "min": 0, "max": "1"},
			{"path": "Patient.name", "datatype": "HumanName", "min": 0, "max": "*"},
			{"path": "Patient.telecom", "datatype": "ContactPoint", "min": 0, "max": "*"},
			{"path": "Patient.gender", "datatype": "code", "min": 0, "max": "1"},
			{"path": "Patient.birthDate", "datatype": "date", "min": 0, "max": "1"},
			{"path": "Patient.deceasedBoolean", "datatype": "boolean", "min": 0, "max": "1"},
			{"path": "Patient.deceasedDateTime", "datatype": "dateTime", "min": 0, "max": "1"},
			{"path": "Patient.address", "datatype": "Address", "min": 0, "max": "*"},
			{"path": "Patient.maritalStatus", "datatype": "CodeableConcept", "min": 0, "max": "1"},
			{"path": "Patient.multipleBirthBoolean", "datatype": "boolean", "min": 0, "max": "1"},
			{"path": "Patient.multipleBirthInteger", "datatype": "integer", "min": 0, "max": "1"},
			{"path": "Patient.contact", "datatype": "BackboneElement", "min": 0, "max": "*"},
			{"path": "Patient.contact.relationship", "datatype": "CodeableConcept", "min": 0, "max": "*"},
			{"path": "Patient.contact.name", "datatype": "HumanName", "min": 0, "max": "1"},
			{"path": "Patient.contact.telecom", "datatype": "ContactPoint", "min": 0, "max": "*"},
			{"path": "Patient.contact.address", "datatype": "Address", "min": 0, "max": "1"},
			{"path": "Patient.contact.gender", "datatype": "code", "min": 0, "max": "1"},
			{"path": "Patient.communication", "datatype": "BackboneElement", "min": 0, "max": "*"},
			{"path": "Patient.communication.language", "datatype": "CodeableConcept", "min": 1, "max": "1"},
			{"path": "Patient.communication.preferred", "datatype": "boolean", "min": 0, "max": "1"},
			{"path": "Patient.managingOrganization", "datatype": "Reference", "min": 0, "max": "1"},
			{"path": "Patient.link", "datatype": "BackboneElement", "min": 0, "max": "*"},
			{"path": "Patient.link.other", "datatype": "Reference", "min": 1, "max": "1"},
			{"path": "Patient.link.type", "datatype": "code", "min": 1, "max": "1"},
		]

		for el in patient_elements:
			patient_sd.append("element_paths", el)

		patient_sd.insert(ignore_permissions=True)
		print("  Created structure definition: Patient-R4")

	# Observation Structure Definition
	if not frappe.db.exists("FHIR Structure Definition", "Observation-R4"):
		obs_sd = frappe.get_doc(
			{
				"doctype": "FHIR Structure Definition",
				"fhir_sd": "Observation",
				"sd_type": "Observation",
				"kind": "Resource",
			}
		)

		obs_elements = [
			{"path": "Observation", "datatype": "", "min": 0, "max": "*"},
			{"path": "Observation.id", "datatype": "id", "min": 0, "max": "1"},
			{"path": "Observation.meta", "datatype": "Meta", "min": 0, "max": "1"},
			{"path": "Observation.identifier", "datatype": "Identifier", "min": 0, "max": "*"},
			{"path": "Observation.status", "datatype": "code", "min": 1, "max": "1"},
			{"path": "Observation.category", "datatype": "CodeableConcept", "min": 0, "max": "*"},
			{"path": "Observation.code", "datatype": "CodeableConcept", "min": 1, "max": "1"},
			{"path": "Observation.subject", "datatype": "Reference", "min": 0, "max": "1"},
			{"path": "Observation.encounter", "datatype": "Reference", "min": 0, "max": "1"},
			{"path": "Observation.effectiveDateTime", "datatype": "dateTime", "min": 0, "max": "1"},
			{"path": "Observation.effectivePeriod", "datatype": "Period", "min": 0, "max": "1"},
			{"path": "Observation.issued", "datatype": "instant", "min": 0, "max": "1"},
			{"path": "Observation.performer", "datatype": "Reference", "min": 0, "max": "*"},
			{"path": "Observation.valueQuantity", "datatype": "Quantity", "min": 0, "max": "1"},
			{"path": "Observation.valueCodeableConcept", "datatype": "CodeableConcept", "min": 0, "max": "1"},
			{"path": "Observation.valueString", "datatype": "string", "min": 0, "max": "1"},
			{"path": "Observation.valueBoolean", "datatype": "boolean", "min": 0, "max": "1"},
			{"path": "Observation.valueInteger", "datatype": "integer", "min": 0, "max": "1"},
			{"path": "Observation.valueRange", "datatype": "Range", "min": 0, "max": "1"},
			{"path": "Observation.valueRatio", "datatype": "Ratio", "min": 0, "max": "1"},
			{"path": "Observation.interpretation", "datatype": "CodeableConcept", "min": 0, "max": "*"},
			{"path": "Observation.note", "datatype": "Annotation", "min": 0, "max": "*"},
			{"path": "Observation.bodySite", "datatype": "CodeableConcept", "min": 0, "max": "1"},
			{"path": "Observation.method", "datatype": "CodeableConcept", "min": 0, "max": "1"},
			{"path": "Observation.referenceRange", "datatype": "BackboneElement", "min": 0, "max": "*"},
			{"path": "Observation.referenceRange.low", "datatype": "Quantity", "min": 0, "max": "1"},
			{"path": "Observation.referenceRange.high", "datatype": "Quantity", "min": 0, "max": "1"},
			{"path": "Observation.referenceRange.type", "datatype": "CodeableConcept", "min": 0, "max": "1"},
			{"path": "Observation.referenceRange.text", "datatype": "string", "min": 0, "max": "1"},
			{"path": "Observation.component", "datatype": "BackboneElement", "min": 0, "max": "*"},
			{"path": "Observation.component.code", "datatype": "CodeableConcept", "min": 1, "max": "1"},
			{"path": "Observation.component.valueQuantity", "datatype": "Quantity", "min": 0, "max": "1"},
			{
				"path": "Observation.component.valueCodeableConcept",
				"datatype": "CodeableConcept",
				"min": 0,
				"max": "1",
			},
			{"path": "Observation.component.valueString", "datatype": "string", "min": 0, "max": "1"},
		]

		for el in obs_elements:
			obs_sd.append("element_paths", el)

		obs_sd.insert(ignore_permissions=True)
		print("  Created structure definition: Observation-R4")


def teardown_fhir_test_fixtures():
	"""Remove test fixtures."""
	# Delete structure definitions
	for name in ["Patient-R4", "Observation-R4"]:
		if frappe.db.exists("FHIR Structure Definition", name):
			frappe.delete_doc("FHIR Structure Definition", name, force=True)

	# Note: Don't delete datatypes as they may be used elsewhere

	frappe.db.commit()
	print("FHIR test fixtures removed.")


# Run setup if called directly
if __name__ == "__main__":
	setup_fhir_test_fixtures()
