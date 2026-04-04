import frappe

from erpnext.tests.utils import ERPNextTestSuite


class BootStrapTestData:
	def __init__(self):
		self.make_master_data()

	def make_master_data(self):
		self.make_company()
		self.make_service_items()
		self.make_diagnoses()
		self.make_medical_departments()
		self.make_practitioners()
		self.make_patients()
		self.make_appointment_types()
		self.make_clinical_procedure_templates()
		self.make_service_unit_types()
		self.make_service_units()
		self.make_users()
		self.make_lab_test_samples()
		self.make_lab_test_templates()
		self.make_observation_templates()

	def make_observation_templates(self):
		records = [
			{
				"doctype": "Observation Template",
				"observation": "_Test Observation with Sample",
				"abbr": "OWS",
				"item_code": "_Test Observation with Sample",
				"observation_category": "Laboratory",
				"permitted_data_type": "Quantity",
				"permitted_unit": "mg / dl",
				"item_group": "Services",
				"sample_collection_required": 1,
				"is_billable": 1,
				"rate": 300,
			},
			{
				"doctype": "Observation Template",
				"observation": "_Test Observation without Sample",
				"abbr": "OWOS",
				"item_code": "_Test Observation without Sample",
				"observation_category": "Laboratory",
				"permitted_data_type": "Quantity",
				"permitted_unit": "mg / dl",
				"item_group": "Services",
				"sample_collection_required": 0,
				"is_billable": 1,
				"rate": 300,
			},
			{
				"doctype": "Observation Template",
				"observation": "_Test Observation Grouped",
				"abbr": "OG",
				"item_code": "_Test Observation Grouped",
				"has_component": 1,
				"observation_category": "Laboratory",
				"permitted_data_type": "Quantity",
				"permitted_unit": "mg / dl",
				"item_group": "Services",
				"sample_collection_required": 1,
				"is_billable": 1,
				"rate": 300,
				"observation_component": [  # FIXME: observation_components
					{"observation_template": "_Test Observation without Sample", "abbr": "OWOS"}
				],
			},
		]
		self.make_records(["observation"], records)

	def make_lab_test_templates(self):
		records = [
			{
				"doctype": "Lab Test Template",
				"lab_test_name": "_Test Lab Test - with Sample",
				"lab_test_template_type": "Descriptive",
				"lab_test_description": "Insulin Resistance",
				"lab_test_code": "_Test Lab Test - with Sample",
				"lab_test_group": "Services",
				"department": "_Test Medical Department",
				"is_billable": 1,
				"lab_test_rate": 2000,
				"sample": "_Test Sample - Blood Sample",
				"sample_qty": "5.0",
				"descriptive_test_templates": [],
			},
			{
				"doctype": "Lab Test Template",
				"lab_test_name": "_Test Lab Test - without Sample",
				"lab_test_template_type": "Descriptive",
				"lab_test_description": "Insulin Resistance",
				"lab_test_code": "_Test Lab Test - without Sample",
				"lab_test_group": "Services",
				"department": "_Test Medical Department",
				"is_billable": 1,
				"lab_test_rate": 2000,
				"descriptive_test_templates": [],
			},
			{
				"doctype": "Lab Test Template",
				"lab_test_name": "_Test Lab Test - Sensitivity",
				"lab_test_template_type": "Descriptive",
				"lab_test_description": "Insulin Resistance",
				"lab_test_code": "_Test Lab Test - Sensitivity",
				"lab_test_group": "Services",
				"department": "_Test Medical Department",
				"is_billable": 1,
				"lab_test_rate": 2000,
				"sensitivity": 1,
				"descriptive_test_templates": [],
			},
		]
		for r in records:
			for entry in ["FBS", "Insulin", "IR"]:
				r["descriptive_test_templates"].append(
					{"particulars": entry, "allow_blank": 1 if entry == "IR" else 0},
				)

		self.make_records(["lab_test_name", "lab_test_code"], records)

	def make_lab_test_samples(self):
		records = [
			{
				"doctype": "Lab Test Sample",
				"sample": "_Test Sample - Blood Sample",
				"sample_uom": "U/ml",
			},
			{
				"doctype": "Lab Test Sample",
				"sample": "_Test Sample - Urine",
				"sample_uom": "U/ml",
			},
		]
		self.make_records(["sample"], records)

	def make_users(self):
		records = [
			{
				"doctype": "User",
				"email": "test_user@marleyhealth.io",
				"first_name": "test_user",
				"password": "password",
			},
			{
				"doctype": "User",
				"email": "test_user_0@marleyhealth.io",
				"first_name": "test_user_0",
				"password": "password",
			},
		]
		self.make_records(["email"], records)

	def make_service_units(self):
		records = [
			{
				"doctype": "Healthcare Service Unit",
				"healthcare_service_unit_name": "_Test HSU - Appointments",
				"service_unit_type": "_Test Service Unit Type - Appointments",
				"company": "_Test Company",
				"allow_appointments": 1,
				"overlap_appointments": 0,
			},
			{
				"doctype": "Healthcare Service Unit",
				"healthcare_service_unit_name": "_Test HSU - Overlapping Appointments",
				"service_unit_type": "_Test Service Unit Type - Overlapping Appointments",
				"company": "_Test Company",
				"allow_appointments": 1,
				"overlap_appointments": 1,
				"service_unit_capacity": 10,
			},
			{
				"doctype": "Healthcare Service Unit",
				"healthcare_service_unit_name": "_Test HSU - Occupancy",
				"service_unit_type": "_Test Service Unit Type - Occupancy",
				"company": "_Test Company",
				"inpatient_occupancy": 1,
			},
		]
		self.make_records(["healthcare_service_unit_name"], records)

	def make_service_unit_types(self):
		records = [
			{
				"doctype": "Healthcare Service Unit Type",
				"service_unit_type": "_Test Service Unit Type - Appointments",
				"allow_appointments": 1,
				"overlap_appointments": 0,
			},
			{
				"doctype": "Healthcare Service Unit Type",
				"service_unit_type": "_Test Service Unit Type - Overlapping Appointments",
				"allow_appointments": 1,
				"overlap_appointments": 1,
			},
			{
				"doctype": "Healthcare Service Unit Type",
				"service_unit_type": "_Test Service Unit Type - Occupancy",
				"inpatient_occupancy": 1,
			},
		]
		self.make_records(["service_unit_type"], records)

	def make_clinical_procedure_templates(self):
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
			{
				"doctype": "Clinical Procedure Template",
				"template": "_Test Procedure - Wound Inspection and Cleaning",
				"item_code": "_Test Procedure - Wound Inspection and Cleaning",
				"item_group": "Services",
				"description": "Wound Inspection and Cleaning",
				"is_billable": 1,
				"rate": 1000,
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
						"inpatient_visit_charge_item": "HLC-SI-002",
						"ip_consulting_charge": 200,
					},
				],
			},
		]
		self.make_records(["appointment_type"], records)

	def make_patients(self):
		records = [
			{
				"doctype": "Patient",
				"first_name": "_Test Patient",
				"sex": "Female",
			},
			{
				"doctype": "Patient",
				"first_name": "_Test Patient 0",
				"sex": "Male",
			},
			{
				"doctype": "Patient",
				"first_name": "_Test Patient 1",
				"sex": "Male",
			},
		]
		self.make_records(["first_name"], records)

	def make_practitioners(self):
		# TODO: fix practitioner naming
		records = [
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "_Test",
				"last_name": "Healthcare Practitioner 0",
				"gender": "Female",
				"department": "_Test Medical Department",
				"op_consulting_charge_item": "HLC-SI-001",
				"op_consulting_charge": 500,
				"inpatient_visit_charge_item": "HLC-SI-002",
				"inpatient_visit_charge": 500,
			},
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "_Test",
				"last_name": "Healthcare Practitioner 1",
				"gender": "Male",
				"department": "_Test Medical Department 0",
				"op_consulting_charge_item": "HLC-SI-001",
				"op_consulting_charge": 500,
				"inpatient_visit_charge_item": "HLC-SI-002",
				"inpatient_visit_charge": 500,
			},
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "_Test",
				"last_name": "Healthcare Practitioner 2",
				"gender": "Male",
				"department": "_Test Medical Department 1",
				"op_consulting_charge_item": "HLC-SI-001",
				"op_consulting_charge": 300,
				"inpatient_visit_charge_item": "HLC-SI-002",
				"inpatient_visit_charge": 300,
			},
		]
		self.make_records(["last_name"], records)

	def make_medical_departments(self):
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

	def make_diagnoses(self):
		records = [
			{
				"doctype": "Diagnosis",
				"diagnosis": "Fever",
			},
			{
				"doctype": "Diagnosis",
				"diagnosis": "Heart Attack",
			},
		]
		self.make_records(["diagnosis"], records)

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
