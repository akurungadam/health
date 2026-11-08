// Auto Schedule the Day on the board (ot_booking/auto_schedule.py): the plan is shown in the
// theatre lanes, beside the real cases, until it is booked or discarded. A plan is for one day
// and one set of filters, so changing either discards it, and a reply to a preview made before
// that is dropped. Booking books the selection the plan was made for.
import { computed, ref } from "vue";

import { post, showError, toastError, toastSuccess } from "./api.js";

export function useAutoSchedule({ day, filters, reload }) {
	const plan = ref(null);
	const busy = ref(false);
	// counts previews and discards, so a reply knows whether it is still the latest
	let runs = 0;

	async function preview() {
		const run = ++runs;
		const selection = params();
		busy.value = true;
		try {
			const result = await post("auto_schedule.plan_day", selection);
			if (run === runs) plan.value = { ...result, selection };
		} catch (error) {
			if (run === runs) showError(error);
		}
		if (run === runs) busy.value = false;
	}

	async function book() {
		busy.value = true;
		try {
			const result = await post("auto_schedule.book_day", plan.value.selection);
			if (result.placed.length)
				toastSuccess(`Booked ${result.placed.length} case(s)`);
			for (const row of result.not_placed)
				toastError(`${row.patient_name}: ${plainText(row.reason)}`);
			plan.value = null;
			reload();
		} catch (error) {
			showError(error);
		}
		busy.value = false;
	}

	function discard() {
		runs++;
		plan.value = null;
		busy.value = false;
	}

	const plannedByName = computed(() =>
		Object.fromEntries((plan.value?.placed || []).map(row => [row.name, row])),
	);

	function plannedIn(theatre) {
		return plan.value?.placed.filter(row => row.theatre === theatre) || [];
	}

	function params() {
		return { date: day.value, ...filters() };
	}

	return { plan, busy, preview, book, discard, plannedIn, plannedByName };
}

// a server message as text: its bold markup dropped, never rendered as HTML
export function plainText(message) {
	return String(message).replace(/<[^>]+>/g, "");
}
