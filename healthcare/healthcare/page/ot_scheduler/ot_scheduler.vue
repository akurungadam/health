<script setup>
// The OT Scheduler: one day of every theatre.
//
// Theatres are rows grouped by OT complex, and time runs across. Each case shows
// its cleaning time after it, blocked theatre time is hatched, and the
// practitioners who are away that day are listed above the board. A request from
// the panel dropped onto a row is booked there; a case dragged elsewhere moves.
// The server checks every drop, so a refused one stays where it was.
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
	Badge,
	Button,
	ContextMenu,
	HoverCard,
	DatePicker,
	Dialog,
	FormControl,
	frappeRequest,
	toast,
	ToastProvider,
} from "frappe-ui";
import { useHost } from "@framework/ui/island";

import FastingIcon from "~icons/lucide/utensils-crossed";

import BookingPreview from "./booking_preview.vue";
import { patientFacts } from "./patient.js";
import RequestPanel from "./request_panel.vue";
import { playDropSound } from "./sounds.js";
import { clock, isoDate, minutesOf, today, twoDigits } from "./time.js";

const props = defineProps({
	route: { type: Array, default: () => [] },
	query: { type: Object, default: () => ({}) },
});
const emit = defineEmits(["title", "actions"]);
const host = useHost();

const RELOAD_SECONDS = 60;
const SNAP_MINUTES = 15;
// statuses that take a case off the board, and the word for doing it
const STOPPING = ["Postponed", "Cancelled"];
const STOPPING_ACTIONS = { Postponed: "Postpone", Cancelled: "Cancel" };
const API = "healthcare.healthcare.doctype.ot_booking";
const STATUS_CLASSES = {
	Tentative: "border-dashed border-outline-gray-3 bg-surface-gray-2",
	Scheduled: "border-outline-blue-1 bg-surface-blue-2",
	"In Progress": "border-outline-amber-1 bg-surface-amber-2",
	Completed: "border-outline-green-1 bg-surface-green-2",
};

const day = ref(props.query.date || today());
const board = ref(null);
const requests = ref([]);
const postponed = ref([]);
const dragged = ref(null);
const dropTheatre = ref(null);
const reasonFor = ref(null);
const reason = ref("");
const menuFor = ref(null);
const previewFor = ref(null);

const dayStart = computed(() => board.value && minutesOf(board.value.day_start));
const dayEnd = computed(() => board.value && minutesOf(board.value.day_end));
const hours = computed(() => {
	if (!board.value) return [];
	const first = Math.ceil(dayStart.value / 60);
	const last = Math.floor(dayEnd.value / 60);
	return Array.from({ length: last - first + 1 }, (_, index) => first + index);
});

onMounted(() => {
	emit("title", "OT Scheduler");
	emit("actions", [
		{ label: "New OT Booking", onClick: () => host.navigate?.("ot-booking/new") },
	]);
	load();
});
useBoardFeed(load);
watch(day, value => (value ? load() : goToday()));

async function load() {
	try {
		[board.value, requests.value, postponed.value] = await Promise.all([
			get("board.get_board", { date: day.value }),
			get("scheduling.get_open_requests"),
			get("scheduling.get_postponed"),
		]);
	} catch (error) {
		showError(error);
	}
}

// The first server message is the toast; any others go beneath it
function showError(error) {
	const [first, ...rest] = error?.messages?.length
		? error.messages
		: [error?.message || String(error)];
	toast.error(first, { description: rest.join(" ") || undefined });
}

function get(method, params = {}) {
	return frappeRequest({ url: `${API}.${method}`, params, method: "GET" });
}

function post(method, params) {
	const headers = { "X-Frappe-CSRF-Token": window.frappe?.csrf_token };
	return frappeRequest({ url: `${API}.${method}`, params, method: "POST", headers });
}

function pickRequest(request, event) {
	dragged.value = { request, grab: 0 };
	event.dataTransfer.setData("text/plain", request.name);
}

function pickPostponed(booking, event) {
	dragged.value = { booking, grab: 0 };
	event.dataTransfer.setData("text/plain", booking.name);
}

// A booked case dropped back on the pane is postponed, keeping its booking for another day
function unschedule() {
	const booking = dragged.value?.booking;
	dragged.value = null;
	if (!booking || booking.status === "Postponed") return;
	askReason("set_status", stopParams(booking, "Postponed"), "Postpone");
}

function stopParams(booking, status) {
	return { name: booking.name, status, modified: booking.modified };
}

// Where in the case it was grabbed, so the case keeps that point under the cursor
function pickBooking(booking, event) {
	const block = event.currentTarget.getBoundingClientRect();
	const row = event.currentTarget.parentElement.getBoundingClientRect();
	const grab =
		((event.clientX - block.left) / row.width) * (dayEnd.value - dayStart.value);
	dragged.value = { booking, grab };
	event.dataTransfer.setData("text/plain", booking.name);
}

function drop(theatre, event) {
	dropTheatre.value = null;
	const drag = dragged.value;
	dragged.value = null;
	if (!drag) return;
	const start = dropStart(event, drag.grab);
	if (drag.request) {
		const booking = { service_request: drag.request.name, theatre, start };
		// on the day of surgery only an OT Manager may add a case, and must say why
		if (day.value === today()) return askReason("book_request", booking, "Add");
		return change("book_request", booking);
	}
	const move = {
		name: drag.booking.name,
		theatre,
		start,
		modified: drag.booking.modified,
	};
	// moving onto today adds a case on the day of surgery, which needs a reason unless it is an emergency
	if (
		drag.booking.needs_reason ||
		(day.value === today() && drag.booking.priority !== "Emergency")
	)
		return askReason("move_booking", move, "Move");
	change("move_booking", move);
}

function dropStart(event, grab) {
	const row = event.currentTarget.getBoundingClientRect();
	const at =
		dayStart.value +
		((event.clientX - row.left) / row.width) * (dayEnd.value - dayStart.value);
	const minutes = Math.round((at - grab) / SNAP_MINUTES) * SNAP_MINUTES;
	return `${day.value} ${twoDigits(Math.floor(minutes / 60))}:${twoDigits(
		minutes % 60,
	)}:00`;
}

// A change the server will refuse without a reason waits here for one
function askReason(method, params, action) {
	reason.value = "";
	reasonFor.value = { method, params, action };
	menuFor.value = null;
	previewFor.value = null;
}

function changeWithReason({ close }) {
	if (!reason.value.trim()) return;
	change(reasonFor.value.method, { ...reasonFor.value.params, reason: reason.value });
	close();
}

// A case's menu and its preview never show together, and neither opens over the reason dialog
function menuOpened(booking, open) {
	menuFor.value = open && !reasonFor.value ? booking.name : null;
	if (open) previewFor.value = null;
}

function previewOpened(booking, open) {
	previewFor.value = open && !menuFor.value && !reasonFor.value ? booking.name : null;
}

// A case's menu, on a left or right click: open it, or move it to a next status
function caseMenu(booking) {
	const statuses = booking.next_statuses.map(status =>
		STOPPING.includes(status)
			? {
					label: `${STOPPING_ACTIONS[status]}…`,
					theme: "red",
					onClick: () =>
						askReason(
							"set_status",
							stopParams(booking, status),
							STOPPING_ACTIONS[status],
						),
			  }
			: {
					label: status,
					onClick: () => change("set_status", stopParams(booking, status)),
			  },
	);
	if (!statuses.length)
		statuses.push({ label: `No change from ${booking.status}`, disabled: true });
	const actions = [{ label: "View", onClick: () => openBooking(booking.name) }];
	if (booking.procedures_pending)
		actions.push({
			label: "Create Procedures",
			onClick: () => createProcedures(booking),
		});
	return [
		{ group: "Booking", hideLabel: true, options: actions },
		{ group: "Change status", options: statuses },
	];
}

async function createProcedures(booking) {
	const created = await change("create_procedures", { name: booking.name });
	if (created?.length)
		toast.success(`Created ${created.length} Clinical Procedure(s)`);
}

async function change(method, params) {
	let result;
	try {
		result = await post(`scheduling.${method}`, params);
		playDropSound("placed");
	} catch (error) {
		showError(error);
		playDropSound("refused");
	}
	load();
	return result;
}

function moveDay(days) {
	const date = new Date(`${day.value}T00:00:00`);
	date.setDate(date.getDate() + days);
	day.value = isoDate(date);
}

function goToday() {
	day.value = today();
}

function bookingsIn(theatre) {
	return board.value.bookings.filter(booking => booking.theatre === theatre);
}

function blocksIn(theatre) {
	return board.value.blocks.filter(block => block.scope === theatre);
}

function span(start, end) {
	const width = dayEnd.value - dayStart.value;
	const from = Math.max(start, dayStart.value);
	const to = Math.min(end, dayEnd.value);
	return {
		left: `${((from - dayStart.value) / width) * 100}%`,
		width: `${((to - from) / width) * 100}%`,
	};
}

// Blocks share one grid cell, placed across it by time
function placed(start, end) {
	const { left, width } = span(start, end);
	return { gridArea: "1 / 1", marginLeft: left, width };
}

function cleaningPlace(booking) {
	const end = minutesOf(booking.scheduled_end);
	return placed(end, end + board.value.cleaning_minutes);
}

function openBooking(name) {
	host.navigate?.(`ot-booking/${name}`);
}

function useBoardFeed(reload) {
	const realtime = window.frappe?.realtime;
	let timer = null;
	const whenChanged = data => data?.doctype === "OT Booking" && reload();
	onMounted(() => {
		realtime?.doctype_subscribe?.("OT Booking");
		realtime?.on("list_update", whenChanged);
		timer = window.setInterval(reload, RELOAD_SECONDS * 1000);
	});
	onBeforeUnmount(() => {
		realtime?.off("list_update", whenChanged);
		window.clearInterval(timer);
	});
}
</script>

<template>
	<div class="flex h-full flex-col gap-3 overflow-hidden p-5">
		<div class="flex shrink-0 flex-wrap items-center gap-2">
			<Button @click="moveDay(-1)">Previous</Button>
			<Button @click="goToday">Today</Button>
			<Button @click="moveDay(1)">Next</Button>
			<DatePicker v-model="day" format="ddd, D MMM YYYY" class="w-44" />
			<Badge
				v-if="board?.holiday"
				:theme="board.holiday.is_half_day ? 'orange' : 'red'"
				size="lg"
			>
				{{ board.holiday.is_half_day ? "Half-day holiday" : "Holiday" }}:
				{{ board.holiday.description }}
			</Badge>
		</div>

		<ToastProvider />

		<div
			v-if="board?.away.length"
			class="flex shrink-0 flex-wrap items-center gap-2 text-sm"
		>
			<span class="text-ink-gray-5">Away today</span>
			<Badge
				v-for="row in board.away"
				:key="`${row.practitioner} ${row.reason} ${row.from_time}`"
				theme="gray"
			>
				{{ row.practitioner_name }} &middot; {{ row.reason }}
				<template v-if="row.from_time"
					>{{ clock(row.from_time) }}&ndash;{{ clock(row.to_time) }}</template
				>
			</Badge>
		</div>

		<div class="flex min-h-0 flex-1 gap-3">
			<RequestPanel
				:requests="requests"
				:postponed="postponed"
				:dropping="
					Boolean(dragged?.booking && dragged.booking.status !== 'Postponed')
				"
				@pick="pickRequest"
				@pick-postponed="pickPostponed"
				@unschedule="unschedule"
				@done="dragged = null"
			/>

			<p
				v-if="board && !board.complexes.length"
				class="p-8 text-center text-base text-ink-gray-5"
			>
				No operation theatres. Mark a Healthcare Service Unit Type as an OT to
				see its units here.
			</p>

			<div
				v-else-if="board"
				class="flex-1 overflow-auto rounded-4 border border-outline-gray-2"
			>
				<div
					class="sticky top-0 z-10 flex border-b border-outline-gray-2 bg-surface-base"
				>
					<div class="w-44 shrink-0 p-2 text-sm text-ink-gray-5">Theatre</div>
					<div class="relative h-8 min-w-[720px] flex-1">
						<span
							v-for="hour in hours"
							:key="hour"
							class="absolute top-2 -translate-x-1/2 text-xs text-ink-gray-5"
							:style="span(hour * 60, hour * 60)"
						>
							{{ String(hour).padStart(2, "0") }}:00
						</span>
					</div>
				</div>

				<section v-for="group in board.complexes" :key="group.name">
					<h2
						class="bg-surface-gray-1 px-2 py-1 text-sm font-semibold text-ink-gray-7"
					>
						{{ group.name || "Theatres" }}
					</h2>
					<div
						v-for="theatre in group.theatres"
						:key="theatre.name"
						class="flex border-b border-outline-gray-1 last:border-b-0"
					>
						<div class="w-44 shrink-0 p-2">
							<p class="truncate text-base text-ink-gray-8">
								{{ theatre.label }}
							</p>
							<p class="truncate text-xs text-ink-gray-5">
								{{ theatre.service_unit_type }}
							</p>
						</div>
						<div
							class="relative grid h-24 min-w-[720px] flex-1 py-1"
							:class="dropTheatre === theatre.name && 'bg-surface-gray-1'"
							@dragover.prevent="dropTheatre = theatre.name"
							@dragleave="dropTheatre = null"
							@drop.prevent="drop(theatre.name, $event)"
						>
							<span
								v-for="hour in hours"
								:key="hour"
								class="absolute inset-y-0 border-l border-outline-gray-1"
								:style="span(hour * 60, hour * 60)"
							/>
							<div
								v-for="block in blocksIn(theatre.name)"
								:key="block.name"
								class="ot-hatch rounded-4 bg-surface-red-1"
								:style="
									placed(
										minutesOf(block.start_time),
										minutesOf(block.end_time),
									)
								"
								:title="`Unavailable (${block.name})`"
							/>
							<template
								v-for="booking in bookingsIn(theatre.name)"
								:key="booking.name"
							>
								<div
									v-if="board.cleaning_minutes"
									class="ot-hatch rounded-e-4 bg-surface-gray-1"
									:style="cleaningPlace(booking)"
									title="Cleaning"
								/>
								<ContextMenu
									:options="caseMenu(booking)"
									:open="menuFor === booking.name"
									@update:open="open => menuOpened(booking, open)"
								>
									<template #default="{ setOpen }">
										<button
											class="overflow-hidden border px-2 py-1 text-left"
											:class="[
												STATUS_CLASSES[booking.status],
												board.cleaning_minutes
													? 'rounded-s-4'
													: 'rounded-4',
												booking.priority === 'Emergency' &&
													'ring-2 ring-outline-red-3',
											]"
											:style="
												placed(
													minutesOf(booking.scheduled_start),
													minutesOf(booking.scheduled_end),
												)
											"
											:draggable="
												['Tentative', 'Scheduled'].includes(
													booking.status,
												)
											"
											@dragstart="pickBooking(booking, $event)"
											@dragend="dragged = null"
											@click="setOpen(true)"
										>
											<HoverCard
												:hover-delay="500"
												:open="previewFor === booking.name"
												@update:open="
													open => previewOpened(booking, open)
												"
											>
												<template #trigger>
													<div class="flex h-full flex-col">
														<div
															class="flex items-start gap-1"
														>
															<p
																class="flex min-w-0 flex-1 flex-wrap gap-x-1 text-sm"
															>
																<span
																	class="max-w-full truncate font-medium text-ink-gray-9"
																>
																	{{
																		booking.patient_name
																	}}
																</span>
																<span
																	class="shrink-0 text-ink-gray-5"
																>
																	{{
																		patientFacts(
																			booking,
																		)
																	}}
																</span>
															</p>
															<FastingIcon
																class="size-3.5 shrink-0"
																:class="
																	booking.fasting_confirmed
																		? 'text-ink-green-3'
																		: 'text-ink-gray-4'
																"
																:title="
																	booking.fasting_confirmed
																		? 'Fasting confirmed'
																		: 'Fasting not confirmed'
																"
															/>
														</div>
														<p
															class="truncate text-xs text-ink-gray-6"
														>
															{{
																clock(
																	booking.scheduled_start,
																)
															}}&ndash;{{
																clock(
																	booking.scheduled_end,
																)
															}}
														</p>
														<p
															class="truncate text-xs text-ink-gray-6"
														>
															{{ booking.surgeon }}
														</p>
													</div>
												</template>
												<BookingPreview
													:booking="booking"
													:theatre="theatre.label"
													:time="`${clock(
														booking.scheduled_start,
													)}–${clock(booking.scheduled_end)}`"
												/>
											</HoverCard>
										</button>
									</template>
								</ContextMenu>
							</template>
						</div>
					</div>
				</section>
			</div>
		</div>

		<Dialog
			:open="Boolean(reasonFor)"
			title="Reason for this change"
			message="The list for this day is committed, so say why the case is changing."
			:actions="[
				{
					label: reasonFor?.action || 'Save',
					variant: 'solid',
					onClick: changeWithReason,
				},
			]"
			@update:open="open => !open && (reasonFor = null)"
		>
			<FormControl v-model="reason" type="textarea" placeholder="Reason" />
		</Dialog>
	</div>
</template>

<style scoped>
.ot-hatch {
	background-image: repeating-linear-gradient(
		45deg,
		transparent 0 6px,
		var(--outline-gray-2, rgba(0, 0, 0, 0.08)) 6px 7px
	);
}
</style>
