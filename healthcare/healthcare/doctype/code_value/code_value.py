# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document


class CodeValue(Document):
	def autoname(self):
		# Local code systems flagged "Name by Code" are named by the bare code (e.g.
		# "Final") so the value can be stored directly on documents and link cleanly;
		# all other systems keep the "{code}-{version}-{system}" form for cross-system
		# uniqueness.
		if self.code_system and frappe.db.get_value("Code System", self.code_system, "name_by_code"):
			self.name = self.code_value
			return
		self.name = f"{self.code_value}{'-' + self.version if self.version else ''}-{self.code_system}"
