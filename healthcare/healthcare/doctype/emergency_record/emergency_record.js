// Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Emergency Record", {
	onload: function(frm) {
        show_clinical_notes(frm);
		show_orders(frm);
	},

	refresh: function(frm) {
		if (!frm.doc.disposition) {
			frm.add_custom_button(__('Schedule Admission'), function() {
				schedule_inpatient(frm);
			});
		}
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

var schedule_inpatient = function(frm) {
	let service_unit_type = "";
	var dialog = new frappe.ui.Dialog({
		title: 'Patient Admission',
		fields: [
			{fieldtype: 'Link', label: 'Medical Department', fieldname: 'medical_department', options: 'Medical Department', reqd: 1},
			{fieldtype: 'Link', label: 'Healthcare Practitioner (Primary)', fieldname: 'primary_practitioner', options: 'Healthcare Practitioner', reqd: 1},
			{fieldtype: 'Link', label: 'Healthcare Practitioner (Secondary)', fieldname: 'secondary_practitioner', options: 'Healthcare Practitioner'},
			{fieldtype: 'Link', label: 'Nursing Checklist Template', fieldname: 'admission_nursing_checklist_template', options: 'Nursing Checklist Template'},
			{fieldtype: 'Column Break'},
			{fieldtype: 'Date', label: 'Admission Ordered For', fieldname: 'admission_ordered_for', default: 'Today'},
			{fieldtype: 'Link', label: 'Service Unit Type', fieldname: 'service_unit_type', options: 'Healthcare Service Unit Type'},
			{fieldtype: 'Int', label: 'Expected Length of Stay', fieldname: 'expected_length_of_stay'},
			{fieldtype: 'Link', label: 'Treatment Plan Template', fieldname: 'treatment_plan_template', options: 'Treatment Plan Template'},
			{fieldtype: 'Section Break'},
			{fieldtype: 'Long Text', label: 'Admission Instructions', fieldname: 'admission_instruction'}
		],
		primary_action_label: __('Order Admission'),
		primary_action : function() {
			var args = {
				patient: frm.doc.patient,
				emergency_record: frm.doc.name,
				referring_practitioner: frm.doc.practitioner,
				company: frm.doc.company,
				medical_department: dialog.get_value('medical_department'),
				primary_practitioner: dialog.get_value('primary_practitioner'),
				secondary_practitioner: dialog.get_value('secondary_practitioner'),
				admission_ordered_for: dialog.get_value('admission_ordered_for'),
				admission_service_unit_type: dialog.get_value('service_unit_type'),
				treatment_plan_template: dialog.get_value('treatment_plan_template'),
				expected_length_of_stay: dialog.get_value('expected_length_of_stay'),
				admission_instruction: dialog.get_value('admission_instruction'),
				admission_nursing_checklist_template: dialog.get_value('admission_nursing_checklist_template'),
			}

			frappe.call({
				doc: frm.doc,
				method: 'schedule_inpatient',
				args: {
					admission_order: args
				},
				callback: function(data) {
					if (!data.exc) {
						frm.reload_doc();
					}
				},
				freeze: true,
				freeze_message: __('Scheduling Patient Admission')
			});
			frm.refresh_fields();
			dialog.hide();
		}
	});

	dialog.set_values({
		'medical_department': frm.doc.medical_department,
		'primary_practitioner': frm.doc.practitioner,
	});

	dialog.fields_dict['service_unit_type'].get_query = function() {
		return {
			filters: {
				'inpatient_occupancy': 1,
				'allow_appointments': 0
			}
		};
	};

	dialog.fields_dict["service_unit_type"].df.onchange = () => {
		if (dialog.get_value("service_unit_type") && dialog.get_value("service_unit_type") != service_unit_type) {
			service_unit_type = dialog.get_value("service_unit_type");
			frappe.db.get_value("Healthcare Service Unit Type", {name: dialog.get_value("service_unit_type")}, ["is_billable", "item"])
			.then(r => {
				if (r.message.is_billable && !r.message.item) {
					frappe.msgprint({
						message: __("Selected service unit type doesn't have any item linked"),
						title: __("Warning"),
						indicator: "orange",
					});
				}
			})
		}
	};

	dialog.show();
	dialog.$wrapper.find('.modal-dialog').css('width', '800px');
};
