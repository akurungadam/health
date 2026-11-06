// Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("OT Booking", {
	setup: function (frm) {
		frm.set_query("theatre", () => ({
			filters: { is_ot: 1, is_group: 0, company: frm.doc.company },
		}));
		frm.set_query("procedure_template", "procedures", () => ({
			filters: { requires_ot: 1, disabled: 0 },
		}));
		frm.set_query("service_request", "procedures", () => ({
			filters: {
				patient: frm.doc.patient,
				template_dt: "Clinical Procedure Template",
				status: "active-Request Status",
				docstatus: 1,
			},
		}));
		frm.set_query("inpatient_record", () => ({
			filters: { patient: frm.doc.patient, status: ["!=", "Discharged"] },
		}));
	},

	refresh: function (frm) {
		if (!frm.is_new() && has_procedures_to_create(frm)) {
			frm.add_custom_button(__("Create Procedures"), () =>
				create_procedures(frm),
			);
			frm.change_custom_button_type(__("Create Procedures"), null, "primary");
		}
	},
});

let has_procedures_to_create = function (frm) {
	const open = !["Cancelled", "Postponed", "Completed"].includes(frm.doc.status);
	return open && frm.doc.procedures.some(row => !row.clinical_procedure);
};

let create_procedures = function (frm) {
	frappe.call({
		doc: frm.doc,
		method: "create_clinical_procedures",
		freeze: true,
		callback: function (r) {
			if (r.exc) return;
			frappe.show_alert({
				message: __("{0} Clinical Procedure(s) created", [r.message.length]),
				indicator: "green",
			});
			frm.reload_doc();
		},
	});
};
