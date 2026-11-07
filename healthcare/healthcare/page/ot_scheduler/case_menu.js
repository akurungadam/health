// A case's menu on the board, opened with a left or right click: view it, create its
// procedures, reschedule it, or move it to its next status. Cancelling a published case needs a
// reason; a Tentative one only a confirm, so a click cannot cancel it by mistake. A viewer who
// cannot change bookings gets View alone.

export function caseMenu(
	booking,
	{ canEdit, open, createProcedures, reschedule, change, askReason },
) {
	const actions = [{ label: "View", onClick: () => open(booking.name) }];
	if (!canEdit) return [{ group: "Booking", hideLabel: true, options: actions }];
	if (booking.next_statuses.includes("Postponed"))
		actions.push({
			label: booking.status === "Scheduled" ? "Reschedule…" : "Reschedule",
			onClick: () => reschedule(booking),
		});
	if (booking.procedures_pending)
		actions.push({
			label: "Create Procedures",
			onClick: () => createProcedures(booking),
		});
	return [
		{ group: "Booking", hideLabel: true, options: actions },
		{ group: "Change status", options: statusOptions(booking, change, askReason) },
	];
}

// Postponed is left out: a case goes back to the pane with Reschedule
function statusOptions(booking, change, askReason) {
	const options = booking.next_statuses
		.filter(status => status !== "Postponed")
		.map(status =>
			status === "Cancelled"
				? {
						label: "Cancel…",
						theme: "red",
						onClick: () => cancel(booking, change, askReason),
				  }
				: {
						label: status,
						onClick: () =>
							change("set_status", statusParams(booking, status)),
				  },
		);
	if (!options.length)
		options.push({ label: `No change from ${booking.status}`, disabled: true });
	return options;
}

function cancel(booking, change, askReason) {
	const params = statusParams(booking, "Cancelled");
	if (booking.status === "Scheduled")
		return askReason("set_status", params, "Cancel");
	window.frappe.confirm(`Cancel ${booking.patient_name}'s case?`, () =>
		change("set_status", params),
	);
}

export function statusParams(booking, status) {
	return { name: booking.name, status, modified: booking.modified };
}
