# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def execute():
	ot_types = frappe.get_all("Healthcare Service Unit Type", {"is_ot": 1}, pluck="name")
	if not ot_types:
		return
	frappe.db.set_value(
		"Healthcare Service Unit",
		{"service_unit_type": ("in", ot_types)},
		"is_ot",
		1,
		update_modified=False,
	)
