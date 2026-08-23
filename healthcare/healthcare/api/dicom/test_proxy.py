# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and Contributors
# See license.txt

"""The DICOMweb proxy: what it will fetch, and for whom.

It exists so the browser never holds PACS credentials. That only holds if it refuses to
fetch arbitrary URLs and refuses studies the caller may not read.
"""

import typing

import frappe
from frappe.tests import IntegrationTestCase

from healthcare.healthcare.api.dicom import proxy


class FakeSettings(dict):
	"""Healthcare Settings with just the PACS fields, so no site config is needed."""

	DEFAULTS: typing.ClassVar[dict] = {
		"pacs_base_url": "https://pacs.invalid",
		"qido_rs_url": "/dicom-web/instances?SeriesInstanceUID={series_uid}",
		"wado_rs_url": "/dicom-web/studies/{study_uid}/series/{series_uid}/instances/{sop_instance_uid}/frames/1/rendered",
		"pacs_username": "pacsuser",
	}

	def __init__(self, **overrides):
		super().__init__({**self.DEFAULTS, **overrides})

	def get(self, key, default=None):
		return super().get(key, default)

	def __getattr__(self, key):
		return self[key]


class TestTheUrlIsBuiltFromConfiguration(IntegrationTestCase):
	"""The caller picks an operation; the administrator's template decides the shape."""

	def test_a_qido_url_uses_the_configured_template(self):
		url = proxy._pacs_url(FakeSettings(), proxy.QIDO, "1.2.3", "4.5.6", None)
		self.assertEqual(url, "https://pacs.invalid/dicom-web/instances?SeriesInstanceUID=4.5.6")

	def test_a_wado_url_carries_every_identifier(self):
		url = proxy._pacs_url(FakeSettings(), proxy.WADO, "1.2.3", "4.5.6", "7.8.9")
		self.assertIn("/studies/1.2.3/series/4.5.6/instances/7.8.9/", url)
		self.assertTrue(url.startswith("https://pacs.invalid/"))

	def test_an_unknown_operation_is_refused(self):
		# a proxy that forwards whatever it is handed is a route into the internal network
		with self.assertRaises(frappe.ValidationError):
			proxy._pacs_url(FakeSettings(), "anything-else", "1.2.3", "4.5.6", None)

	def test_a_caller_cannot_smuggle_a_host_through_an_identifier(self):
		# identifiers only ever fill placeholders inside the configured template
		url = proxy._pacs_url(FakeSettings(), proxy.QIDO, "1.2.3", "https://evil.invalid/x", None)
		self.assertTrue(url.startswith("https://pacs.invalid/"))

	def test_an_unconfigured_pacs_is_reported_rather_than_guessed(self):
		with self.assertRaises(frappe.ValidationError):
			proxy._pacs_url(FakeSettings(qido_rs_url=""), proxy.QIDO, "1.2.3", "4.5.6", None)


class TestOnlyReadableStudiesAreServed(IntegrationTestCase):
	"""The study id travels in the URL, so it is checked on every request."""

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_a_study_the_user_may_not_read_is_refused(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			proxy._readable_study("any-study")

	def test_the_refusal_happens_before_the_pacs_is_contacted(self):
		# the permission check is the first thing fetch() does that can fail
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			proxy.fetch(proxy.QIDO, "any-study", "4.5.6")
