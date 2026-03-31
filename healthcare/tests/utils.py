import frappe

# from frappe.tests.utils import load_test_records_for
from erpnext.tests.utils import ERPNextTestSuite


class BootStrapTestData:
	def __init__(self):
		self.make_master_data()

	def make_master_data(self):
		self.make_company()
		self.make_medical_department()
		self.make_practitioner()
		self.make_patient()
		self.make_service_items()
		self.make_appointment_types()
		self.make_clinical_procedure_template()

	def make_clinical_procedure_template(self):
		records = [
			{
				"doctype": "Clinical Procedure Template",
				"template": "_Test Procedure - Knee Surgery and Rehab",
				"item_code": "_Test Procedure - Knee Surgery and Rehab",
				"item_group": "Services",
				"description": "Knee Surgery and Rehab",
				"is_billable": 1,
				"rate": 50000,
			},
		]
		self.make_records(["template", "item_code"], records)

	def make_appointment_types(self):
		records = [
			{
				"doctype": "Appointment Type",
				"appointment_type": "_Test Appointment Type",
				"allow_booking_for": "Practitioner",
				"medical_department": "_Test Medical Department",
				"default_duration": 20,
			},
			{
				"doctype": "Appointment Type",
				"appointment_type": "_Test Appointment Type for Department",
				"allow_booking_for": "Department",
				"medical_department": "_Test Medical Department",
				"default_duration": 20,
			},
			{
				"doctype": "Appointment Type",
				"appointment_type": "_Test Appointment Type with Items",
				"allow_booking_for": "Practitioner",
				"medical_department": "_Test Medical Department",
				"default_duration": 20,
				"items": [
					{
						"dt": "Medical Department",
						"dn": "_Test Medical Department",
						"op_consulting_charge_item": "HLC-SI-001",
						"op_consulting_charge": 200,
					},
				],
			},
		]
		self.make_records(["appointment_type"], records)

	def make_service_items(self):
		records = [
			{
				"doctype": "Item",
				"item_code": "HLC-SI-001",
				"item_name": "OP Consulting Charges",
				"item_group": "Services",
				"is_stock_item": 0,
				"stock_uom": "Nos",
			},
			{
				"doctype": "Item",
				"item_code": "HLC-SI-002",
				"item_name": "IP Consulting Charges",
				"item_group": "Services",
				"is_stock_item": 0,
				"stock_uom": "Nos",
			},
		]
		self.make_records(["item_code"], records)

	def make_patient(self):
		records = [
			{
				"doctype": "Patient",
				"first_name": "_Test Patient",
				"sex": "Male",
			},
		]
		self.make_records(["first_name"], records)

	def make_practitioner(self):
		records = [
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "_Test Healthcare Practitioner",
				"gender": "Female",
				"department": "_Test Medical Department",
				"op_consulting_charge": 500,
				"inpatient_visit_charge": 500,
			},
		]
		self.make_records(["first_name"], records)

	def make_medical_department(self):
		records = [
			{
				"doctype": "Medical Department",
				"department": "_Test Medical Department",
			},
			{
				"doctype": "Medical Department",
				"department": "_Test Medical Department 0",
			},
			{
				"doctype": "Medical Department",
				"department": "_Test Medical Department 1",
			},
			{
				"doctype": "Medical Department",
				"department": "_Test Medical Department 2",
			},
		]
		self.make_records(["department"], records)

	def make_company(self):
		records = [
			{
				"abbr": "_TC",
				"company_name": "_Test Company",
				"country": "India",
				"default_currency": "INR",
				"doctype": "Company",
				"chart_of_accounts": "Standard",
			},
		]
		self.make_records(["company_name"], records)

	def make_records(self, key, records):
		doctype = records[0].get("doctype")

		def get_filters(record):
			filters = {}
			for x in key:
				filters[x] = record.get(x)
			return filters

		for x in records:
			filters = get_filters(x)
			if not frappe.db.exists(doctype, filters):
				frappe.get_doc(x).insert()


BootStrapTestData()


class HealthcareTestSuite(ERPNextTestSuite):
	"""Class for creating Healthcare test records"""

	pass
