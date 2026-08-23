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


class TestRouting(IntegrationTestCase):
	"""Which operation a path and method select, without running any of them."""

	def test_every_workitem_action_is_reachable(self):
		expected = {
			("POST", "claim"): "UPS Claim",
			("POST", "cancelrequest"): "UPS Cancel",
			("POST", "workitemevent"): "UPS WorkitemEvent",
			("PUT", ""): "UPS Update",
		}
		for key, message_type in expected.items():
			self.assertEqual(dcmweb_renderer.WORKITEM_OPERATIONS[key].message_type, message_type, key)

	def test_a_method_the_action_does_not_support_is_not_routed(self):
		# a GET on /claim used to fall through the if/elif and answer "UPS task not found"
		self.assertIsNone(dcmweb_renderer.WORKITEM_OPERATIONS.get(("GET", "claim")))
		self.assertIsNone(dcmweb_renderer.WORKITEM_OPERATIONS.get(("DELETE", "")))

	def test_the_capability_paths_are_routed(self):
		self.assertEqual(set(dcmweb_renderer.CAPABILITIES), {"/dicom-web/echo", "/dicom-web/conformance"})

	def test_operations_that_carry_no_request_payload_say_so(self):
		# cancel and the capability endpoints logged request_payload=None before
		self.assertFalse(dcmweb_renderer.WORKITEM_OPERATIONS[("POST", "cancelrequest")].logs_request)
		for operation in dcmweb_renderer.CAPABILITIES.values():
			self.assertFalse(operation.logs_request)

	def test_the_worklist_logs_its_filters(self):
		self.assertTrue(dcmweb_renderer.WORKLIST.logs_request)


class TestMalformedBodies(DICOMWebAuthTestCase):
	"""A body that is not JSON is reported as such, not as a later failure."""

	def test_an_unparsable_body_is_a_bad_request(self):
		class BadBody(FakeRequest):
			def get_data(self, as_text=False):
				return "{not json"

		frappe.local.request = BadBody("/dicom-web/workitems", method="POST")
		frappe.set_user("Administrator")
		with patch.object(frappe, "get_request_header", return_value=""):
			response = dcmweb_renderer.DICOMWebRenderer("dicom-web/workitems", 200).render()
		self.assertEqual(response.status_code, 400)
		self.assertIn("Invalid JSON", json.loads(response.get_data())["ErrorComment"])
