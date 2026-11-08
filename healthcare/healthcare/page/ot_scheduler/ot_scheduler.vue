<script setup>
// The OT Scheduler: one day of every theatre.
//
// Theatres are rows grouped by OT complex, and time runs across. Each case shows
// its cleaning time after it, blocked theatre time is hatched, and the
// practitioners who are away that day are listed above the board. A request from
// the panel dropped onto a row is booked there; a case dragged elsewhere moves.
// The server checks every drop, so a refused one stays where it was.
import { computed, onMounted, ref, watch } from "vue";
import {
	Badge,
	ContextMenu,
	HoverCard,
	Dialog,
	FormControl,
	toast,
	ToastProvider,
} from "frappe-ui";
import { useHost } from "@framework/ui/island";

import FastingIcon from "~icons/lucide/utensils-crossed";
import LockIcon from "~icons/lucide/lock";

import BookingPreview from "./booking_preview.vue";
import DropGhost from "./drop_ghost.vue";
import { caseMenu as buildCaseMenu, statusParams } from "./case_menu.js";
import { confirmPublish } from "./publish.js";
import SlotHighlight from "./slot_highlight.vue";
import RowWash from "./row_wash.vue";
import UnavailableBlock from "./unavailable_block.vue";
import { useDrop } from "./use_drop.js";
import { useSlots } from "./use_slots.js";
import { caseBorder, caseFill } from "./case_style.js";
import DateBar from "./date_bar.vue";
import { patientFacts } from "./patient.js";
import RequestPanel from "./request_panel.vue";
import { get, post, showError } from "./api.js";
import { useBoardFeed } from "./feed.js";
import { playDropSound } from "./sounds.js";
import { clock, minutesOf, pastUntil, placed, span, today } from "./time.js";

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
const HOUR_WIDTH = 96; // pixels: the usual 12-hour day is about a window wide
const THEATRE_WIDTH = 176; // the theatre column, w-44
const HOURS = Array.from({ length: 25 }, (_, hour) => hour);
const timeline = ref(null);
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
	// a quarter of an hour early, so a case at the start of the day clears the theatre column
	timeline.value.scrollLeft = ((workStart.value - 15) / 60) * HOUR_WIDTH;
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
	return minutesOf(booking.scheduled_start) < pastUntil(day.value);
}

function bookingsIn(theatre) {
	return board.value.bookings.filter(booking => booking.theatre === theatre);
}

function blocksIn(theatre) {
	return board.value.blocks.filter(block => block.scope === theatre);
}

function cleaningPlace(booking) {
	const end = minutesOf(booking.scheduled_end);
	return placed(end, end + board.value.cleaning_minutes);
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
				<!-- one block as wide as a row, so the header, headings and rows scroll together;
				     the theatre column stays put while the day scrolls past it -->
				<div :style="{ width: `${THEATRE_WIDTH + 24 * HOUR_WIDTH}px` }">
					<div
						class="sticky top-0 z-30 flex border-b border-outline-gray-2 bg-surface-base"
					>
						<div
							class="sticky left-0 z-30 w-44 shrink-0 bg-surface-base p-2 text-sm text-ink-gray-5"
						>
							Theatre
						</div>
						<div class="relative h-8 flex-1 overflow-hidden">
							<span
								v-for="hour in HOURS.slice(0, -1)"
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
							<span class="sticky left-2">{{
								group.name || "Theatres"
							}}</span>
						</h2>
						<div
							v-for="theatre in group.theatres"
							:key="theatre.name"
							class="flex border-b border-outline-gray-1 last:border-b-0"
						>
							<div
								class="sticky left-0 z-20 w-44 shrink-0 bg-surface-base p-2"
								@dragover.prevent="dragOver(theatre.name, null)"
								@drop.prevent="drop(theatre.name)"
							>
								<p class="truncate text-base text-ink-gray-8">
									{{ theatre.label }}
								</p>
								<p class="truncate text-xs text-ink-gray-5">
									{{ theatre.service_unit_type }}
								</p>
							</div>
							<div
								class="relative isolate grid h-24 flex-1 overflow-hidden py-1"
								:class="
									dropTheatre === theatre.name && 'bg-surface-gray-1'
								"
								@dragover.prevent="dragOver(theatre.name, $event)"
								@dragleave="dropTheatre = null"
								@drop.prevent="drop(theatre.name)"
							>
								<RowWash
									:work-start="workStart"
									:work-end="workEnd"
									:placed="placed"
								/>
								<span
									v-for="hour in HOURS"
									:key="hour"
									class="absolute inset-y-0 -z-10 border-l border-outline-gray-1"
									:style="span(hour * 60, hour * 60)"
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
										placed(
											minutesOf(block.start_time),
											minutesOf(block.end_time),
										)
									"
								/>
								<template
									v-for="booking in bookingsIn(theatre.name)"
									:key="booking.name"
								>
									<div
										v-if="board.cleaning_minutes"
										class="ot-hatch rounded-e-4 bg-surface-gray-1"
										:class="[caseBorder(booking), 'border-l-0']"
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
												class="overflow-hidden px-2 py-1 text-left"
												:class="[
													caseBorder(booking),
													caseFill(booking),
													board.cleaning_minutes
														? 'rounded-s-4 border-r-0'
														: 'rounded-4',
												]"
												:style="
													placed(
														minutesOf(
															booking.scheduled_start,
														),
														minutesOf(
															booking.scheduled_end,
														),
													)
												"
												:draggable="
													canEdit &&
													['Tentative', 'Scheduled'].includes(
														booking.status,
													) &&
													!hasPassed(booking)
												"
												@dragstart="
													pickBooking(booking, $event)
												"
												@dragend="endDrag"
												@click="setOpen(true)"
											>
												<HoverCard
													:hover-delay="500"
													:open="previewFor === booking.name"
													@update:open="
														open =>
															previewOpened(booking, open)
													"
												>
													<template #trigger>
														<div
															class="flex h-full flex-col"
														>
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
																<LockIcon
																	v-if="
																		hasPassed(
																			booking,
																		)
																	"
																	class="size-3.5 shrink-0 text-ink-gray-5"
																	title="Its time has passed: reschedule or cancel it"
																/>
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
														)}–${clock(
															booking.scheduled_end,
														)}`"
													/>
												</HoverCard>
											</button>
										</template>
									</ContextMenu>
								</template>
								<DropGhost
									v-if="plan && dropTheatre === theatre.name"
									:plan="plan"
									:placed="placed"
								/>
								<SlotHighlight
									v-if="slotIn(theatre.name)"
									:place="
										placed(
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
						</div>
					</section>
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
