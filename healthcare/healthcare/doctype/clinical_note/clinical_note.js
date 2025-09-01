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

	birth_date: function (frm) {
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

let calculate_age = function (birth) {
	let ageMS = Date.parse(Date()) - Date.parse(birth);
	let age = new Date();
	age.setTime(ageMS);
	let years = age.getFullYear() - 1970;
	if (years >= 0) {
		return `${years} ${__('Years(s)')} ${age.getMonth()} ${__('Month(s)')} ${age.getDate()} ${__('Day(s)')}`;
	} else {
		return `NA`
	}
};

/** Clinical Note — format-aware quick entry behavior
 * Works in both Quick Entry dialog and full form.
 */
/** Utilities */

function toggle_fields_by_format(frm) {
	const fmt = (frm.doc.note_format || 'Narrative').trim();

	// All format field groups (from your schema)
	const groups = {
		'Narrative': ['terms_and_conditions', 'note'],
		'SOAP': ['subjective', 'objective', 'assessment', 'plan'],
		'EIR': ['evaluation', 'intervention', 'revision'],
		'PIE': ['pie_problem', 'pie_intervention', 'pie_evaluation'],
		'FOCUS/DAR': ['topic', 'data', 'action', 'response'],
		'SBAR': ['sbar_situation', 'sbar_background', 'sbar_assessment', 'sbar_recommendation'],
	};

	// Flatten all unique fields that belong to any format
	const all_fields = Array.from(new Set([].concat(...Object.values(groups))));

	// Fields required per format (adjust if your policy differs)
	const required_map = {
		'Narrative': ['note'],
		'SOAP': ['subjective', 'objective', 'assessment', 'plan'],
		'EIR': ['evaluation'], // often EIR is optional; tweak as needed
		'PIE': ['pie_problem', 'pie_intervention', 'pie_evaluation'],
		'FOCUS/DAR': ['topic', 'data', 'action', 'response'],
		'SBAR': ['sbar_situation', 'sbar_background', 'sbar_assessment', 'sbar_recommendation'],
	};

	// Show/Hide + Required toggles
	const show_now = new Set(groups[fmt] || []);
	const req_now = new Set(required_map[fmt] || []);

	// Support both full Form and Quick Entry Dialog
	const is_dialog = !!cur_dialog;
	const setHidden = (fieldname, hidden) => {
		if (is_dialog) {
			const f = cur_dialog.get_field(fieldname);
			if (f) {
				f.df.hidden = hidden ? 1 : 0;
				// In quick entry, refresh+layout is needed
				f.refresh && f.refresh();
				cur_dialog.layout && cur_dialog.layout.refresh_sections();
			}
		} else {
			// standard form
			frm.set_df_property(fieldname, 'hidden', hidden ? 1 : 0);
		}
	};
	const setReqd = (fieldname, reqd) => {
		if (is_dialog) {
			const f = cur_dialog.get_field(fieldname);
			if (f) {
				f.df.reqd = reqd ? 1 : 0;
				f.refresh && f.refresh();
			}
		} else {
			frm.set_df_property(fieldname, 'reqd', reqd ? 1 : 0);
		}
	};

	// Hide everything first (only those in our control list),
	// then show the current set and toggle reqd flags.
	all_fields.forEach(fn => {
		setHidden(fn, true);
		setReqd(fn, false);
	});
	show_now.forEach(fn => setHidden(fn, false));
	req_now.forEach(fn => setReqd(fn, true));

	// Optional niceties: collapse/expand label sections (visual only)
	// Your schema already has Section Breaks with depends_on;
	// Quick Entry ignores Sections, so we mimic with minimal headings.
	inject_section_headings_if_quick_entry(fmt);

	// If SBAR chosen, pre-fill gentle placeholders (only when empty)
	if (fmt === 'SBAR') {
		safe_placeholder(frm, 'sbar_situation', '**S:** ');
		safe_placeholder(frm, 'sbar_background', '**B:** ');
		safe_placeholder(frm, 'sbar_assessment', '**A:** ');
		safe_placeholder(frm, 'sbar_recommendation', '**R:** ');
	}
}

function inject_section_headings_if_quick_entry(fmt) {
	if (!cur_dialog) return;
	const headings = {
		'Narrative': 'Narrative',
		'SOAP': 'SOAP',
		'EIR': 'EIR',
		'PIE': 'PIE',
		'FOCUS/DAR': 'F-DAR',
		'SBAR': 'SBAR'
	};
	const $body = $(cur_dialog.body || cur_dialog.$body || []);
	if (!$body.length) return;

	// remove any previous heading we added
	$body.find('.cn-quick-heading').remove();

	// Add a subtle heading just before the first visible field
	const firstVisible = (cur_dialog.fields_list || [])
		.map(f => cur_dialog.get_field(f.df.fieldname))
		.find(f => f && !f.df.hidden);

	if (firstVisible && firstVisible.$wrapper) {
		$('<div class="cn-quick-heading" style="margin:6px 0 4px;font-weight:600;color:#666;"></div>')
			.text(headings[fmt] || fmt)
			.insertBefore(firstVisible.$wrapper);
	}
}

function safe_placeholder(frm, fieldname, text) {
	// Only insert if empty; works for both dialog & form
	if (cur_dialog) {
		const f = cur_dialog.get_field(fieldname);
		if (f && !f.get_value()) {
			f.set_value(text);
		}
	} else {
		if (!frm.doc[fieldname]) {
			frm.set_value(fieldname, text);
		}
	}
}
