// Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

// apps/healthcare/healthcare/doctype/ot_schedule/ot_schedule.js

const JS_URL = "/assets/healthcare/js/ot_calendar/dist/app.js";
const CSS_URL = "/assets/healthcare/js/ot_calendar/dist/style.css";

async function ensureAssets() {
	const hasCss = Array.from(document.querySelectorAll('link[rel="stylesheet"]'))
		.some(l => (l.href || "").includes(CSS_URL));
	const hasJs = Array.from(document.scripts)
		.some(s => (s.src || "").includes(JS_URL));

	if (!hasCss) {
		await new Promise((res, rej) => {
			console.log("loading CSS");
			const l = document.createElement("link");
			l.rel = "stylesheet";
			l.href = CSS_URL;
			l.onload = res;
			l.onerror = rej;
			document.head.appendChild(l);
		});
	}

	if (!hasJs) {
		await new Promise((res, rej) => {
			const s = document.createElement("script");
			s.src = JS_URL;
			s.defer = true;
			s.onload = res;
			s.onerror = rej;
			document.head.appendChild(s);
		});
	}
}

async function mount(frm) {
	if (!frm || frm.is_new() || !frm.doc?.name) return;
	const w = frm.fields_dict?.entries_html?.wrapper;
	if (!w) return;

	if (!w.querySelector("#ot-calendar-root")) {
		w.innerHTML = '<div id="ot-calendar-root" style="min-height:540px"></div>';
	}

	await ensureAssets();

	if (window.OTCalendarMount) {
		window.OTCalendarMount({ el: '#ot-calendar-root', scheduleName: frm.doc.name, initialDate: frm.doc.schedule_date });
		// window.OTCalendarMount("#ot-calendar-root");
	}
}

frappe.ui.form.on('OT Schedule', {
	onload_post_render(frm) { mount(frm); },

	// Client Script: OT Schedule
	refresh: async function (frm) {
		mount(frm);

		if (frm.fields_dict.entries?.grid && !frm._lsr_btn_mounted) {
			frm._lsr_btn_mounted = true;
			frm.fields_dict["entries"].grid.wrapper.find('.grid-add-row').hide();
			frm.fields_dict["entries"].grid.clear_custom_buttons();
			frm.fields_dict.entries.grid.add_custom_button(
				__('Load Service Requests'),
				async function () {
					if (!frm.doc.schedule_date) {
						frappe.msgprint(__('Set Schedule Date first.'));
						return;
					}
					frappe.dom.freeze(__('Loading Service Requests…'));
					try {
						const r = await frappe.call({
							method: "healthcare.healthcare.doctype.ot_schedule.ot_schedule.load_service_requests",
							args: { doc: frm.doc },
							freeze: true
						});
						if (r && r.message) {
							frappe.show_alert({
								message: __(`Added ${r.message.added}, Skipped ${r.message.skipped} (SR total ${r.message.total})`),
								indicator: 'green'
							});
							await frm.reload_doc();
						}
					} catch (e) {
						console.error(e);
						frappe.msgprint(__('Failed to load Service Requests.'));
					} finally {
						frappe.dom.unfreeze();
					}
				}
			);
		}
	},

	validate(frm) {
		(frm.doc.entries || []).forEach(row => normalizeRowTime(frm, row.doctype, row.name));
	}
});

frappe.ui.form.on('OT Schedule Entry', {
	planned_start(frm, cdt, cdn) { normalizeRowTime(frm, cdt, cdn); },
	duration(frm, cdt, cdn) { normalizeRowTime(frm, cdt, cdn); }
});

// ---- helpers ----
const SNAP_STEP_MIN = 5; // hard 5-min snap

function normalizeRowTime(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row) return;

	if (row.planned_start) {
		const s = snap_to_step(row.planned_start, SNAP_STEP_MIN);
		if (s !== row.planned_start) {
			frappe.model.set_value(cdt, cdn, 'planned_start', s);
		}
	}

	const dur = toInt(row.duration);
	if (row.planned_start && dur > 0) {
		const raw_end = addMinutes(row.planned_start, dur);   // << was frappe.datetime.add_minutes
		const snapped = snap_to_step(raw_end, SNAP_STEP_MIN);
		frappe.model.set_value(cdt, cdn, 'planned_end', snapped);
	} else {
		frappe.model.set_value(cdt, cdn, 'planned_end', null);
	}
}
function snap_to_step(dt_str, step) {
	// prefer dayjs/moment if present
	if (window.dayjs) {
		const d = dayjs(dt_str, 'YYYY-MM-DD HH:mm:ss');
		if (d.isValid()) {
			const rem = d.minute() % step;
			const d2 = rem ? d.add(step - rem, 'minute') : d;
			return d2.second(0).format('YYYY-MM-DD HH:mm:ss');
		}
	}
	if (window.moment) {
		const m = moment(dt_str, 'YYYY-MM-DD HH:mm:ss', true);
		if (m.isValid()) {
			const rem = m.minutes() % step;
			if (rem) m.add(step - rem, 'minutes');
			return m.seconds(0).format('YYYY-MM-DD HH:mm:ss');
		}
	}
	// native fallback
	const d = parseLocal(dt_str);
	if (!d) return dt_str;
	const rem = d.getMinutes() % step;
	if (rem) d.setMinutes(d.getMinutes() + (step - rem));
	d.setSeconds(0, 0);
	return formatLocal(d);
}

function toInt(x) {
	const n = parseInt(x, 10);
	return isNaN(n) ? 0 : n;
}

function addMinutes(dtStr, minutes) {
	// tries dayjs -> moment -> native Date
	if (window.dayjs) {
		const d = dayjs(dtStr, 'YYYY-MM-DD HH:mm:ss');
		if (d.isValid()) return d.add(minutes, 'minute').second(0).format('YYYY-MM-DD HH:mm:ss');
	}
	if (window.moment) {
		const m = moment(dtStr, 'YYYY-MM-DD HH:mm:ss', true);
		if (m.isValid()) return m.add(minutes, 'minutes').seconds(0).format('YYYY-MM-DD HH:mm:ss');
	}
	// fallback: native Date; assumes local time, input "YYYY-MM-DD HH:mm:ss"
	const d2 = parseLocal(dtStr);
	if (!d2) return dtStr;
	d2.setMinutes(d2.getMinutes() + (parseInt(minutes, 10) || 0));
	d2.setSeconds(0, 0);
	return formatLocal(d2);
}

function parseLocal(dtStr) {
	// "YYYY-MM-DD HH:mm:ss" -> Date in local tz
	const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$/.exec(dtStr);
	if (!m) return null;
	const [_, Y, M, D, h, m2, s] = m.map(Number);
	return new Date(Y, M - 1, D, h, m2, s, 0);
}

function formatLocal(d) {
	const pad = (n) => String(n).padStart(2, '0');
	const Y = d.getFullYear();
	const M = pad(d.getMonth() + 1);
	const D = pad(d.getDate());
	const h = pad(d.getHours());
	const m = pad(d.getMinutes());
	const s = pad(d.getSeconds());
	return `${Y}-${M}-${D} ${h}:${m}:${s}`;
}
