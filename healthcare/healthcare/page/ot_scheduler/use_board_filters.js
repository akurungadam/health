// The board's practitioner, patient and theatre filters (board_filters.vue): what they leave out
// is dimmed, not hidden, so the free time around the rest still shows.
import { ref } from "vue";

export function useBoardFilters() {
	const practitioner = ref("");
	const patient = ref("");
	const theatre = ref("");

	function caseDimmed(booking) {
		if (practitioner.value && !booking.team_names?.includes(practitioner.value))
			return true;
		if (patient.value && booking.patient_name !== patient.value) return true;
		return theatreDimmed(booking.theatre);
	}

	function theatreDimmed(name) {
		return Boolean(theatre.value) && name !== theatre.value;
	}

	return { practitioner, patient, theatre, caseDimmed, theatreDimmed };
}
