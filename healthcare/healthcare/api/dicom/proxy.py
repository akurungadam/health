# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and Contributors
# For license information, please see license.txt

"""Serve DICOMweb to the viewer without handing the browser PACS credentials.

The viewer needs QIDO and WADO. Pointing it straight at the PACS means the browser must
hold a username and password, and the only way to get them there is through the page -
where they end up in history, access logs and Referer headers.

So the browser talks to this instead. It is already authenticated as a Frappe user, the
PACS credentials never leave the server, and each request is checked against the Imaging
Study it claims to be for. The PACS itself need not be reachable from the internet at all.
"""

import requests

import frappe
from frappe import _
from frappe.utils.password import get_decrypted_password

STUDY_DOCTYPE = "Imaging Study"
TIMEOUT_SECONDS = 30

# What the viewer is allowed to ask the PACS for, and the Healthcare Settings field
# holding each template. Anything outside this is refused: a proxy that forwards an
# arbitrary URL is a way into whatever else the server can reach.
QIDO = "qido"
WADO = "wado"
TEMPLATES = {QIDO: "qido_rs_url", WADO: "wado_rs_url"}
CONTENT_TYPES = {QIDO: "application/dicom+json", WADO: "image/jpeg"}


@frappe.whitelist()
def fetch(operation: str, study: str, series_uid: str, sop_instance_uid: str | None = None):
	"""Fetch one QIDO or WADO resource for a study this user may read."""
	# permission first: an unauthorised caller should learn nothing, not even whether a
	# PACS is configured
	imaging_study = _readable_study(study)
	settings = _pacs_settings()
	url = _pacs_url(settings, operation, imaging_study.study_instance_uid, series_uid, sop_instance_uid)
	return _forward(url, operation, settings)


def _readable_study(study: str):
	"""The Imaging Study, if this user is allowed to read it.

	Checked per request rather than once at page load: the study uid travels in the URL,
	and without this anyone signed in could read any study by changing it.
	"""
	if not frappe.has_permission(STUDY_DOCTYPE, "read"):
		raise frappe.PermissionError(_("Not permitted to view imaging studies."))
	imaging_study = frappe.get_cached_doc(STUDY_DOCTYPE, study)
	imaging_study.check_permission("read")
	return imaging_study


def _pacs_settings():
	settings = frappe.get_cached_doc("Healthcare Settings")
	if not settings.get("pacs_base_url"):
		frappe.throw(_("No PACS base URL is configured."), title=_("PACS Not Configured"))
	return settings


def _pacs_url(settings, operation: str, study_uid: str, series_uid: str, sop_instance_uid: str | None) -> str:
	"""Build the PACS URL from the configured template - never from the caller.

	The caller chooses an operation and supplies identifiers; the shape of the request is
	the administrator's, so a caller cannot point this at anything else.
	"""
	template_field = TEMPLATES.get(operation)
	if not template_field:
		frappe.throw(_("Unknown DICOMweb operation {0}.").format(operation), title=_("Not Allowed"))
	template = (settings.get(template_field) or "").lstrip("/")
	if not template:
		frappe.throw(_("No {0} URL is configured.").format(operation.upper()), title=_("PACS Not Configured"))
	base = settings.pacs_base_url.rstrip("/")
	path = template.format(
		study_uid=study_uid, series_uid=series_uid, sop_instance_uid=sop_instance_uid or ""
	)
	return f"{base}/{path}"


def _forward(url: str, operation: str, settings):
	"""Fetch from the PACS with the server's credentials and hand the bytes back."""
	auth = (
		settings.get("pacs_username"),
		get_decrypted_password("Healthcare Settings", "Healthcare Settings", fieldname="pacs_password"),
	)
	accept = CONTENT_TYPES[operation]
	try:
		response = requests.get(url, headers={"Accept": accept}, auth=auth, timeout=TIMEOUT_SECONDS)
		response.raise_for_status()
	except Exception as error:
		# the PACS URL and credentials stay in the log, not in the reply
		frappe.log_error(f"{error!s}\n{url}", "DICOMweb proxy failed")
		frappe.throw(_("The imaging server did not answer."), title=_("PACS Unavailable"))
	_respond_with(response, accept)


def _respond_with(response, accept: str) -> None:
	"""Return the PACS body verbatim, as itself rather than wrapped in a Frappe response."""
	frappe.local.response["type"] = "binary"
	frappe.local.response["filename"] = ""
	frappe.local.response["filecontent"] = response.content
	frappe.local.response["content_type"] = response.headers.get("Content-Type", accept)
