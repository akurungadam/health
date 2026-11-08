<script setup>
// A case the Auto Schedule plan would book, shown in its theatre's lane until the plan is booked
// or discarded
import OtherCases from "./other_cases.vue";

defineProps({
	row: { type: Object, required: true },
	place: { type: Object, required: true },
});
</script>

<template>
	<div
		class="pointer-events-none z-10 overflow-hidden rounded-4 border-2 border-dashed border-outline-green-5 bg-surface-green-2 px-2 py-1"
		:style="place"
		:title="`${row.patient_name} · ${row.procedures} · ${row.start}–${row.end}`"
	>
		<div class="flex items-start gap-1">
			<p class="min-w-0 flex-1 truncate text-sm font-medium text-ink-gray-9">
				{{ row.patient_name }}
			</p>
			<OtherCases :cases="row.other_cases" />
		</div>
		<p class="truncate text-xs text-ink-gray-7">{{ row.procedures }}</p>
		<p class="truncate text-xs text-ink-gray-6">
			{{ row.start }}&ndash;{{ row.end }}
		</p>
	</div>
</template>
