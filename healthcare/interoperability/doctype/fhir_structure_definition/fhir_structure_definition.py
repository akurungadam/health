# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class FHIRStructureDefinition(Document):
	def autoname(self):
		if self.fhir_profile:
			self.name = f"{self.fhir_sd}-{self.fhir_profile}-{self.fhir_version}"
		else:
			self.name = f"{self.fhir_sd}-{self.fhir_version}"
