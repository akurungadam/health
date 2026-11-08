<script setup>
// The faint shading behind a theatre row for the hours outside the usual working day. The
// shades share the row's grid cell, below everything else in the row (which is isolated for
// it), so the row's blocks and cases are always drawn over them.
import { DAY_MINUTES } from "./time.js";

defineProps({
	workStart: { type: Number, required: true },
	workEnd: { type: Number, required: true },
	placed: { type: Function, required: true },
});
</script>

<template>
	<span
		v-for="[from, to] in [
			[0, workStart],
			[workEnd, DAY_MINUTES],
		]"
		:key="from"
		class="-z-10 bg-surface-gray-1 opacity-30"
		:style="placed(from, to)"
	/>
</template>
