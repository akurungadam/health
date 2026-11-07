<script setup>
// The surgical requests still waiting for a theatre. Drag one onto a theatre row to book it.
import { computed, ref } from "vue";
import { FormControl } from "frappe-ui";

import { patientFacts } from "./patient.js";

const props = defineProps({
	requests: { type: Array, default: () => [] },
});
const emit = defineEmits(["pick"]);

const search = ref("");

const shown = computed(() => {
	const text = search.value.trim().toLowerCase();
	if (!text) return props.requests;
	return props.requests.filter(request =>
		[
			request.patient_name,
			request.procedure,
			request.practitioner_name,
			request.name,
		]
			.join(" ")
			.toLowerCase()
			.includes(text),
	);
});

function minutes(seconds) {
	const total = Math.round((seconds || 0) / 60);
	return total >= 60 ? `${Math.floor(total / 60)}h ${total % 60}m` : `${total}m`;
}
</script>

<template>
	<aside class="flex w-72 shrink-0 flex-col gap-2 overflow-hidden">
		<p class="text-sm font-semibold text-ink-gray-7">
			To schedule ({{ requests.length }})
		</p>
		<FormControl
			v-model="search"
			placeholder="Search patient, procedure, surgeon"
		/>
		<p v-if="!shown.length" class="p-4 text-center text-sm text-ink-gray-5">
			{{
				requests.length ? "Nothing matches" : "Every surgical request is booked"
			}}
		</p>
		<ul class="flex flex-col gap-2 overflow-y-auto">
			<li
				v-for="request in shown"
				:key="request.name"
				draggable="true"
				class="cursor-grab rounded-4 border border-outline-gray-2 bg-surface-base p-2"
				@dragstart="emit('pick', request, $event)"
			>
				<p class="break-words text-sm font-medium text-ink-gray-9">
					{{ request.patient_name }}
					<span class="font-normal text-ink-gray-5">
						{{ patientFacts(request) }}
					</span>
				</p>
				<p class="break-words text-xs text-ink-gray-6">
					{{ request.procedure }}
				</p>
				<p class="text-xs text-ink-gray-5">
					{{ minutes(request.duration) }} &middot;
					{{ request.practitioner_name }} &middot;
					{{ request.order_date }}
				</p>
			</li>
		</ul>
	</aside>
</template>
