import frappe

from erpnext.tests.utils import ERPNextTestSuite


class BootStrapTestData:
	def __init__(self):
		self.make_master_data()

	def make_master_data(self):
		self.make_company()
		self.make_medical_department()

	def make_medical_department(self):
		records = [
			{
				"doctype": "Medical Department",
				"department": "_Test Medical Department",
			}
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
			}
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
				print("H:", x)
				frappe.get_doc(x).insert()


BootStrapTestData()


class HealthcareTestSuite(ERPNextTestSuite):
	"""Class for creating Healthcare test records"""

	pass
