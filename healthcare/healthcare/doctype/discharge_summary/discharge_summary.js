// Copyright (c) 2023, healthcare and contributors
// For license information, please see license.txt

frappe.ui.form.on("Discharge Summary", {
	refresh: function (frm){
		frm.set_query('inpatient_record', function(doc) {
			return {
				filters: {
					status: "Discharge Scheduled",
				},
			};
		});
	},

	onload: function (frm) {
		show_orders(frm);
	},

	inpatient_record: function (frm) {
		show_orders(frm);
	},

	physical_examination_template: function (frm) {
		set_terms_and_conditions(frm, "physical_examination_template", "physical_examination")
	},

	treatment_template: function (frm) {
		set_terms_and_conditions(frm, "treatment_template", "treatment_done")
	},

	advice_on_discharge_template: function (frm) {
		set_terms_and_conditions(frm, "advice_on_discharge_template", "advice_on_discharge")
	},

	diet_template: function (frm) {
		set_terms_and_conditions(frm, "diet_template", "diet_adviced")
	},

	instructions_template: function (frm) {
		set_terms_and_conditions(frm, "instructions_template", "instructions")
	}
});

var show_orders = function (frm) {
	const orders = new healthcare.Orders({
		frm: frm,
		open_activities_wrapper: $(frm.fields_dict.orders_html.wrapper),
		form_wrapper: $(frm.wrapper),
		create_orders: true,
	});
	orders.refresh();
}

var set_terms_and_conditions = function (frm, template_field, target_field) {
	if (frm.doc[template_field]) {
		return frappe.call({
			method: "erpnext.setup.doctype.terms_and_conditions.terms_and_conditions.get_terms_and_conditions",
			args: {
				template_name: frm.doc[template_field],
				doc: frm.doc
			},
			callback: function (r) {
				frm.set_value(target_field, r.message)
			}
		});
	} else {
		frm.set_value(target_field, "")
	}
}
