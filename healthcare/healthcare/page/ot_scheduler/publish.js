// Publishing the day shown on the board: every Tentative case in its company and department
// becomes Scheduled. It commits the day's list, so desk's own confirm asks first. A case that
// fails its checks stays Tentative and is reported on its own.
import { post, showError, toastError, toastSuccess } from "./api.js";
import { playDropSound } from "./sounds.js";

export function confirmPublish({
	count,
	day,
	company,
	department,
	filters,
	host,
	reload,
}) {
	const date = host.format?.(day, { fieldtype: "Date" }) ?? day;
	const shown = company + (department ? `, ${department}` : "");
	window.frappe.confirm(
		`Publish ${count} Tentative case(s) on ${date} for ${shown}? They become Scheduled, their ` +
			"Clinical Procedures are created and the ward gets their fasting tasks. Moving or " +
			"cancelling them after this needs a reason.",
		() => publish(day, filters, reload),
	);
}

async function publish(day, filters, reload) {
	try {
		const result = await post("publishing.publish_day", { date: day, ...filters });
		if (result.published.length)
			toastSuccess(`Published ${result.published.length} case(s)`);
		for (const row of result.failed)
			toastError(`${row.patient_name || row.name}: ${row.message}`);
		playDropSound(result.failed.length ? "refused" : "placed");
	} catch (error) {
		showError(error);
		playDropSound("refused");
	}
	reload();
}
