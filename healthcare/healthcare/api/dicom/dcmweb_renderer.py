# Copyright (c) 2025, earthians and contributors
# For license information, please see license.txt

import json
from collections.abc import Callable
from dataclasses import dataclass

from werkzeug.wrappers import Response

import frappe
from frappe import _
from frappe.auth import validate_auth_via_api_keys
from frappe.website.page_renderers.base_renderer import BaseRenderer

from healthcare.healthcare.api.dicom.actions import (
	cancel_ups,
	get_ups_tasks,
	handle_workitem_event,
	process_ups_claim,
	update_from_modality,
)
from healthcare.healthcare.api.dicom.capabilities import (
	get_conformance_statement,
	get_dicomweb_verification,
)
from healthcare.healthcare.doctype.modality_message_log.modality_message_log import (
	log_modality_message,
)

DICOM_STATUS_CODES = {
	"Success": "0000H",
	"ProcessingFailure": "0110H",
	"InvalidArgumentValue": "0106H",
	"InvalidAttributeValue": "0107H",
	"MissingAttribute": "0120H",
	"NoSuchObjectInstance": "0112H",
	"UPSAlreadyClaimed": "C301H",
	"UPSNotYetClaimed": "C302H",
	"UPSAlreadyInProgress": "C303H",
	"UPSAlreadyCompleted": "C304H",
	"NotAuthorized": "0124H",
}


WORKITEMS_PATH = "/dicom-web/workitems"
SUCCESS_STATUS = "0000H"
FAILURE_STATUS = "0110H"


@dataclass(frozen=True)
class Operation:
	"""One DICOMweb operation: what to run, and what to call it in the modality log.

	``call`` takes the renderer, the request payload and the workitem reference, because
	that is the widest signature any of them needs; the narrower ones ignore what they
	do not use.
	"""

	call: Callable
	message_type: str
	success: str
	failure: str
	logs_request: bool = True


WORKLIST = Operation(
	call=lambda _renderer, payload, _reference: get_ups_tasks(filters=payload),
	message_type="UPS RS",
	success="UPS RS served",
	failure="UPS-RS failed",
)

# (method, trailing action) -> what it does. A PUT carries no action segment.
WORKITEM_OPERATIONS = {
	("POST", "claim"): Operation(
		call=lambda renderer, payload, reference: process_ups_claim(reference, payload, renderer.ae_title()),
		message_type="UPS Claim",
		success="Claim accepted",
		failure="Claim failed",
	),
	("POST", "cancelrequest"): Operation(
		call=lambda renderer, payload, reference: cancel_ups(reference, payload, renderer.ae_title()),
		message_type="UPS Cancel",
		success="Cancelled",
		failure="Cancel failed",
		logs_request=False,
	),
	("POST", "workitemevent"): Operation(
		call=lambda renderer, payload, reference: handle_workitem_event(
			reference, payload, renderer.ae_title()
		),
		message_type="UPS WorkitemEvent",
		success="Workitem updated",
		failure="Workitem event failed",
	),
	("PUT", ""): Operation(
		call=lambda renderer, payload, reference: update_from_modality(
			reference, payload, renderer.ae_title()
		),
		message_type="UPS Update",
		success="Updated",
		failure="Update failed",
	),
}

CAPABILITIES = {
	"/dicom-web/echo": Operation(
		call=lambda _renderer, _payload, _reference: get_dicomweb_verification(),
		message_type="Verification",
		success="DICOMWeb Verification completed successfully",
		failure="Verification failed",
		logs_request=False,
	),
	"/dicom-web/conformance": Operation(
		call=lambda _renderer, _payload, _reference: get_conformance_statement(),
		message_type="Conformance",
		success="DICOM Conformance served successfully",
		failure="Conformance failed",
		logs_request=False,
	),
}


class DICOMWebRenderer(BaseRenderer):
	def __init__(self, path, http_status_code=None):
		super().__init__(path, http_status_code)

	def can_render(self):
		return self.path.startswith("dicom-web")

	def render(self):
		"""Dispatch a DICOMweb request, refusing it cleanly when it is not authenticated.

		An AuthenticationError raised in a handler would otherwise leave this renderer as
		a traceback rather than a response a modality can read.
		"""
		try:
			return self.dispatch()
		except frappe.AuthenticationError as error:
			return self.respond(401, self.dicom_error("NotAuthorized", str(error)))

	def dispatch(self):
		path = frappe.request.path.rstrip("/")
		method = frappe.request.method

		if path == WORKITEMS_PATH:
			return self.serve_worklist(method)
		if path.startswith(f"{WORKITEMS_PATH}/"):
			return self.serve_workitem(method, path)
		if path in CAPABILITIES:
			return self.serve(CAPABILITIES[path])
		return self.respond(404, self.dicom_error("NoSuchObjectInstance", "UPS task not found"))

	def serve_worklist(self, method):
		"""The worklist itself, whose filters arrive in the query string or a JSON body."""
		if method == "GET":
			return self.serve(WORKLIST, payload=dict(frappe.request.args or {}))
		if method == "POST":
			try:
				filters = self.request_body()
			except ValueError:
				return self.respond(400, self.dicom_error("InvalidAttributeValue", "Invalid JSON body"))
			return self.serve(WORKLIST, payload=filters)
		return self.respond(404, self.dicom_error("NoSuchObjectInstance", "UPS task not found"))

	def serve_workitem(self, method, path):
		"""One workitem, addressed as /workitems/<id>/<action> - or PUT with no action."""
		parts = path[len(WORKITEMS_PATH) + 1 :].split("/")
		workitem_id, action = parts[0], (parts[1] if len(parts) > 1 else "")
		operation = WORKITEM_OPERATIONS.get((method, action))
		if not operation:
			return self.respond(404, self.dicom_error("NoSuchObjectInstance", "UPS task not found"))
		try:
			body = self.request_body()
		except ValueError:
			return self.respond(400, self.dicom_error("InvalidAttributeValue", "Invalid JSON body"))
		return self.serve(operation, payload=body, reference=workitem_id)

	def serve(self, operation, payload=None, reference=None):
		"""Run one operation, log how it went, and answer.

		Every DICOMweb operation has the same shape - authenticate, act, log, respond - so
		it lives here once. What differs between them is only what to call and what to
		call it in the log, which is what an Operation carries.
		"""
		self.authenticate_request()
		ae_title = self.ae_title()
		try:
			result = operation.call(self, payload, reference)
		except Exception as error:
			self.log(operation, ae_title, payload, reference, status_text=str(error))
			return self.respond(400, self.dicom_error("ProcessingFailure", f"{operation.failure}: {error}"))
		self.log(operation, ae_title, payload, reference, result=result)
		return self.respond(200, result)

	def log(self, operation, ae_title, payload, reference, result=None, status_text=None):
		log_modality_message(
			ae_title=ae_title,
			message_type=operation.message_type,
			request_payload=payload if operation.logs_request else None,
			response_payload=result,
			status_code=SUCCESS_STATUS if result is not None else FAILURE_STATUS,
			status_text=status_text or operation.success,
			**({"reference": reference} if reference else {}),
		)

	def request_body(self):
		"""The JSON body, or an empty one. Raises ValueError when it is not JSON.

		Parsed before the operation runs rather than inside its try, so a malformed body
		is reported as such instead of surfacing later as an unbound name.
		"""
		return json.loads(frappe.request.get_data(as_text=True) or "{}")

	def respond(self, status, data, content_type="application/json"):
		return Response(
			response=json.dumps(data, indent=2),
			status=status,
			content_type=content_type,
		)

	def dicom_error(self, code_key, message):
		return {"Status": DICOM_STATUS_CODES.get(code_key, "0110H"), "ErrorComment": message}

	def ae_title(self):
		return frappe.get_request_header("X-AE-TITLE") or "Unknown"

	def authenticate_request(self):
		"""Establish who is calling, and refuse the request if nobody was.

		``validate_auth_via_api_keys`` sets the session user when the key is good and
		returns silently when it is not - an absent header unpacks to a one-element list,
		raises ValueError inside it, and is swallowed. So on its own it authenticates
		nothing: the caller stays Guest and the handler serves the worklist anyway.

		Frappe guards this on the next line of its own ``validate_auth``; page renderers
		bypass that path entirely, so the same check has to be made here.
		"""
		auth_header = frappe.get_request_header("Authorization", "").split(" ")
		validate_auth_via_api_keys(auth_header)
		if frappe.session.user in ("", "Guest"):
			raise frappe.AuthenticationError(_("A valid API key is required for DICOMweb."))
