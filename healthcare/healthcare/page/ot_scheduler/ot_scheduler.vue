<script setup>
// The OT Scheduler: one day of every theatre, read-only for now.
//
// Theatres are rows grouped by OT complex, and time runs across. Each case shows
// its cleaning time after it, blocked theatre time is hatched, and the
// practitioners who are away that day are listed above the board.
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Badge, Button, DatePicker, frappeRequest } from "frappe-ui";
import { useHost } from "@framework/ui/island";

const props = defineProps({
	route: { type: Array, default: () => [] },
	query: { type: Object, default: () => ({}) },
});
const emit = defineEmits(["title", "actions"]);
const host = useHost();

const RELOAD_SECONDS = 60;
const STATUS_CLASSES = {
	Tentative: "border-dashed border-outline-gray-3 bg-surface-gray-2",
	Scheduled: "border-outline-blue-1 bg-surface-blue-2",
	"In Progress": "border-outline-amber-1 bg-surface-amber-2",
	Completed: "border-outline-green-1 bg-surface-green-2",
};

const day = ref(props.query.date || today());
const board = ref(null);
const notice = ref("");

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
		board.value = await frappeRequest({
			url: "healthcare.healthcare.doctype.ot_booking.board.get_board",
			params: { date: day.value },
			method: "GET",
		});
		notice.value = "";
	} catch (error) {
		notice.value = error?.messages?.join("\n") || error?.message || String(error);
	}
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

// Blocks share one grid cell, so the row grows to its tallest block
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

function minutesOf(value) {
	const [hours, minutes] = String(value).split(" ").pop().split(":");
	return Number(hours) * 60 + Number(minutes);
}

function clock(value) {
	const minutes = minutesOf(value);
	return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(
		minutes % 60,
	).padStart(2, "0")}`;
}

function today() {
	return isoDate(new Date());
}

function isoDate(date) {
	const offset = date.getTimezoneOffset() * 60000;
	return new Date(date - offset).toISOString().slice(0, 10);
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
		<div class="flex flex-wrap items-center gap-2">
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

		<p v-if="notice" class="rounded-3 bg-surface-red-2 p-3 text-sm text-ink-red-3">
			{{ notice }}
		</p>

		<div
			v-if="board?.away.length"
			class="flex flex-wrap items-center gap-2 text-sm"
		>
			<span class="text-ink-gray-5">Away today</span>
			<Badge v-for="row in board.away" :key="row.reference" theme="gray">
				{{ row.practitioner_name }} &middot; {{ row.reason }}
				<template v-if="row.from_time"
					>{{ clock(row.from_time) }}&ndash;{{ clock(row.to_time) }}</template
				>
			</Badge>
		</div>

		<p
			v-if="board && !board.complexes.length"
			class="p-8 text-center text-base text-ink-gray-5"
		>
			No operation theatres. Mark a Healthcare Service Unit Type as an OT to see
			its units here.
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
					<div class="relative grid min-h-16 min-w-[720px] flex-1 py-1">
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
								:title="`${
									booking.patient_name
								} · ${booking.procedures.join(', ')} · ${
									booking.status
								}`"
								@click="openBooking(booking.name)"
							>
								<p
									class="break-words text-sm font-medium text-ink-gray-9"
								>
									{{ booking.patient_name }}
								</p>
								<p class="break-words text-xs text-ink-gray-6">
									{{ clock(booking.scheduled_start) }}&ndash;{{
										clock(booking.scheduled_end)
									}}
									&middot; {{ booking.surgeon }}
								</p>
							</button>
						</template>
					</div>
				</div>
			</section>
		</div>
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
