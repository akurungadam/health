<script setup>
// On a pane card, where the Auto Schedule preview places the case
defineProps({
	row: { type: Object, default: null },
});
</script>

<template>
	<p v-if="row" class="text-xs font-medium text-ink-green-7">
		Planned: {{ row.theatre_label }} {{ row.start }}&ndash;{{ row.end }}
	</p>
</template>
