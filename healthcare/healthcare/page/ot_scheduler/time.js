// Times and dates as the board reads and shows them. A time is minutes since midnight.

export function minutesOf(value) {
	const [hours, minutes] = String(value).split(" ").pop().split(":");
	return Number(hours) * 60 + Number(minutes);
}

export function clock(value) {
	const minutes = minutesOf(value);
	return `${twoDigits(Math.floor(minutes / 60))}:${twoDigits(minutes % 60)}`;
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
