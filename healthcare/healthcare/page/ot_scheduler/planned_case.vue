<script setup>
// A case the Auto Schedule plan would book, shown in its theatre's lane until the plan is booked
// or discarded
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
		<p class="truncate text-sm font-medium text-ink-gray-9">
			{{ row.patient_name }}
		</p>
		<p class="truncate text-xs text-ink-gray-7">{{ row.procedures }}</p>
		<p class="truncate text-xs text-ink-gray-6">
			{{ row.start }}&ndash;{{ row.end }}
		</p>
	</div>
</template>
