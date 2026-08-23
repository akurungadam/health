# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and Contributors
# See license.txt

"""Who may read a DICOMweb worklist.

These endpoints are served by a page renderer, which bypasses the authentication Frappe
applies to its own API layer - so the checks have to be made here, and be seen to be.
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from healthcare.healthcare.api.dicom import dcmweb_renderer


class FakeRequest:
	"""Just the parts of a request the renderer reads."""

	def __init__(self, path, method="GET"):
		self.path = path
		self.method = method
		self.args = {}

	def get_data(self, as_text=False):
		return ""


class DICOMWebAuthTestCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.original = getattr(frappe.local, "request", None)

	def tearDown(self):
		frappe.local.request = self.original
		frappe.set_user("Administrator")
		super().tearDown()

	def render(self, path, user="Guest", headers=None):
		frappe.local.request = FakeRequest(path)
		frappe.set_user(user)
		with patch.object(
			frappe,
			"get_request_header",
			side_effect=lambda name, default="": (headers or {}).get(name, default),
		):
			return dcmweb_renderer.DICOMWebRenderer(path.lstrip("/"), 200).render()


class TestAnUnauthenticatedCallerIsRefused(DICOMWebAuthTestCase):
	"""An absent or unusable key leaves the session as Guest, and must not be served."""

	def test_the_worklist_is_not_served_to_a_guest(self):
		# the worklist carries patient names, procedures and accession numbers
		response = self.render("/dicom-web/workitems")
		self.assertEqual(response.status_code, 401)

	def test_the_refusal_is_a_dicom_error_a_modality_can_read(self):
		response = self.render("/dicom-web/workitems")
		body = json.loads(response.get_data())
		self.assertEqual(body["Status"], dcmweb_renderer.DICOM_STATUS_CODES["NotAuthorized"])
		self.assertTrue(body["ErrorComment"])

	def test_echo_and_conformance_are_refused_too(self):
		# both were commented "no auth"; they call the same check and now honour it
		for path in ("/dicom-web/echo", "/dicom-web/conformance"):
			self.assertEqual(self.render(path).status_code, 401, path)

	def test_a_malformed_authorization_header_does_not_pass(self):
		# "".split(" ") and a single token both unpack badly inside Frappe, which
		# swallows the error - the caller stays Guest and must still be refused
		for header in ({}, {"Authorization": "garbage"}, {"Authorization": "token only-one-part"}):
			self.assertEqual(self.render("/dicom-web/workitems", headers=header).status_code, 401, header)
