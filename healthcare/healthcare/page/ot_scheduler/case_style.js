// How a case looks on the board. The case and its cleaning tail share one border, so the
// two read as one block: the status colour, or a thicker red one for an emergency.

const STATUS_BORDERS = {
	Tentative: "border border-dashed border-outline-gray-4",
	Scheduled: "border border-outline-blue-4",
	"In Progress": "border border-outline-amber-5",
	Completed: "border border-outline-green-5",
};

const STATUS_FILLS = {
	Tentative: "bg-surface-gray-2",
	Scheduled: "bg-surface-blue-2",
	"In Progress": "bg-surface-amber-2",
	Completed: "bg-surface-green-2",
};

export function caseBorder(booking) {
	return booking.is_emergency
		? "border-2 border-outline-red-3"
		: STATUS_BORDERS[booking.status];
}

export function caseFill(booking) {
	return STATUS_FILLS[booking.status];
}
