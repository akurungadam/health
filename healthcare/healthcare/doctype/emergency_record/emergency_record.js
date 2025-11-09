// Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Emergency Record", {
	onload: function(frm) {
        show_clinical_notes(frm);
		show_orders(frm);
	},
    triage_level: function(frm) {
        if (!frm.doc.triage_done_by && frm.doc.triage_level) {
            frm.set_value("triage_done_by", frappe.session.user);
            frm.set_value("triage_datetime", frappe.datetime.now_datetime());
        }
        if (frm.doc.triage_level) {
            frappe.db.get_value("Triage Level", frm.doc.triage_level, "color")
            .then((r) => {
                if (r && r.message) {
                    frm.set_value("triage_color", r.message.color);
                }
            });
            frm.set_value
        }
    },
});

var show_clinical_notes = async function(frm) {
	if (frm.doc.docstatus == 0 && frm.doc.patient) {
		const clinical_notes = new healthcare.ClinicalNotes({
			frm: frm,
			notes_wrapper: $(frm.fields_dict.clinical_notes.wrapper),
		});
		clinical_notes.refresh();
	}
}

var show_orders = async function(frm) {
	if (frm.doc.docstatus == 0 && frm.doc.patient) {
		const orders = new healthcare.Orders({
			frm: frm,
			open_activities_wrapper: $(frm.fields_dict.order_history_html.wrapper),
			form_wrapper: $(frm.wrapper),
			create_orders: true,
		});
		orders.refresh();
	}
}