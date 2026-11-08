<script setup>
// Narrowing the board to a practitioner, a patient or a theatre: the rest is dimmed, not hidden,
// so the free time around them still shows. The choices are the day's own.
import { computed } from "vue";
import { Button, FormControl } from "frappe-ui";

const props = defineProps({
	board: { type: Object, required: true },
});
const practitioner = defineModel("practitioner", { type: String, default: "" });
const patient = defineModel("patient", { type: String, default: "" });
const theatre = defineModel("theatre", { type: String, default: "" });

const practitioners = computed(() =>
	choices(
		props.board.bookings.flatMap(booking => booking.team_names || []),
		"All Practitioners",
	),
);
const patients = computed(() =>
	choices(
		props.board.bookings.map(booking => booking.patient_name),
		"All Patients",
	),
);
const theatres = computed(() => [
	{ label: "All Theatres", value: "" },
	...props.board.complexes.flatMap(group =>
		group.theatres.map(row => ({ label: row.label, value: row.name })),
	),
]);

function choices(names, all) {
	const unique = [...new Set(names.filter(Boolean))].sort();
	return [
		{ label: all, value: "" },
		...unique.map(name => ({ label: name, value: name })),
	];
}

function clear() {
	practitioner.value = patient.value = theatre.value = "";
}
</script>

<template>
	<div class="contents">
		<div class="w-48">
			<FormControl
				v-model="practitioner"
				type="select"
				:options="practitioners"
			/>
		</div>
		<div class="w-48">
			<FormControl v-model="patient" type="select" :options="patients" />
		</div>
		<div class="w-40">
			<FormControl v-model="theatre" type="select" :options="theatres" />
		</div>
		<Button
			v-if="practitioner || patient || theatre"
			variant="ghost"
			@click="clear"
		>
			Clear
		</Button>
	</div>
</template>
