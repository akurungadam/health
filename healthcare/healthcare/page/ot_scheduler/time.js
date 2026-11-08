// Times and dates as the board reads and shows them. A time is minutes since midnight.

// the board always shows the whole day, midnight to midnight
export const DAY_MINUTES = 24 * 60;

// A position on the row, kept inside the day; a case running past midnight is cut there
export function span(start, end) {
	const inside = minutes => Math.min(Math.max(minutes, 0), DAY_MINUTES);
	const from = inside(start);
	const to = Math.max(inside(end < start ? DAY_MINUTES : end), from);
	return {
		left: `${(from / DAY_MINUTES) * 100}%`,
		width: `${((to - from) / DAY_MINUTES) * 100}%`,
	};
}

// Blocks share one grid cell, placed across it by time
export function placed(start, end) {
	const { left, width } = span(start, end);
	return { gridArea: "1 / 1", marginLeft: left, width };
}

// A case's length in minutes, from its full start and end, so one running past midnight counts
export function caseMinutes(booking) {
	const at = value => new Date(String(value).replace(" ", "T"));
	return (at(booking.scheduled_end) - at(booking.scheduled_start)) / 60000;
}

export function minutesOf(value) {
	const [hours, minutes] = String(value).split(" ").pop().split(":");
	return Number(hours) * 60 + Number(minutes);
}

export function clock(value) {
	const minutes = minutesOf(value);
	return `${twoDigits(Math.floor(minutes / 60))}:${twoDigits(minutes % 60)}`;
}

// Minutes since midnight before which `day` has passed: all of a past day, today up to one grid
// step (15 minutes) ago, as the server counts it, and none of a day still to come
export function pastUntil(day) {
	if (day < today()) return DAY_MINUTES;
	if (day > today()) return 0;
	const now = new Date();
	return now.getHours() * 60 + now.getMinutes() - 15;
}

export function twoDigits(number) {
	return String(number).padStart(2, "0");
}

export function today() {
	return isoDate(new Date());
}

export function isoDate(date) {
	const offset = date.getTimezoneOffset() * 60000;
	return new Date(date - offset).toISOString().slice(0, 10);
}
