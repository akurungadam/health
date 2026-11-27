import frappe


def get_context(context):
	context.read_only = 1


def get_list_context(context):
	context.row_template = "erpnext/templates/includes/healthcare/appointment_row_template.html"
	context.get_list = get_appointment_list


def get_appointment_list(doctype, txt, filters, limit_start, limit_page_length=20, order_by="modified desc"):
	patient = get_patient()
	if not patient:
		return []
	return frappe.get_all(
		"Patient Appointment",
		filters={"patient": patient, "status": ["in", ["Open", "Scheduled"]]},
		fields=["*"],
		order_by="appointment_date",
	)


def get_patient():
	return frappe.get_value("Patient", {"email": frappe.session.user}, "name")


def has_website_permission(doc, ptype, user, verbose=False):
	if doc.patient == get_patient():
		return True
	else:
		return False
