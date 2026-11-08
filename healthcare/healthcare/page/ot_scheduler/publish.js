// The day shown on the board, as a whole, in its company and department (ot_booking/publishing.py).
// Publishing makes every Tentative case Scheduled; starting over sends every case not yet under way
// back to the pane. Desk's own confirm asks first, and its prompt asks one reason when a case was
// published. A case that fails its checks stays as it is and is reported on its own.
import { post, showError, toastError, toastSuccess } from "./api.js";
import { playDropSound } from "./sounds.js";
import { today } from "./time.js";

// The board's ⋯ menu for an editor. Auto Schedule and Start Over are for today or a day to come:
// nothing can be placed at a time that has passed. `count` and `published` are the day's
// Tentative and Scheduled cases.
export function dayActions({
	editable,
	count,
	published,
	shownDay,
	autoSchedule,
	newBooking,
	print,
	...day
}) {
	// anyone who can see the board can print it; the rest is for editors
	const printing = [
		{ label: "Print by Theatre", onClick: () => print("theatre") },
		{ label: "Print by Practitioner", onClick: () => print("practitioner") },
	];
	if (!editable) return printing;
	const actions = [{ label: "New OT Booking", onClick: newBooking }, ...printing];
	if (shownDay >= today())
		actions.push({ label: "Auto Schedule the Day", onClick: autoSchedule });
	if (shownDay >= today() && count + published)
		actions.push({
			label: "Start Over",
			onClick: () =>
				confirmStartOver({ count: count + published, published, ...day }),
		});
	if (count)
		actions.push({
			label: `Publish ${count} case(s)`,
			onClick: () => confirmPublish({ count, ...day }),
		});
	return actions;
}

function confirmPublish({ count, day, company, department, filters, host, reload }) {
	const date = host.format?.(day, { fieldtype: "Date" }) ?? day;
	const shown = company + (department ? `, ${department}` : "");
	window.frappe.confirm(
		`Publish ${count} Tentative case(s) on ${date} for ${shown}? They become Scheduled, their ` +
			"Clinical Procedures are created and the ward gets their fasting tasks. Moving or " +
			"cancelling them after this needs a reason.",
		() => publish(day, filters, reload),
	);
}

function publish(day, filters, reload) {
	dayChange(
		"publish_day",
		{ date: day, ...filters },
		"published",
		"Published",
		reload,
	);
}

function confirmStartOver({
	count,
	published,
	day,
	company,
	department,
	filters,
	host,
	reload,
}) {
	const date = host.format?.(day, { fieldtype: "Date" }) ?? day;
	const shown = company + (department ? `, ${department}` : "");
	const question =
		`Send the ${count} case(s) not yet under way on ${date} for ${shown} back to To reschedule? ` +
		"Their draft Clinical Procedures and fasting tasks go with them.";
	const startOver = reason =>
		dayChange(
			"start_over_day",
			{ date: day, ...filters, reason },
			"moved",
			"Moved back",
			reload,
		);
	if (!published) return window.frappe.confirm(question, () => startOver(null));
	window.frappe.prompt(
		{
			fieldname: "reason",
			fieldtype: "Small Text",
			label: "Reason",
			reqd: 1,
			description: question,
		},
		values => startOver(values.reason),
		"Start Over",
		"Start Over",
	);
}

async function dayChange(method, params, doneKey, doneLabel, reload) {
	try {
		const result = await post(`publishing.${method}`, params);
		if (result[doneKey].length)
			toastSuccess(`${doneLabel} ${result[doneKey].length} case(s)`);
		for (const row of result.failed)
			toastError(`${row.patient_name || row.name}: ${row.message}`);
		playDropSound(result.failed.length ? "refused" : "placed");
	} catch (error) {
		showError(error);
		playDropSound("refused");
	}
	reload();
}
