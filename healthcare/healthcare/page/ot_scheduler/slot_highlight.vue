<script setup>
// A picked slot on its theatre row: the case and its cleaning time outlined in green, with
// Book here, and a way to let the slot go.
import { computed } from "vue";

import { clock } from "./time.js";

const props = defineProps({
	place: { type: Object, required: true },
	gap: { type: Object, required: true },
});
const emit = defineEmits(["book", "clear"]);
const time = computed(() => `${clock(props.gap.start)}–${clock(props.gap.end)}`);
</script>

<template>
	<div
		class="z-10 flex items-center gap-1 overflow-hidden rounded-4 border-2 border-dashed border-outline-green-5 bg-surface-green-2 px-1"
		:style="place"
		:title="`${time} fits, with cleaning`"
	>
		<button
			class="shrink-0 rounded-3 bg-surface-gray-9 px-2 py-1 text-xs text-ink-white"
			@click="emit('book')"
		>
			Book here
		</button>
		<button
			class="shrink-0 rounded-3 px-1 text-xs text-ink-gray-7"
			aria-label="Clear the picked slot"
			@click="emit('clear')"
		>
			✕
		</button>
	</div>
</template>
