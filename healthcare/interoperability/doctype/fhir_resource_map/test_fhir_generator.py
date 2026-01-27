import frappe
from frappe.tests.utils import IntegrationTestCase

from healthcare.interoperability.doctype.fhir_resource_map.fhir_resource_generator import (
	FHIRResourceGenerator,
	FHIRResourceGenerationError,
)

from healthcare.interoperability.doctype.fhir_resource_map.fhir_compiler import FHIRMappingCompiler
from healthcare.interoperability.doctype.fhir_resource_map.fhir_value_resolver import FHIRValueResolver


class TestFHIRGenerator(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Reuse your existing helper if it exists; else ensure doctypes here
		# cls._ensure_test_doctypes()
		# cls._create_gender("Female")
		pass

	def test_generator_builds_patient_resource(self):
		# Replace these with your existing helper calls
		patient_name = self._create_patient_with_telecom_rows(
			dob="1985-02-04",
			language="en",
			sex="Female",
			telecom_rows=[
				{"type": "phone", "phone_xtty": "+91-9999999999"},
				{"type": "phone", "phone_xtty": "+91-8888888888"},
			],
		)
		self._create_patient_appointment(patient_name, practitioner_name="Dilpreet Saini")

		resource_map = self._build_resource_map()  # your helper that builds the FHIR Resource Map doc/dict
		compiled = FHIRMappingCompiler(resource_map).compile()

		resolved = FHIRValueResolver(compiled, patient_name).resolve()

		generator = FHIRResourceGenerator(compiled, resolved)
		resource = generator.build()

		self.assertEqual(resource.get("resourceType"), "Patient")
		self.assertEqual(resource.get("birthDate"), "1985-02-04")
		self.assertEqual(resource.get("gender"), "female")

		self.assertTrue(isinstance(resource.get("telecom"), list))
		self.assertEqual(len(resource.get("telecom")), 2)
		self.assertEqual(resource["telecom"][0]["value"], "+91-999999999")

		self.assertTrue(isinstance(resource.get("identifier"), list))
		self.assertEqual(resource["identifier"][0]["use"], "usual")

	def test_generator_raises_when_required_child_missing_in_row(self):
		patient_name = self._create_patient_with_telecom_rows(
			dob="1985-02-04",
			language="en",
			sex="Female",
			telecom_rows=[
				{"type": "phone", "phone_xtty": None},  # value min=1 should fail
			],
		)

		resource_map = self._build_resource_map()
		compiled = FHIRMappingCompiler(resource_map).compile()
		resolved = FHIRValueResolver(compiled, patient_name).resolve()

		with self.assertRaises(FHIRResourceGenerationError):
			FHIRResourceGenerator(compiled, resolved).build()
