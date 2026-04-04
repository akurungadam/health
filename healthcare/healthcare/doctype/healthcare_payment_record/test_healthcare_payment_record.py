# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and Contributors
# See license.txt

# import frappe
from healthcare.tests.utils import HealthcareTestSuite

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestHealthcarePaymentRecord(HealthcareTestSuite):
	"""
	Integration tests for HealthcarePaymentRecord.
	Use this class for testing interactions between multiple components.
	"""

	pass
