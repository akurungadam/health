<script setup>
// The bar above the board while an Auto Schedule plan is shown in the lanes: how many cases it
// places, the ones that do not fit and why, and Book or Discard.
import { Button } from "frappe-ui";

import { plainText } from "./use_auto_schedule.js";

defineProps({
	plan: { type: Object, required: true },
	busy: { type: Boolean, default: false },
});
const emit = defineEmits(["book", "discard"]);
</script>

<template>
	<div
		class="flex shrink-0 flex-col gap-2 rounded-4 border border-dashed border-outline-green-5 bg-surface-green-1 p-3 text-sm"
	>
		<div class="flex flex-wrap items-center gap-2">
			<p class="font-medium text-ink-gray-9">
				Auto schedule preview: {{ plan.placed.length }} case(s) placed, shown in
				green
			</p>
			<p class="text-ink-gray-6">
				STAT, ASAP and Urgent cases, and Routine ones due by this day, each in
				the earliest free time in working hours, as Tentative
			</p>
			<div class="ml-auto flex gap-2">
				<Button :disabled="busy" @click="emit('discard')">Discard</Button>
				<Button
					variant="solid"
					:disabled="busy || !plan.placed.length"
					@click="emit('book')"
				>
					Book {{ plan.placed.length }} case(s)
				</Button>
			</div>
		</div>
		<p
			v-if="!plan.placed.length && !plan.not_placed.length"
			class="text-ink-gray-6"
		>
			No waiting case is pressing or due by this day.
		</p>
		<ul v-if="plan.not_placed.length" class="flex flex-col gap-0.5 text-ink-gray-6">
			<li v-for="row in plan.not_placed" :key="row.name">
				Not placed:
				<span class="font-medium text-ink-gray-8">{{ row.patient_name }}</span>
				&middot; {{ row.procedures }}: {{ plainText(row.reason) }}
			</li>
		</ul>
	</div>
</template>
