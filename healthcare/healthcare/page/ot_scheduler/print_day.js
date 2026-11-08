// The day's schedule sheet (ot_booking/day_sheet.py), theatre by theatre or practitioner by
// practitioner, for what the board shows and its filters leave clear, opened in a new tab for
// the browser to print or save.
import { get, showError } from "./api.js";

export async function printDay(params) {
	// opened before the request, while the click still allows a new tab
	const page = window.open("", "_blank");
	if (!page) return;
	try {
		page.document.write(await get("day_sheet.get_day_sheet", params));
		page.document.close();
		page.focus();
		page.print();
	} catch (error) {
		page.close();
		showError(error);
	}
}
