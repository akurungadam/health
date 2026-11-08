<script setup>
// The OT Scheduler: one day of every theatre.
//
// Theatres are rows grouped by OT complex, and time runs across; or, by the Healthcare
// Settings' OT Scheduler Layout, theatres are columns and time runs down. Each case shows
// its cleaning time after it, blocked theatre time is hatched, and the
// practitioners who are away that day are listed above the board. A request from
// the panel dropped onto a row is booked there; a case dragged elsewhere moves.
// The server checks every drop, so a refused one stays where it was.
import { computed, onMounted, ref, watch } from "vue";
import { Badge, Dialog, FormControl, toast, ToastProvider } from "frappe-ui";
import { useHost } from "@framework/ui/island";

import CaseCard from "./case_card.vue";
import HourScale from "./hour_scale.vue";
import DropGhost from "./drop_ghost.vue";
import { caseMenu as buildCaseMenu, statusParams } from "./case_menu.js";
import { confirmPublish } from "./publish.js";
import SlotHighlight from "./slot_highlight.vue";
import RowWash from "./row_wash.vue";
import UnavailableBlock from "./unavailable_block.vue";
import { useDrop } from "./use_drop.js";
import { useSlots } from "./use_slots.js";
import DateBar from "./date_bar.vue";
import RequestPanel from "./request_panel.vue";
import { get, post, showError } from "./api.js";
import { useBoardFeed } from "./feed.js";
import { playDropSound } from "./sounds.js";
import {
	clock,
	DAY_SIZE,
	HOUR_SIZE,
	HOURS,
	caseOnDay,
	minutesOf,
	pastUntil,
	placed,
	span,
	today,
} from "./time.js";

const props = defineProps({
	route: { type: Array, default: () => [] },
	query: { type: Object, default: () => ({}) },
});
const emit = defineEmits(["title", "actions"]);
const host = useHost();

const day = ref(props.query.date || today());
const company = ref(props.query.company || "");
const department = ref(props.query.department || "");
const board = ref(null);
const requests = ref([]);
const postponed = ref([]);
const reasonFor = ref(null);
const reason = ref("");
const menuFor = ref(null);
const previewFor = ref(null);

// The whole day, midnight to midnight, scrolled to the usual working hours; any hour is bookable
const timeline = ref(null);
const vertical = computed(() => board.value?.layout === "Theatres in Columns");
// A theatre's lane is at least 96px tall as a row, or 144px wide as a column, and shares out
// whatever room the board has left, so a few theatres fill the screen and many scroll
const LANE = { row: "minmax(96px, 1fr)", column: "minmax(144px, 1fr)" };
const boardGrid = computed(() => {
	const groups = board.value.complexes;
	if (!vertical.value) {
		const rows = groups.flatMap(group => [
			"auto",
			...group.theatres.map(() => LANE.row),
		]);
		return {
			gridTemplateColumns: `176px ${DAY_SIZE}px`,
			gridTemplateRows: ["auto", ...rows].join(" "),
		};
	}
	const count = groups.flatMap(group => group.theatres).length;
	return {
		gridTemplateColumns: `56px repeat(${count}, ${LANE.column})`,
		gridTemplateRows: `auto ${DAY_SIZE}px`,
		gridAutoFlow: "column",
	};
});
const workStart = computed(() => minutesOf(board.value?.day_start || "08:00"));
const workEnd = computed(() => minutesOf(board.value?.day_end || "20:00"));
let scrolledDay = null;
// a viewer who cannot change bookings sees the board read-only
const canEdit = computed(() => Boolean(board.value?.can_edit));
const tentativeCount = computed(
	() =>
		board.value?.bookings.filter(booking => booking.status === "Tentative")
			.length || 0,
);

onMounted(() => {
	emit("title", "OT Scheduler");
	load();
});
// the page menu (the three dots) offers Publish while the day has Tentative cases
watch([tentativeCount, canEdit], sendActions, { immediate: true });
useBoardFeed(load);
watch(day, value => (value ? load() : (day.value = today())));
// the first load fills in the user's default company, which needs no second load; any other
// change of company, the first pick of a user with no default included, loads the board
let companyFromServer = false;
watch(company, () => {
	if (companyFromServer) return (companyFromServer = false);
	department.value = "";
	load();
});
watch(department, load);
// a new day opens at the start of working hours; a reload of the same day stays where it is
watch(board, scrollToWorkingHours, { flush: "post" });

function scrollToWorkingHours() {
	if (!timeline.value || scrolledDay === day.value) return;
	// a quarter of an hour early, so a case at the start of the day clears the theatre names
	const offset = ((workStart.value - 15) / 60) * HOUR_SIZE;
	timeline.value[vertical.value ? "scrollTop" : "scrollLeft"] = offset;
	scrolledDay = day.value;
}

const {
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
} = useDrop({
	board,
	day,
	vertical,
	canEdit,
	bookingsIn,
	blocksIn,
	change,
	askReason,
	stopParams: statusParams,
});

function caseMenu(booking) {
	return buildCaseMenu(booking, {
		canEdit: canEdit.value,
		open: openBooking,
		createProcedures,
		reschedule,
		change,
		askReason,
	});
}

const {
	finder,
	picked,
	find: findSlots,
	pick: pickSlot,
	book: bookSlot,
	close: closeSlots,
	slotIn,
} = useSlots({ day, filters: boardFilters, change });
// slots found for other theatres no longer apply
watch([company, department], closeSlots);

// The board's set filters, for loading and publishing: an empty one arrives as "undefined"
function boardFilters() {
	const filters = { company: company.value, department: department.value };
	return Object.fromEntries(Object.entries(filters).filter(([, value]) => value));
}

async function load() {
	try {
		const filters = boardFilters();
		[board.value, requests.value, postponed.value] = await Promise.all([
			get("board.get_board", { date: day.value, ...filters }),
			get("scheduling.get_open_requests", filters),
			get("scheduling.get_postponed", filters),
		]);
		if (!company.value && board.value.company) {
			companyFromServer = true;
			company.value = board.value.company;
		}
	} catch (error) {
		showError(error);
	}
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

// A case's menu and its preview never show together, and neither opens over the reason
// dialog. Any preview, a case's or a block's, closes while the board scrolls.
function menuOpened(booking, open) {
	menuFor.value = open && !reasonFor.value ? booking.name : null;
	if (open) previewFor.value = null;
}

function previewOpened(booking, open) {
	previewFor.value = open && !menuFor.value && !reasonFor.value ? booking.name : null;
}

function sendActions([count, editable]) {
	if (!editable) return emit("actions", []);
	const actions = [
		{ label: "New OT Booking", onClick: () => host.navigate?.("ot-booking/new") },
	];
	if (count)
		actions.push({
			label: `Publish ${count} case(s)`,
			onClick: () =>
				confirmPublish({
					count,
					day: day.value,
					company: board.value.company,
					department: department.value,
					filters: boardFilters(),
					host,
					reload: load,
				}),
		});
	emit("actions", actions);
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

// a case whose time has passed stays put: it can only be rescheduled or cancelled
function hasPassed(booking) {
	return caseOnDay(booking, boardDay()).start < pastUntil(boardDay());
}

function bookingsIn(theatre) {
	return board.value.bookings.filter(booking => booking.theatre === theatre);
}

function blocksIn(theatre) {
	return board.value.blocks.filter(block => block.scope === theatre);
}

// The day the board's cases are for. Next and Previous change `day` at once, but the cases shown
// are the old day's until the new day loads, and are placed against their own day meanwhile.
function boardDay() {
	return String(board.value?.date || day.value);
}

// a place along a lane, in the board's direction
function place(start, end) {
	return placed(start, end, vertical.value);
}

function casePlace(booking) {
	const { start, end } = caseOnDay(booking, boardDay());
	return place(start, end);
}

function cleaningPlace(booking) {
	const { end } = caseOnDay(booking, boardDay());
	return place(end, end + board.value.cleaning_minutes);
}

function openBooking(name) {
	host.navigate?.(`ot-booking/${name}`);
}
</script>

<template>
	<div class="flex h-full flex-col gap-3 overflow-hidden p-5">
		<DateBar
			v-model:day="day"
			v-model:company="company"
			v-model:department="department"
			:board="board"
		/>

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
				v-if="canEdit"
				:requests="requests"
				:postponed="postponed"
				:dropping="
					Boolean(dragged?.booking && dragged.booking.status !== 'Postponed')
				"
				@pick="pickRequest"
				@pick-postponed="pickPostponed"
				@unschedule="unschedule"
				@over="clearGhost"
				@done="endDrag"
				:finder="finder"
				:picked="picked"
				@find="findSlots"
				@pick-slot="pickSlot"
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
				ref="timeline"
				class="flex-1 overflow-auto rounded-4 border border-outline-gray-2"
				@scroll="previewFor = null"
			>
				<!-- one grid, so the hours, the theatres and their lanes scroll together, with the
				     theatre names and the hours pinned. Theatres are rows, or columns by setting. -->
				<div class="grid min-h-full w-max min-w-full" :style="boardGrid">
					<div
						class="sticky left-0 top-0 z-30 border-b border-outline-gray-2 bg-surface-base p-2 text-sm text-ink-gray-5"
					>
						{{ vertical ? "" : "Theatre" }}
					</div>
					<HourScale :vertical="vertical" />
					<template v-for="group in board.complexes" :key="group.name">
						<h2
							v-if="!vertical"
							class="col-span-full bg-surface-gray-1 px-2 py-1 text-sm font-semibold text-ink-gray-7"
						>
							<span class="sticky left-2">{{
								group.name || "Theatres"
							}}</span>
						</h2>
						<template
							v-for="(theatre, index) in group.theatres"
							:key="theatre.name"
						>
							<div
								class="sticky z-20 bg-surface-base p-2"
								:class="
									vertical
										? 'top-0 border-b border-l border-outline-gray-2'
										: 'left-0 border-b border-outline-gray-1'
								"
								@dragover.prevent="dragOver(theatre.name, null)"
								@drop.prevent="drop(theatre.name)"
							>
								<p
									v-if="vertical"
									class="truncate text-xs font-semibold text-ink-gray-7"
									:class="index && 'invisible'"
								>
									{{ group.name || "Theatres" }}
								</p>
								<p class="truncate text-base text-ink-gray-8">
									{{ theatre.label }}
								</p>
								<p class="truncate text-xs text-ink-gray-5">
									{{ theatre.service_unit_type }}
								</p>
							</div>
							<div
								class="relative isolate grid overflow-hidden border-outline-gray-1"
								:class="[
									vertical ? 'border-l px-1' : 'border-b py-1',
									dropTheatre === theatre.name && 'bg-surface-gray-1',
								]"
								@dragover.prevent="dragOver(theatre.name, $event)"
								@dragleave="dropTheatre = null"
								@drop.prevent="drop(theatre.name)"
							>
								<RowWash
									:work-start="workStart"
									:work-end="workEnd"
									:placed="place"
								/>
								<span
									v-for="hour in HOURS"
									:key="hour"
									class="absolute -z-10 border-outline-gray-1"
									:class="
										vertical
											? 'inset-x-0 border-t'
											: 'inset-y-0 border-l'
									"
									:style="span(hour * 60, hour * 60, vertical)"
								/>
								<UnavailableBlock
									v-for="block in blocksIn(theatre.name)"
									:key="block.name"
									:block="block"
									:open="previewFor === block.name"
									@update:open="open => previewOpened(block, open)"
									@view="
										name =>
											host.navigate?.(
												`practitioner-availability/${name}`,
											)
									"
									:place="
										place(
											minutesOf(block.start_time),
											minutesOf(block.end_time),
										)
									"
								/>
								<CaseCard
									v-for="booking in bookingsIn(theatre.name)"
									:key="booking.name"
									:booking="booking"
									:theatre-label="
										[theatre.label, theatre.service_unit_type]
											.filter(Boolean)
											.join(' · ')
									"
									:cleaning-minutes="board.cleaning_minutes"
									:vertical="vertical"
									:menu-options="caseMenu(booking)"
									:menu-open="menuFor === booking.name"
									@update:menu-open="
										open => menuOpened(booking, open)
									"
									:preview-open="previewFor === booking.name"
									@update:preview-open="
										open => previewOpened(booking, open)
									"
									:movable="
										canEdit &&
										['Tentative', 'Scheduled'].includes(
											booking.status,
										) &&
										!hasPassed(booking)
									"
									:passed="hasPassed(booking)"
									:place="casePlace(booking)"
									:cleaning-place="cleaningPlace(booking)"
									@pick="event => pickBooking(booking, event)"
									@drop-end="endDrag"
								/>
								<DropGhost
									v-if="plan && dropTheatre === theatre.name"
									:plan="plan"
									:placed="place"
								/>
								<SlotHighlight
									v-if="slotIn(theatre.name)"
									:place="
										place(
											minutesOf(picked.start),
											minutesOf(picked.end) +
												board.cleaning_minutes,
										)
									"
									:gap="picked"
									@book="bookSlot"
									@clear="picked = null"
								/>
							</div>
						</template>
					</template>
				</div>
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

<style>
/* not scoped: unavailable_block.vue hatches its blocks the same way */
.ot-hatch {
	background-image: repeating-linear-gradient(
		45deg,
		transparent 0 6px,
		var(--outline-gray-2, rgba(0, 0, 0, 0.08)) 6px 7px
	);
}
</style>
