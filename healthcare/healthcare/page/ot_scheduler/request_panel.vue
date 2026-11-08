<script setup>
// The cases still waiting for a theatre: open surgical requests, and postponed cases.
// Drag one onto a theatre row to book it. Drop a booked case here to postpone it.
import { computed, ref } from "vue";
import { Badge, FormControl } from "frappe-ui";
import { useHost } from "@framework/ui/island";

import { priorityBorder, priorityTheme } from "./case_style.js";
import FinderButton from "./finder_button.vue";
import PlannedLine from "./planned_line.vue";
import { patientFacts } from "./patient.js";
import SlotList from "./slot_list.vue";
import { caseMinutes, today } from "./time.js";

const props = defineProps({
	requests: { type: Array, default: () => [] },
	postponed: { type: Array, default: () => [] },
	// a booked case is being dragged, so the pane offers to take it
	dropping: { type: Boolean, default: false },
	// the slot finder: which card it is open on and what it found (use_slots.js)
	finder: { type: Object, required: true },
	picked: { type: Object, default: null },
	// the cases an Auto Schedule preview places, by name (use_auto_schedule.js)
	planned: { type: Object, default: () => ({}) },
});
const emit = defineEmits([
	"pick",
	"pickPostponed",
	"unschedule",
	"over",
	"done",
	"find",
	"pickSlot",
]);

const host = useHost();
const search = ref("");
const over = ref(false);

const shownRequests = computed(() =>
	matching(props.requests, request => [request.procedure, request.practitioner_name]),
);
const shownPostponed = computed(() =>
	matching(props.postponed, booking => [...booking.procedures, booking.surgeon]),
);

function matching(rows, details) {
	const text = search.value.trim().toLowerCase();
	if (!text) return rows;
	return rows.filter(row =>
		[row.patient_name, row.name, ...details(row)]
			.join(" ")
			.toLowerCase()
			.includes(text),
	);
}

function minutes(seconds) {
	const total = Math.round((seconds || 0) / 60);
	return total >= 60 ? `${Math.floor(total / 60)}h ${total % 60}m` : `${total}m`;
}

function length(booking) {
	return caseMinutes(booking) * 60;
}

// a date as desk prints a Date field, in the date format of System Settings
function formatDate(value) {
	return host.format?.(value, { fieldtype: "Date" }) ?? value;
}

// an Expected By date already gone is shown in red
function isPast(date) {
	return String(date) < today();
}

// a case the Auto Schedule preview places is outlined in green, as its card on the board is
function cardBorder(row) {
	return props.planned[row.name]
		? "border-2 border-outline-green-5"
		: priorityBorder(row);
}

function drop() {
	over.value = false;
	emit("unschedule");
}
</script>

<template>
	<aside
		class="flex w-72 shrink-0 flex-col gap-2 overflow-hidden rounded-4 border-2 border-dashed"
		:class="dropping ? 'border-outline-gray-3 p-1' : 'border-transparent'"
		@dragover.prevent="
			over = dropping;
			emit('over');
		"
		@dragleave="over = false"
		@drop.prevent="drop"
	>
		<p class="text-sm font-semibold text-ink-gray-7">
			To schedule ({{ requests.length + postponed.length }})
		</p>
		<p
			v-if="dropping"
			class="rounded-4 p-3 text-center text-sm text-ink-gray-6"
			:class="over ? 'bg-surface-gray-3' : 'bg-surface-gray-1'"
		>
			Drop here to reschedule the case
		</p>
		<FormControl
			v-model="search"
			placeholder="Search patient, procedure, surgeon"
		/>
		<div class="flex flex-col gap-2 overflow-y-auto">
			<p
				v-if="!shownRequests.length && !shownPostponed.length"
				class="p-4 text-center text-sm text-ink-gray-5"
			>
				{{ search ? "Nothing matches" : "Every surgical request is booked" }}
			</p>
			<div
				v-for="request in shownRequests"
				:key="request.name"
				draggable="true"
				class="cursor-grab rounded-4 bg-surface-base p-2"
				:class="cardBorder(request)"
				@dragstart="emit('pick', request, $event)"
				@dragend="emit('done')"
			>
				<p
					class="flex items-start justify-between gap-2 break-words text-sm font-medium text-ink-gray-9"
				>
					<span>
						{{ request.patient_name }}
						<span class="font-normal text-ink-gray-5">{{
							patientFacts(request)
						}}</span>
					</span>
					<Badge
						v-if="request.priority_label"
						class="ml-auto shrink-0"
						:theme="priorityTheme(request)"
					>
						{{ request.priority_label }}
					</Badge>
					<FinderButton
						:open="finder.for === request.name"
						@click="emit('find', { request })"
					/>
				</p>
				<p class="break-words text-xs text-ink-gray-6">
					{{ request.procedure }}
					<span v-if="request.theatre_type" class="text-ink-gray-5">
						&middot; {{ request.theatre_type }}
					</span>
				</p>
				<p class="text-xs text-ink-gray-5">
					{{ minutes(request.duration) }} &middot;
					{{ request.practitioner_name }} &middot; Ordered
					{{ formatDate(request.order_date) }}
				</p>
				<p
					v-if="request.expected_date"
					class="text-xs"
					:class="
						isPast(request.expected_date)
							? 'text-ink-red-7'
							: 'text-ink-gray-6'
					"
				>
					Expected by {{ formatDate(request.expected_date) }}
				</p>
				<PlannedLine :row="planned[request.name]" />
				<SlotList
					v-if="finder.for === request.name"
					class="mt-2"
					:finder="finder"
					:picked="picked"
					@pick="slot => emit('pickSlot', slot)"
				/>
			</div>

			<p
				v-if="shownPostponed.length"
				class="pt-2 text-sm font-semibold text-ink-gray-7"
			>
				To reschedule ({{ shownPostponed.length }})
			</p>
			<div
				v-for="booking in shownPostponed"
				:key="booking.name"
				draggable="true"
				class="cursor-grab rounded-4 border-dashed bg-surface-base p-2"
				:class="cardBorder(booking)"
				@dragstart="emit('pickPostponed', booking, $event)"
				@dragend="emit('done')"
			>
				<p
					class="flex items-start justify-between gap-2 break-words text-sm font-medium text-ink-gray-9"
				>
					<span>
						{{ booking.patient_name }}
						<span class="font-normal text-ink-gray-5">{{
							patientFacts(booking)
						}}</span>
					</span>
					<Badge
						v-if="booking.priority_label"
						class="ml-auto shrink-0"
						:theme="priorityTheme(booking)"
					>
						{{ booking.priority_label }}
					</Badge>
					<FinderButton
						:open="finder.for === booking.name"
						@click="emit('find', { booking })"
					/>
				</p>
				<p class="break-words text-xs text-ink-gray-6">
					{{ booking.procedures.join(", ") }}
					<span v-if="booking.theatre_type" class="text-ink-gray-5">
						&middot; {{ booking.theatre_type }}
					</span>
				</p>
				<p class="text-xs text-ink-gray-5">
					{{ minutes(length(booking)) }} &middot;
					{{ booking.surgeon }} &middot;
					{{ booking.name }}
				</p>
				<PlannedLine :row="planned[booking.name]" />
				<SlotList
					v-if="finder.for === booking.name"
					class="mt-2"
					:finder="finder"
					:picked="picked"
					@pick="slot => emit('pickSlot', slot)"
				/>
			</div>
		</div>
	</aside>
</template>
