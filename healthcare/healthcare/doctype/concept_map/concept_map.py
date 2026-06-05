# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Concept Map - a FHIR-shaped translation table.

One Concept Map document = one source Code Value and its target codings (a small
``targets`` table, one per system: LOINC, SNOMED, ...). The document is named after
its source code, so translating is a primary-key lookup - no monolithic table and
no scanning. The minimal terminology service answers the one question the FHIR layer
needs: "what does this local code mean in a standard system?" - reusing Code Value;
no external terminology server.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class ConceptMap(Document):
	def validate(self):
		self._dedupe_targets()

	def _dedupe_targets(self):
		seen = set()
		for row in self.targets or []:
			if row.target_code in seen:
				frappe.throw(_("Duplicate target code {0} in row {1}.").format(row.target_code, row.idx))
			seen.add(row.target_code)


class TerminologyService:
	"""Read-only terminology lookups over Code Value + Concept Map."""

	@staticmethod
	def translate(code, system=None):
		"""Translate a local ``code`` to its FHIR target codings.

		``system`` (a Code System name) disambiguates the source code. Returns a list
		of ``{system, code, display}`` codings (empty when nothing matches) so a
		CodeableConcept can carry several.
		"""
		codings = []
		for source_name in TerminologyService._code_value_names(code, system):
			if not frappe.db.exists("Concept Map", source_name):
				continue
			for row in frappe.get_cached_doc("Concept Map", source_name).targets:
				coding = TerminologyService._coding(row.target_code)
				if coding and coding not in codings:
					codings.append(coding)
		return codings

	@staticmethod
	def lookup(code, system=None):
		"""Return the coding for a code that is already a Code Value (fills system/display)."""
		names = TerminologyService._code_value_names(code, system)
		return TerminologyService._coding(names[0]) if names else None

	@staticmethod
	def _code_value_names(code, system=None):
		if not code:
			return []
		filters = {"code_value": code}
		if system:
			filters["code_system"] = system
		return frappe.get_all("Code Value", filters=filters, pluck="name")

	@staticmethod
	def _coding(code_value_name):
		if not code_value_name:
			return None
		cv = frappe.get_cached_doc("Code Value", code_value_name)
		coding = {"code": cv.code_value}
		if cv.system_uri:
			coding["system"] = cv.system_uri
		if cv.display:
			coding["display"] = cv.display
		return coding


@frappe.whitelist()
def translate(code, system=None):
	return TerminologyService.translate(code, system=system)


@frappe.whitelist()
def lookup(code, system=None):
	return TerminologyService.lookup(code, system=system)
