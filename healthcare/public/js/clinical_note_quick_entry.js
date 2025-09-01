frappe.provide("frappe.ui.form");
frappe.provide("healthcare");

healthcare.clinical_note_fields = function () {
	return [
		{ label: __("Patient"), fieldname: "patient", fieldtype: "Link", options: "Patient", reqd: 1 },
		{ fieldtype: "Column Break" },
		{ label: __("Clinical Note Type"), fieldname: "clinical_note_type", fieldtype: "Link", options: "Clinical Note Type", reqd: 0 },
		{
			label: __("Note Format"), fieldname: "note_format", fieldtype: "Select",
			options: ["Narrative", "SOAP", "EIR", "FOCUS/DAR", "PIE", "SBAR"].join("\n"), default: "Narrative", reqd: 1
		},

		{ fieldtype: "Section Break", label: __("Narrative"), depends_on: "eval:doc.note_format=='Narrative'" },
		{ label: __("Narrative Template"), fieldname: "terms_and_conditions", fieldtype: "Link", options: "Terms and Conditions" },
		{ label: __("Narrative"), fieldname: "narrative", fieldtype: "Text Editor" },

		{ fieldtype: "Section Break", label: __("SOAP"), depends_on: "eval:doc.note_format=='SOAP'" },
		{ label: __("Subjective"), fieldname: "subjective", fieldtype: "Small Text" },
		{ label: __("Objective"), fieldname: "objective", fieldtype: "Small Text" },
		{ fieldtype: "Column Break" },
		{ label: __("Assessment"), fieldname: "assessment", fieldtype: "Small Text" },
		{ label: __("Plan"), fieldname: "plan", fieldtype: "Small Text" },

		{ fieldtype: "Section Break", label: __("EIR"), depends_on: "eval:doc.note_format=='EIR'" },
		{ label: __("Evaluation"), fieldname: "evaluation", fieldtype: "Small Text" },
		{ fieldtype: "Column Break" },
		{ label: __("Intervention"), fieldname: "intervention", fieldtype: "Small Text" },
		{ fieldtype: "Column Break" },
		{ label: __("Revision"), fieldname: "revision", fieldtype: "Small Text" },

		{ fieldtype: "Section Break", label: __("PIE"), depends_on: "eval:doc.note_format=='PIE'" },
		{ label: __("Problem"), fieldname: "pie_problem", fieldtype: "Small Text" },
		{ fieldtype: "Column Break" },
		{ label: __("Intervention"), fieldname: "pie_intervention", fieldtype: "Small Text" },
		{ fieldtype: "Column Break" },
		{ label: __("Evaluation"), fieldname: "pie_evaluation", fieldtype: "Small Text" },

		{ fieldtype: "Section Break", label: __("F-DAR"), depends_on: "eval:doc.note_format=='FOCUS/DAR'" },
		{ label: __("Topic"), fieldname: "topic", fieldtype: "Small Text" },
		{ label: __("Data"), fieldname: "data", fieldtype: "Small Text" },
		{ fieldtype: "Column Break" },
		{ label: __("Action"), fieldname: "action", fieldtype: "Small Text" },
		{ label: __("Response"), fieldname: "response", fieldtype: "Small Text" },

		{ fieldtype: "Section Break", label: __("SBAR"), depends_on: "eval:doc.note_format=='SBAR'" },
		{ label: __("Situation"), fieldname: "sbar_situation", fieldtype: "Small Text" },
		{ label: __("Background"), fieldname: "sbar_background", fieldtype: "Small Text" },
		{ fieldtype: "Column Break" },
		{ label: __("Assessment"), fieldname: "sbar_assessment", fieldtype: "Small Text" },
		{ label: __("Recommendation"), fieldname: "sbar_recommendation", fieldtype: "Small Text" },

		{ fieldtype: "Section Break", label: __("Reference") },
		{ label: __("Reference Doc"), fieldname: "reference_doc", fieldtype: "Link", options: "DocType", read_only: 1 },
		{ label: __("Reference Name"), fieldname: "reference_name", fieldtype: "Dynamic Link", options: "reference_doc", read_only: 1 },
	];
};

healthcare.apply_note_format = function (dlg) {
	const groups = {
		"Narrative": ["terms_and_conditions", "narrative"],
		"SOAP": ["subjective", "objective", "assessment", "plan"],
		"EIR": ["evaluation", "intervention", "revision"],
		"PIE": ["pie_problem", "pie_intervention", "pie_evaluation"],
		"FOCUS/DAR": ["topic", "data", "action", "response"],
		"SBAR": ["sbar_situation", "sbar_background", "sbar_assessment", "sbar_recommendation"]
	};
	const all_groups = Array.from(new Set([].concat(...Object.values(groups))));

	const setHidden = (fn, hidden) => {
		const f = dlg.get_field(fn);
		if (f) {
			f.df.hidden = hidden ? 1 : 0;
			f.refresh && f.refresh();
		}
	};
	const apply = () => {
		const format = (dlg.get_value("note_format") || "Narrative").trim();
		all_groups.forEach(fn => setHidden(fn, true));
		(groups[format] || []).forEach(fn => setHidden(fn, false));

		if (format === "SBAR") {
			const prefix = (fn, t) => {
				const f = dlg.get_field(fn);
				if (f && !f.get_value()) {
					f.set_value(t);
				}
			};
			prefix("sbar_situation", "**S:** ");
			prefix("sbar_background", "**B:** ");
			prefix("sbar_assessment", "**A:** ");
			prefix("sbar_recommendation", "**R:** ");
		}
		dlg.layout && dlg.layout.refresh_sections && dlg.layout.refresh_sections();
	};

	apply();
	const fmt_field = dlg.get_field("note_format");
	if (fmt_field?.$input) fmt_field.$input.on("change", apply);
	else setTimeout(apply, 0);
};

healthcare.openClinicalNoteDialog = async function ({ encounterDoc, title = "Add Clinical Note", preset = {} } = {}) {
	const d = new frappe.ui.Dialog({
		title: __(title),
		size: "large",
		fields: healthcare.clinical_note_fields(),
		primary_action_label: __("Create"),
		primary_action: async () => {
			const v = d.get_values(); if (!v) return;
			try {
				const new_doc = {
					doctype: "Clinical Note",
					patient: v.patient,
					clinical_note_type: v.clinical_note_type,
					note_format: v.note_format || "Narrative",
					terms_and_conditions: v.terms_and_conditions,
					narrative: v.narrative,
					subjective: v.subjective, objective: v.objective, assessment: v.assessment, plan: v.plan,
					evaluation: v.evaluation, intervention: v.intervention, revision: v.revision,
					pie_problem: v.pie_problem, pie_intervention: v.pie_intervention, pie_evaluation: v.pie_evaluation,
					topic: v.topic, data: v.data, action: v.action, response: v.response,
					sbar_situation: v.sbar_situation, sbar_background: v.sbar_background,
					sbar_assessment: v.sbar_assessment, sbar_recommendation: v.sbar_recommendation,
					reference_doc: v.reference_doc, reference_name: v.reference_name,
				};
				const r = await frappe.db.insert(new_doc);
				frappe.show_alert({ message: __("Clinical Note {0} created", [r.name]), indicator: "green" });
				d.hide();
			} catch (e) {
				console.error(e);
				frappe.msgprint({ title: __("Error"), message: e?.message || e, indicator: "red" });
			}
		}
	});

	const defaults = Object.assign({
		note_format: "Narrative",
		reference_doc: "Patient Encounter",
		reference_name: encounterDoc?.name,
		patient: encounterDoc?.patient,
	}, preset || {});
	for (const [k, v] of Object.entries(defaults)) {
		const f = d.get_field(k); if (f && v != null) f.set_value(v);
	}

	healthcare.apply_note_format(d);
	d.show();
	return d;
};

healthcare.createClinicalNoteViaDialog = (encounterDoc, preset = {}) =>
	healthcare.openClinicalNoteDialog({ encounterDoc, preset });

class ClinicalNoteQuickEntryForm extends frappe.ui.form.QuickEntryForm {
	constructor(doctype, after_insert, init_callback, doc, force) {
		super(doctype, after_insert, init_callback, doc, force);
		this.skip_redirect_on_error = true;
		this.doctype = "Clinical Note";
	}
	get_fields() { return healthcare.clinical_note_fields(); }
	get_title() {
		const dt = this.doctype || "Clinical Note";
		const name = (this.doc && this.doc.name) || this.docname;
		return name ? `${__(dt)}: ${name}` : __(dt);
	}
	async render_dialog() {
		if (!this.meta) {
			await new Promise(res => {
				const m = frappe.get_meta(this.doctype);
				if (m) { this.meta = m; return res(); }
				frappe.model.with_doctype(this.doctype, () => { this.meta = frappe.get_meta(this.doctype); res(); });
			});
		}

		super.render_dialog();

		if (this.dialog) {

			const encounterDoc = this.doc || cur_frm?.doc || {};
			const defaults = Object.assign({
				note_format: "Narrative",
				reference_doc: "Patient Encounter",
				reference_name: encounterDoc?.name,
				patient: encounterDoc?.patient,
			}, frappe.route_options || {});
			Object.keys(defaults).forEach(k => {
				const f = this.dialog.get_field(k);
				if (f && defaults[k] != null) f.set_value(defaults[k]);
			});

			healthcare.apply_note_format(this.dialog);
		}
	}
}

healthcare.editClinicalNoteViaDialog = async function (a, b) {
	// (encounterDoc, note_name) OR (note_name[, encounterDoc])
	let encounterDoc, note_name;
	if (typeof a === "string") {
		note_name = a;
		encounterDoc = b || (cur_frm && cur_frm.doc) || {};
	} else {
		encounterDoc = a || (cur_frm && cur_frm.doc) || {};
		note_name = b;
	}
	if (!note_name) {
		frappe.throw(__("Missing Clinical Note name."));
		return;
	}

	// fetch current note
	const { message: noteDoc } = await frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Clinical Note", name: note_name },
		freeze: true
	});

	const d = new frappe.ui.Dialog({
		title: __("Edit Clinical Note"),
		size: "large",
		fields: healthcare.clinical_note_fields(),
		primary_action_label: __("Update"),
		primary_action: async () => {
			const v = d.get_values(); if (!v) return;
			try {

				const updated = Object.assign({}, noteDoc, {
					patient: v.patient,
					clinical_note_type: v.clinical_note_type,
					note_format: v.note_format || "Narrative",
					terms_and_conditions: v.terms_and_conditions,
					narrative: v.narrative,

					subjective: v.subjective, objective: v.objective,
					assessment: v.assessment, plan: v.plan,

					evaluation: v.evaluation, intervention: v.intervention, revision: v.revision,

					pie_problem: v.pie_problem, pie_intervention: v.pie_intervention, pie_evaluation: v.pie_evaluation,

					topic: v.topic, data: v.data, action: v.action, response: v.response,

					sbar_situation: v.sbar_situation, sbar_background: v.sbar_background,
					sbar_assessment: v.sbar_assessment, sbar_recommendation: v.sbar_recommendation,

					reference_doc: v.reference_doc || noteDoc.reference_doc,
					reference_name: v.reference_name || noteDoc.reference_name
				});

				// save the doc
				await frappe.call({
					method: "frappe.client.save",
					args: { doc: updated },
					freeze: true
				});

				frappe.show_alert({ message: __("Clinical Note {0} updated", [note_name]), indicator: "green" });
				d.hide();
			} catch (e) {
				console.error(e);
				frappe.msgprint({ title: __("Error"), message: e?.message || e, indicator: "red" });
			}
		}
	});

	// prefill values from note
	const initial = {
		patient: noteDoc.patient,
		clinical_note_type: noteDoc.clinical_note_type,
		note_format: noteDoc.note_format || "Narrative",
		terms_and_conditions: noteDoc.terms_and_conditions,
		narrative: noteDoc.narrative,

		subjective: noteDoc.subjective, objective: noteDoc.objective,
		assessment: noteDoc.assessment, plan: noteDoc.plan,

		evaluation: noteDoc.evaluation, intervention: noteDoc.intervention, revision: noteDoc.revision,

		pie_problem: noteDoc.pie_problem, pie_intervention: noteDoc.pie_intervention, pie_evaluation: noteDoc.pie_evaluation,

		topic: noteDoc.topic, data: noteDoc.data, action: noteDoc.action, response: noteDoc.response,

		sbar_situation: noteDoc.sbar_situation, sbar_background: noteDoc.sbar_background,
		sbar_assessment: noteDoc.sbar_assessment, sbar_recommendation: noteDoc.sbar_recommendation,

		reference_doc: noteDoc.reference_doc,
		reference_name: noteDoc.reference_name
	};
	Object.keys(initial).forEach(k => {
		const f = d.get_field(k); if (f && initial[k] != null) f.set_value(initial[k]);
	});

	healthcare.apply_note_format(d);
	d.show();
};


(function registerCNQE() {
	function go() {
		if (!frappe.ui?.form?.QuickEntryForm) return setTimeout(go, 30);
		frappe.ui.form.quick_entry_form_map = frappe.ui.form.quick_entry_form_map || {};
		frappe.ui.form.quick_entry_form_map["Clinical Note"] = ClinicalNoteQuickEntryForm;
	}
	if (frappe.ready) frappe.ready(go); else document.addEventListener("DOMContentLoaded", go);
})();
