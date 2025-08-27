// Copyright (c) 2023, healthcare and contributors
// For license information, please see license.txt

frappe.ui.form.on("Clinical Note", {
	onload: function (frm) {
		frm.set_value("user", frappe.session.user);
		frm.trigger("user");
	},

	terms_and_conditions: function (frm) {
		set_terms_and_conditions(frm)
	},

	birth_date: function(frm) {
		let age_str = calculate_age(frm.doc.birth_date);
		frm.set_value('age', age_str);
	}
});

var set_terms_and_conditions = function (frm, terms_and_conditions = '') {
	if (frm.doc.terms_and_conditions) {
		return frappe.call({
			method: 'erpnext.setup.doctype.terms_and_conditions.terms_and_conditions.get_terms_and_conditions',
			args: {
				template_name: frm.doc.terms_and_conditions || terms_and_conditions,
				doc: frm.doc
			},
			callback: function (r) {
				frm.set_value('note', r.message)
			}
		});
	} else {
		frm.set_value('note', '')
	}
};

let calculate_age = function(birth) {
	let ageMS = Date.parse(Date()) - Date.parse(birth);
	let age = new Date();
	age.setTime(ageMS);
	let years =  age.getFullYear() - 1970;
	if (years >= 0) {
		return `${years} ${__('Years(s)')} ${age.getMonth()} ${__('Month(s)')} ${age.getDate()} ${__('Day(s)')}`;
	} else {
		return `NA`
	}
};