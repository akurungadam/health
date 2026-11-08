<script setup>
// The board's hour labels, pinned while the day scrolls: across the top when theatres are
// rows, down the left when they are columns.
import { HOURS, span } from "./time.js";

defineProps({
	vertical: { type: Boolean, default: false },
});
</script>

<template>
	<div
		class="relative bg-surface-base"
		:class="
			vertical
				? 'sticky left-0 z-20 border-r border-outline-gray-2'
				: 'sticky top-0 z-20 h-8 border-b border-outline-gray-2'
		"
	>
		<span
			v-for="hour in HOURS.slice(0, -1)"
			:key="hour"
			class="absolute text-xs text-ink-gray-5"
			:class="vertical ? 'left-2 -translate-y-1/2' : 'top-2 -translate-x-1/2'"
			:style="span(hour * 60, hour * 60, vertical)"
		>
			{{ String(hour).padStart(2, "0") }}:00
		</span>
	</div>
</template>
