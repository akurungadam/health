// Dragging cases on the board: a request or a postponed case from the pane, or a booked case
// moved to another time or theatre. While a case is over a theatre row, `plan` says where it
// would land and what the drop would do there; on the drop the server makes the change.
import { ref } from "vue";
import { toast } from "frappe-ui";

import { post, showError } from "./api.js";
import { hideDragImage, planDrop, snapFirstDrop, snapToGrid } from "./drop_plan.js";
import { playDropSound } from "./sounds.js";
import {
	caseMinutes,
	caseOnDay,
	DAY_MINUTES,
	minutesOf,
	pastUntil,
	twoDigits,
} from "./time.js";

export function useDrop({
	board,
	day,
	vertical,
	canEdit,
	bookingsIn,
	blocksIn,
	change,
	askReason,
	stopParams,
}) {
	const dragged = ref(null);
	const dropTheatre = ref(null);
	const plan = ref(null);

	// A request or a postponed case is a first drop: no grab, and it may snap to the case before it
	function pickRequest(request, event) {
		pick(
			{ request, grab: null, length: Math.round(request.duration / 60) },
			request.name,
			event,
		);
	}

	function pickPostponed(booking, event) {
		pick({ booking, grab: null, length: caseLength(booking) }, booking.name, event);
	}

	function pick(drag, name, event) {
		dragged.value = drag;
		plan.value = null;
		event.dataTransfer.setData("text/plain", name);
		hideDragImage(event);
	}

	function caseLength(booking) {
		return caseMinutes(booking);
	}

	// A booked case dropped back on the pane is rescheduled, keeping its booking for another day
	function unschedule() {
		const booking = dragged.value?.booking;
		endDrag();
		if (booking && booking.status !== "Postponed") reschedule(booking);
	}

	// The ghost belongs to a row, so it goes as soon as the case is anywhere else: over the
	// pane, dropped there, or let go of anywhere at all
	function clearGhost() {
		dropTheatre.value = null;
		plan.value = null;
	}

	function endDrag() {
		dragged.value = null;
		clearGhost();
	}

	// Back to the To schedule pane, keeping the booking for a new day. A Scheduled case was
	// published, so it needs a reason; a Tentative one goes straight back.
	function reschedule(booking) {
		const params = stopParams(booking, "Postponed");
		if (booking.status === "Scheduled")
			return askIfPossible("set_status", params, "Reschedule");
		change("set_status", params);
	}

	// Where in the case it was grabbed, so the case keeps that point under the cursor
	function pickBooking(booking, event) {
		const block = event.currentTarget.getBoundingClientRect();
		const lane = event.currentTarget.parentElement.getBoundingClientRect();
		const grab = alongLane(event, lane, block);
		pick({ booking, grab, length: caseLength(booking) }, booking.name, event);
	}

	// What the drop would do at the cursor, shown on the row before the case is let go. Over
	// the theatre's name (no event) a case lands at the start of the working day.
	function dragOver(theatre, event) {
		if (!canEdit.value || !dragged.value) return;
		dropTheatre.value = theatre;
		const drag = dragged.value;
		const cleaning = board.value.cleaning_minutes;
		const cases = rowCases(theatre, drag.booking?.name);
		const workStart = minutesOf(board.value.day_start);
		const at = event ? cursorMinutes(event) : workStart;
		const start =
			drag.grab === null
				? snapFirstDrop(cases, at, cleaning)
				: event
				  ? snapToGrid(at - drag.grab)
				  : workStart;
		const blocks = blocksIn(theatre).map(block => ({
			start: minutesOf(block.start_time),
			end: minutesOf(block.end_time),
		}));
		plan.value = planDrop({
			cases,
			blocks,
			start,
			length: drag.length,
			cleaning,
			// the end of the usual working day: running past it is shown, not refused
			dayEnd: minutesOf(board.value.day_end),
			holiday: fullHoliday(),
			pastUntil: pastUntil(day.value),
			emergency: Boolean(
				drag.request?.is_emergency || drag.booking?.is_emergency,
			),
		});
	}

	function fullHoliday() {
		const holiday = board.value.holiday;
		return holiday && !holiday.is_half_day ? holiday.description : null;
	}

	function rowCases(theatre, leaving) {
		return bookingsIn(theatre)
			.filter(booking => booking.name !== leaving)
			.map(booking => ({
				name: booking.name,
				patient_name: booking.patient_name,
				status: booking.status,
				is_emergency: booking.is_emergency,
				...caseOnDay(booking, String(board.value.date)),
			}));
	}

	function cursorMinutes(event) {
		return alongLane(event, event.currentTarget.getBoundingClientRect());
	}

	// The cursor's time on a lane, measured from the start of `from` (the lane, or a case on it):
	// across the lane on rows, down it on columns
	function alongLane(event, lane, from = lane) {
		if (vertical.value)
			return ((event.clientY - from.top) / lane.height) * DAY_MINUTES;
		return ((event.clientX - from.left) / lane.width) * DAY_MINUTES;
	}

	function atTime(minutes) {
		return `${day.value} ${twoDigits(Math.floor(minutes / 60))}:${twoDigits(
			minutes % 60,
		)}:00`;
	}

	function drop(theatre) {
		dropTheatre.value = null;
		const drag = dragged.value;
		const landing = plan.value;
		dragged.value = null;
		plan.value = null;
		if (!drag || !landing) return;
		if (landing.problem) {
			toast.error(landing.problem);
			return playDropSound("refused");
		}
		const start = atTime(landing.start);
		// Adding a case never needs a reason. Moving a published case does, and so does a drop
		// that pushes published cases back.
		if (drag.request) {
			const booking = { service_request: drag.request.name, theatre, start };
			if (landing.needsReason)
				return askIfPossible("book_request", booking, "Add");
			return change("book_request", booking);
		}
		const move = {
			name: drag.booking.name,
			theatre,
			start,
			modified: drag.booking.modified,
		};
		if (drag.booking.needs_reason || landing.needsReason)
			return askIfPossible("move_booking", move, "Move");
		change("move_booking", move);
	}

	// The reason is asked for only when the server says the drop would go through
	async function askIfPossible(method, params, action) {
		try {
			const refusal = await post("scheduling.check_drop", {
				method,
				params: JSON.stringify(params),
			});
			if (!refusal) return askReason(method, params, action);
			toast.error(refusal);
		} catch (error) {
			showError(error);
		}
		playDropSound("refused");
	}

	return {
		dragged,
		dropTheatre,
		plan,
		pickRequest,
		pickPostponed,
		pickBooking,
		dragOver,
		drop,
		unschedule,
		reschedule,
		clearGhost,
		endDrag,
	};
}
