# Copyright (c) 2017, earthians and Contributors
# See license.txt

import frappe

from healthcare.healthcare.doctype.clinical_procedure.test_clinical_procedure import (
	create_clinical_procedure_template,
)
from healthcare.healthcare.doctype.healthcare_service_unit_type.test_healthcare_service_unit_type import (
	create_theatre_type,
)
from healthcare.tests.utils import HealthcareTestSuite


class TestClinicalProcedureTemplate(HealthcareTestSuite):
	def test_theatre_type_must_be_an_ot_type(self):
		template = create_clinical_procedure_template()
		template.requires_ot = 1
		template.required_theatre_type = create_theatre_type("_Test Ward Type", is_ot=0).name

		self.assertRaises(frappe.ValidationError, template.save)

	def test_ot_theatre_type_is_accepted(self):
		template = create_clinical_procedure_template()
		template.requires_ot = 1
		template.required_theatre_type = create_theatre_type("_Test Laminar Flow OT").name
		template.save()

		self.assertEqual(template.required_theatre_type, "_Test Laminar Flow OT")

	def test_theatre_type_is_cleared_when_ot_is_not_required(self):
		template = create_clinical_procedure_template()
		template.requires_ot = 0
		template.required_theatre_type = create_theatre_type("_Test Laminar Flow OT").name
		template.save()

		self.assertFalse(template.required_theatre_type)
