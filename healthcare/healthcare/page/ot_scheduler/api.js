// Calls to the OT Booking API. A read is a GET; a change is a POST with desk's CSRF token.
import { frappeRequest, toast } from "frappe-ui";

const API = "healthcare.healthcare.doctype.ot_booking";

export function get(method, params = {}) {
	return frappeRequest({ url: `${API}.${method}`, params, method: "GET" });
}

export function post(method, params) {
	const headers = { "X-Frappe-CSRF-Token": window.frappe?.csrf_token };
	return frappeRequest({ url: `${API}.${method}`, params, method: "POST", headers });
}

// The first server message is the toast; any others go beneath it
export function showError(error) {
	const [first, ...rest] = error?.messages?.length
		? error.messages
		: [error?.message || String(error)];
	toast.error(first, { description: rest.join(" ") || undefined });
}
