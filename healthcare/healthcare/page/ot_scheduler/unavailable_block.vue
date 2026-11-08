<script setup>
// A theatre's unavailable time on its row: hatched, saying why (its reason, then its note),
// with the full details on hover. A block with neither falls back to its title.
import { computed } from "vue";
import { Tooltip } from "frappe-ui";

import { clock } from "./time.js";

const props = defineProps({
	block: { type: Object, required: true },
	place: { type: Object, required: true },
	// no tooltip while the board scrolls
	quiet: { type: Boolean, default: false },
});

const why = computed(() => props.block.reason || "Unavailable");
const hasDetails = computed(() => props.block.reason || props.block.note);
const time = computed(
	() => `${clock(props.block.start_time)}–${clock(props.block.end_time)}`,
);
</script>

<template>
	<Tooltip :disabled="quiet">
		<div
			class="ot-hatch overflow-hidden rounded-4 bg-surface-red-1 px-2 py-1"
			:style="place"
		>
			<p v-if="hasDetails" class="truncate text-xs text-ink-red-7">
				<span class="font-medium">{{ why }}</span>
				<span v-if="block.note"> · {{ block.note }}</span>
			</p>
			<p v-else class="truncate text-xs font-medium text-ink-red-7">
				{{ block.title }}
			</p>
		</div>
		<template #content>
			<div class="flex max-w-64 flex-col gap-0.5 text-xs">
				<p class="font-medium">{{ why }} · {{ time }}</p>
				<p v-if="block.note" class="whitespace-pre-line">{{ block.note }}</p>
				<p class="opacity-70">{{ block.title }}</p>
			</div>
		</template>
	</Tooltip>
</template>
