<script setup>
// The cases still waiting for a theatre: open surgical requests, and postponed cases.
// Drag one onto a theatre row to book it. Drop a booked case here to postpone it.
import { computed, ref } from "vue";
import { FormControl } from "frappe-ui";

import { patientFacts } from "./patient.js";

const props = defineProps({
	requests: { type: Array, default: () => [] },
	postponed: { type: Array, default: () => [] },
	// a booked case is being dragged, so the pane offers to take it
	dropping: { type: Boolean, default: false },
});
const emit = defineEmits(["pick", "pickPostponed", "unschedule", "done"]);

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
	const at = value => new Date(String(value).replace(" ", "T"));
	return (at(booking.scheduled_end) - at(booking.scheduled_start)) / 1000;
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
		@dragover.prevent="over = dropping"
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
			Drop here to postpone the case
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
				class="cursor-grab rounded-4 border border-outline-gray-2 bg-surface-base p-2"
				@dragstart="emit('pick', request, $event)"
				@dragend="emit('done')"
			>
				<p class="break-words text-sm font-medium text-ink-gray-9">
					{{ request.patient_name }}
					<span class="font-normal text-ink-gray-5">{{
						patientFacts(request)
					}}</span>
				</p>
				<p class="break-words text-xs text-ink-gray-6">
					{{ request.procedure }}
				</p>
				<p class="text-xs text-ink-gray-5">
					{{ minutes(request.duration) }} &middot;
					{{ request.practitioner_name }} &middot;
					{{ request.order_date }}
				</p>
			</div>

			<p
				v-if="shownPostponed.length"
				class="pt-2 text-sm font-semibold text-ink-gray-7"
			>
				Postponed ({{ shownPostponed.length }})
			</p>
			<div
				v-for="booking in shownPostponed"
				:key="booking.name"
				draggable="true"
				class="cursor-grab rounded-4 border border-dashed border-outline-gray-3 bg-surface-base p-2"
				@dragstart="emit('pickPostponed', booking, $event)"
				@dragend="emit('done')"
			>
				<p class="break-words text-sm font-medium text-ink-gray-9">
					{{ booking.patient_name }}
					<span class="font-normal text-ink-gray-5">{{
						patientFacts(booking)
					}}</span>
				</p>
				<p class="break-words text-xs text-ink-gray-6">
					{{ booking.procedures.join(", ") }}
				</p>
				<p class="text-xs text-ink-gray-5">
					{{ minutes(length(booking)) }} &middot;
					{{ booking.surgeon }} &middot;
					{{ booking.name }}
				</p>
			</div>
		</div>
	</aside>
</template>
