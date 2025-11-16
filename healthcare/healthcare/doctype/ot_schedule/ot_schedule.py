# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import DocType
from frappe.utils import cint, get_datetime, getdate, now_datetime, time_diff_in_seconds


class OTSchedule(Document):
	def before_save(self):
		for entry in self.entries or []:
			self.set_duration_and_check_bounds(entry)
			self.set_patient_details(entry)
			self.set_practitioner_details(entry)

	def validate(self):
		if (self.status or "").strip().lower() == "locked":
			frappe.throw(_("This OT Schedule is Locked. Unlock to edit."))

		if not self.schedule_date:
			frappe.throw(_("Schedule Date is required."))

		self.validate_overlaps_qb()
		self.validate_units_are_ot()

	def set_patient_details(self, entry):
		if entry.patient:
			details = frappe.db.get_value(
				"Patient",
				entry.patient,
				["patient_name", "patient_age as age", "sex as gender", "mobile", "phone"],
				as_dict=True,
			)
			entry.patient_name = details.patient_name
			entry.patient_age = details.age
			entry.gender = details.gender
			entry.patient_contact = details.mobile if details.mobile else details.phone

	def set_practitioner_details(self, entry):
		if entry.primary_practitioner:
			details = frappe.db.get_value(
				"Healthcare Practitioner",
				entry.primary_practitioner,
				["practitioner_name", "mobile_phone as mobile", "office_phone as phone"],
				as_dict=True,
			)
			entry.primary_practitioner_name = details.practitioner_name
			entry.primary_pact_contact = details.mobile if details.mobile else details.phone

		if entry.secondary_practitioner:
			details = frappe.db.get_value(
				"Healthcare Practitioner",
				entry.secondary_practitioner,
				["practitioner_name", "mobile_phone as mobile", "office_phone as phone"],
				as_dict=True,
			)
			entry.secondary_practitioner_name = details.practitioner_name
			entry.secondary_pact_contact = details.mobile if details.mobile else details.phone

	def set_duration_and_check_bounds(self, entry):
		date_str = str(self.schedule_date)

		if not entry.planned_start or not entry.planned_end:
			frappe.throw(_(f"Entry #{entry.idx}: Planned Start & End are required."))

		start, end = (
			get_datetime(entry.planned_start),
			get_datetime(entry.planned_end),
		)
		if end <= start:
			frappe.throw(_(f"Entry #{entry.idx}: End must be after Start."))

		if str(start.date()) != date_str or str(end.date()) != date_str:
			frappe.throw(_(f"Entry #{entry.idx}: must be within {date_str}."))

		# use start/end
		entry.duration = max(1, cint(time_diff_in_seconds(end, start) // 60))

	def validate_overlaps_qb(self):
		"""Fail fast if any two entries in this schedule overlap on same lane OR same practitioner."""
		OSE = DocType("OT Schedule Entry")
		a = OSE.as_("a")
		b = OSE.as_("b")

		entries = (
			frappe.qb.from_(a)
			.join(b)
			.on((a.parent == b.parent) & (a.name < b.name))
			.select(
				a.idx.as_("a_idx"),
				b.idx.as_("b_idx"),
				a.service_unit.as_("a_su"),
				b.service_unit.as_("b_su"),
				a.primary_practitioner.as_("a_prac"),
				b.primary_practitioner.as_("b_prac"),
			)
			.where(a.parent == self.name)
			.where(
				a.planned_start.isnotnull()
				& a.planned_end.isnotnull()
				& b.planned_start.isnotnull()
				& b.planned_end.isnotnull()
			)
			.where((a.planned_start < b.planned_end) & (b.planned_start < a.planned_end))
			.where(
				((a.service_unit == b.service_unit) & a.service_unit.isnotnull() & b.service_unit.isnotnull())
				| (
					(a.primary_practitioner == b.primary_practitioner)
					& a.primary_practitioner.isnotnull()
					& b.primary_practitioner.isnotnull()
				)
			)
			.limit(1)
		).run(as_dict=True)

		if entries:
			entry = entries[0]
			if entry["a_su"] and entry["a_su"] == entry["b_su"]:
				frappe.throw(
					_("Overlap on Service Unit '{0}' between entries #{1} and #{2}.").format(
						entry["a_su"], entry["a_idx"], entry["b_idx"]
					)
				)
			else:
				frappe.throw(
					_("Overlap for Practitioner '{0}' between entries #{1} and #{2}.").format(
						entry["a_prac"], entry["a_idx"], entry["b_idx"]
					)
				)

	def validate_units_are_ot(self):
		"""Ensure every chosen unit is an OT (via service_unit_type='OT')."""
		for entry in self.entries or []:
			# if not entry.service_unit:
			# 	frappe.throw(_(f"Entry #{entry.idx}: Service Unit is required."))
			if entry.service_unit:
				is_ot = frappe.db.get_value("Healthcare Service Unit", entry.service_unit, "is_ot")
				if not is_ot:
					frappe.throw(_(f"Service Unit '{entry.service_unit}' is not of type 'Is OT'"))

	# Nice UX sugar; instance methods, idempotent
	@frappe.whitelist()
	def lock(self):
		if (self.status or "").strip().lower() != "locked":
			self.db_set("status", "Locked")

	@frappe.whitelist()
	def unlock(self):
		if (self.status or "").strip().lower() == "locked":
			self.db_set("status", "Draft")


def is_same_day(parent, start, end):
	d = str(parent.schedule_date)
	if str(start.date()) != d or str(end.date()) != d:
		frappe.throw(_("Times must be within {0}.").format(d))


def is_editable(parent, start):
	# not locked
	if (parent.status or "").strip().lower() == "locked":
		frappe.throw(_("Schedule is locked, cannot edit."))

	sched_day = getdate(parent.schedule_date)
	today = getdate()

	# past day
	if sched_day < today:
		frappe.throw(_("Past schedules are read-only."))

	# today: no moving into past time
	if sched_day == today and start < now_datetime():
		frappe.throw(_("Cannot schedule into the past for today."))


def has_overlap_conflict(row, start, end, target_su=None):
	"""
	Return one conflicting sibling (dict) or None.
	Conflicts when time-overlap AND (same lane|same practitioner|same patient).
	If target_su is provided, lane check uses that; else uses row.service_unit.
	"""
	OSE = DocType("OT Schedule Entry")
	t = OSE

	parts = []
	lane = target_su or row.service_unit
	if lane:
		parts.append(t.service_unit == lane)
	if row.primary_practitioner:
		parts.append(t.primary_practitioner == row.primary_practitioner)
	if row.patient:
		parts.append(t.patient == row.patient)

	if not parts:
		return None

	or_filter = parts[0]
	for p in parts[1:]:
		or_filter = or_filter | p

	entries = (
		frappe.qb.from_(t)
		.select(
			t.name,
			t.idx,
			t.service_unit,
			t.primary_practitioner,
			t.patient,
			t.planned_start,
			t.planned_end,
		)
		.where(t.parent == row.parent)
		.where(t.name != row.name)
		.where(t.planned_start.isnotnull() & t.planned_end.isnotnull())
		.where((t.planned_start < end) & (start < t.planned_end))
		.where(or_filter)
		.limit(1)
	).run(as_dict=True)

	return entries[0] if entries else None


def update_entry(entry_name, planned_start, planned_end, service_unit=None):
	"""Single core updater used by both update_entry_time and move_entry."""
	row = frappe.get_doc("OT Schedule Entry", entry_name)
	parent = frappe.get_doc("OT Schedule", row.parent)

	start, end = get_datetime(planned_start), get_datetime(planned_end)
	if end <= start:
		frappe.throw(_("End must be after Start."))

	is_same_day(parent, start, end)
	is_editable(parent, start)

	entry = has_overlap_conflict(row, start, end, target_su=service_unit)
	if entry:
		if (service_unit or row.service_unit) and entry.get("service_unit") == (
			service_unit or row.service_unit
		):
			frappe.throw(
				_("Overlap on OT '{0}' with entry {1}.").format(
					service_unit or row.service_unit, entry["name"]
				)
			)
		if row.primary_practitioner and entry.get("primary_practitioner") == row.primary_practitioner:
			frappe.throw(
				_("Overlap for practitioner '{0}' with entry {1}.").format(
					row.primary_practitioner, entry["name"]
				)
			)
		if row.patient and entry.get("patient") == row.patient:
			frappe.throw(
				_("Patient '{0}' already scheduled at this time (entry {1}).").format(
					row.patient, entry["name"]
				)
			)

	duration = max(1, cint(time_diff_in_seconds(end, start) // 60))
	updates = {
		"planned_start": planned_start,
		"planned_end": planned_end,
		"duration": duration,
	}
	if service_unit and service_unit != row.service_unit:
		updates["service_unit"] = service_unit

	row.db_set(updates)
	# 200 OK if no exception


@frappe.whitelist()
def reorder_entries(schedule_name):
	"""Re-sequence OT Schedule Entry rows for this schedule."""
	doc = frappe.get_doc("OT Schedule", schedule_name)

	lanes = {}
	for row in doc.entries or []:
		lanes.setdefault(row.service_unit, []).append(row)

	ordered = []
	for lane_key in sorted(lanes.keys(), key=lambda start: str(start)):
		block = lanes[lane_key]
		block.sort(
			key=lambda r: get_datetime(r.planned_start)
			if r.planned_start
			else get_datetime("1900-01-01 00:00:00")
		)
		ordered.extend(block)

	for i, row in enumerate(ordered, start=1):
		frappe.db.set_value("OT Schedule Entry", row.name, "idx", i, update_modified=False)


@frappe.whitelist()
def get_schedule_entries(schedule_name):
	"""(kept as-is) payload for calendar from this document only."""
	doc = frappe.get_doc("OT Schedule", schedule_name)
	entries = []
	for entry in doc.entries or []:
		title = " — ".join([x for x in [entry.patient, entry.procedure] if x]) + (
			" (F)" if entry.fasting_required else ""
		)
		entries.append(
			{
				"name": entry.name,
				"patient": entry.patient,
				"patient_name": entry.name,
				"patient_age": entry.age,
				"patient_gender": entry.gender,
				"patient_contact": entry.patient_contact,
				"procedure": entry.procedure,
				"template": entry.template,
				"service_request": entry.service_request,
				"service_unit": entry.service_unit,
				"service_unit_type": entry.service_unit_type,
				"primary_practitioner": entry.primary_practitioner,
				"practitioner_name": entry.primary_practitioner_name,
				"practitioner_contact": entry.primary_pact_contact,
				"secondary_practitioner": entry.secondary_practitioner,
				"priority": entry.priority,
				"fasting_required": int(entry.fasting_required or 0),
				"status": entry.status,
				"planned_start": entry.planned_start,
				"planned_end": entry.planned_end,
				"duration": entry.duration or 0,
				"color": entry.color,
				"title": title,
			}
		)
	return {
		"schedule_date": str(doc.schedule_date),
		"mode": doc.mode,
		"ot_type": doc.ot_type,
		"allow_emergency_inserts": int(doc.allow_emergency_inserts or 0),
		"entries": entries,
	}


@frappe.whitelist()
def update_entry_time(entry_name, planned_start, planned_end, service_unit=None):
	"""Time-only update (frontend legacy). Uses the unified updater."""
	update_entry(entry_name, planned_start, planned_end, service_unit=service_unit)


@frappe.whitelist()
def move_entry(entry_name, planned_start, planned_end, service_unit=None):
	"""Time + (optional) lane update. Uses the same unified updater."""
	update_entry(entry_name, planned_start, planned_end, service_unit=service_unit)


def overlaps_day_window(start_dt, end_dt, day_str):
	day_start = get_datetime(f"{day_str} 00:00:00")
	day_end = get_datetime(f"{day_str} 23:59:59")
	return max(start_dt, day_start) < min(end_dt, day_end)


def get_event(entry, sr_status_map=None):
	patient = entry.get("patient")
	procedure = entry.get("procedure")
	fasting = entry.get("fasting_required")
	service_req = entry.get("service_request")

	# title
	title = " — ".join([x for x in [patient, procedure] if x]) or ""
	if int(fasting or 0):
		title = (title + " (F)").strip() if title else "(F)"

	return {
		"id": entry["name"],
		"kind": "ENTRY",
		"resourceId": entry.get("service_unit") or "Unassigned",
		"start": entry.get("planned_start"),
		"end": entry.get("planned_end"),
		"service_request": service_req,
		"patient": patient,
		"patient_name": entry.get("patient_name", ""),
		"patient_age": entry.get("age", ""),
		"patient_gender": entry.get("gender", ""),
		"patient_contact": entry.get("patient_contact", ""),
		"procedure": procedure,
		"template": entry.get("template"),
		"service_unit": entry.get("service_unit"),
		"service_unit_type": entry.get("service_unit_type", ""),
		"primary_practitioner": entry.get("primary_practitioner"),
		"practitioner_name": entry.get("primary_practitioner_name", ""),
		"practitioner_contact": entry.get("primary_pact_contact", ""),
		"secondary_practitioner": entry.get("secondary_practitioner"),
		"priority": entry.get("priority"),
		"fasting_required": int(fasting or 0),
		"status": entry.get("status"),
		"sr_status": (sr_status_map or {}).get(service_req) if sr_status_map is not None else None,
		"duration": entry.get("duration") or 0,
		"color": entry.get("color"),
		"title": title,
	}


@frappe.whitelist()
def get_day_events(schedule_name, date):
	"""Day's events either from this doc (editable) or from other schedules (read-only)."""
	doc = frappe.get_doc("OT Schedule", schedule_name)
	day = str(getdate(date))
	sched_day = str(getdate(doc.schedule_date))
	today = str(getdate())

	# branch 1: this schedule (editable rules apply)
	if day == sched_day:
		events = []
		for entry in doc.entries or []:
			if not entry.planned_start or not entry.planned_end:
				continue
			try:
				s, e = get_datetime(entry.planned_start), get_datetime(entry.planned_end)
			except Exception:
				continue
			if not overlaps_day_window(s, e, day):
				continue
			events.append(get_event(entry.as_dict()))

		locked = (doc.status or "").strip().lower() == "locked"
		can_edit = int(sched_day >= today and not locked)
		return {"date": day, "source": "schedule", "can_edit": can_edit, "events": events}

	ot_schedules = frappe.get_all("OT Schedule", filters={"schedule_date": day}, pluck="name")
	if not ot_schedules:
		return {"date": day, "source": "ot_entries", "can_edit": 0, "events": []}

	entries = frappe.get_all(
		"OT Schedule Entry",
		filters={"parent": ["in", ot_schedules]},
		fields=[
			"name",
			"patient",
			"procedure",
			"service_request",
			"service_unit",
			"primary_practitioner",
			"secondary_practitioner",
			"priority",
			"fasting_required",
			"status",
			"planned_start",
			"planned_end",
			"duration",
			"group_id",
			"color",
			"notes",
			"patient_name",
			"age",
			"gender",
			"patient_contact",
			"primary_practitioner_name",
			"primary_pact_contact",
			"service_unit_type",
		],
	)

	sr_status_map = {}
	names = [entry["service_request"] for entry in entries if entry.get("service_request")]
	if names:
		for sr in frappe.get_all(
			"Service Request", filters={"name": ["in", list(set(names))]}, fields=["name", "status"]
		):
			sr_status_map[sr["name"]] = sr.get("status")

	events = []
	for entry in entries:
		ps, pe = entry.get("planned_start"), entry.get("planned_end")
		if not ps or not pe:
			continue
		s, e = get_datetime(ps), get_datetime(pe)
		if not overlaps_day_window(s, e, day):
			continue
		events.append(get_event(entry, sr_status_map=sr_status_map))

	return {"date": day, "source": "ot_entries", "can_edit": 0, "events": events}


# ---- config ----
TEMPLATE_DURATION_KEYS = [
	"default_duration_min",
	"duration_min",
	"expected_duration_min",
	"duration",
	"expected_duration",
]
CHILD_TABLE_FIELDNAME = "entries"
DT_FMT = "%Y-%m-%d %H:%M:%S"
SNAP_MINUTE_STEP = 5
DEFAULT_DURATION_MIN = 60


@frappe.whitelist()
def load_service_requests(doc):
	# normalize incoming doc (string or dict) -> Document
	if isinstance(doc, str):
		doc = json.loads(doc)
	if isinstance(doc, dict):
		doc = frappe.get_doc(doc)  # now a real Document

	_guard_locked(doc)
	if not doc.schedule_date:
		frappe.throw(_("Schedule Date is required."))

	# day window (snap hard to 5 min)
	start_hour = cint(getattr(doc, "start_hour", 6) or 6)
	end_hour = cint(getattr(doc, "end_hour", 22) or 22)
	turnaround = cint(getattr(doc, "turnaround_minutes", 10) or 10)

	day = getdate(doc.schedule_date)
	day_start = datetime.combine(day, time(hour=start_hour, minute=0, second=0))
	day_end = datetime.combine(day, time(hour=end_hour, minute=0, second=0))

	# dedupe existing SRs
	existing = set()
	for row in doc.get(CHILD_TABLE_FIELDNAME) or []:
		if row.service_request:
			existing.add(row.service_request)

	# fetch SRs for the date (only Clinical Procedure Template)
	print(f"fetching for date: {day.strftime('%Y-%m-%d')}")
	srs = frappe.get_all(
		"Service Request",
		filters={
			"expected_date": day.strftime("%Y-%m-%d"),
			"template_dt": "Clinical Procedure Template",
		},
		fields=[
			"name",
			"status as sr_status",
			"referred_to_practitioner",  # per schema
			"patient",
			"title",
			"template_dt",
			"template_dn",
			"healthcare_service_unit_type",
			"fasting_required",
			"creation",
		],
		order_by="creation asc",
	)

	work = []
	added, skipped = 0, 0
	print(f"srs: {len(srs)}")

	for sr in srs:
		name = sr.get("name")
		if name in existing:
			skipped += 1
			continue

		dur = frappe.db.get_value(sr.get("template_dt"), sr.get("template_dn"), "duration")
		if not cint(dur):
			dur = DEFAULT_DURATION_MIN

		work.append(
			{
				"name": name,
				"sr_status": (sr.get("sr_status") or None),
				"patient": sr.get("patient") or None,
				"referred_to_practitioner": sr.get("referred_to_practitioner") or None,
				"title": sr.get("title") or None,
				"template_dt": sr.get("template_dt") or None,
				"template_dn": sr.get("template_dn") or None,
				"service_unit_type": sr.get("healthcare_service_unit_type") or None,
				"fasting_required": cint(sr.get("fasting_required") or 0),
				"duration": cint(dur or 0),
				"creation": sr.get("creation"),
			}
		)

	# fasting → patient → practitioner → creation

	work.sort(
		key=lambda x: (
			0 if cint(x.get("fasting_required") or 0) else 1,
			(x.get("patient") or "").strip(),
			(x.get("practitioner") or "").strip(),
			x.get("creation"),
		)
	)

	cursor = snap_up(day_start, SNAP_MINUTE_STEP)

	for item in work:
		if cursor >= day_end:
			skipped += 1
			continue

		start_dt = cursor
		dur_min = cint(item.get("duration") or 0)
		end_dt = snap_up(start_dt + timedelta(minutes=dur_min), SNAP_MINUTE_STEP)

		if end_dt > day_end:
			skipped += 1
			continue

		# append child — UNASSIGNED
		child = doc.append(CHILD_TABLE_FIELDNAME, {})
		child.service_request = item["name"]
		child.sr_status = item["sr_status"]
		child.patient = item["patient"]
		child.primary_practitioner = item["referred_to_practitioner"]
		child.template = item["template_dn"]
		# child.procedure = item["title"]
		child.fasting_required = item["fasting_required"]
		child.duration = dur_min
		child.service_unit = None
		child.service_unit_type = item["service_unit_type"]

		child.planned_start = start_dt.strftime(DT_FMT)
		child.planned_end = end_dt.strftime(DT_FMT)

		added += 1
		existing.add(item["name"])

		cursor = snap_up(end_dt + timedelta(minutes=turnaround), SNAP_MINUTE_STEP)

	doc.save(ignore_permissions=True)
	doc.notify_update()
	return {
		"added": added,
		"skipped": skipped,
		"total": len(srs),
		"rows": len(doc.get(CHILD_TABLE_FIELDNAME) or []),
	}


# --- helpers ---
def _guard_locked(doc):
	if cint(getattr(doc, "is_locked", 0)):
		frappe.throw(_("This Schedule is locked."))


def snap_up(dt, step):
	if step <= 1:
		return dt
	dt = dt.replace(second=0, microsecond=0)
	rem = dt.minute % step
	if rem == 0:
		return dt
	return dt + timedelta(minutes=(step - rem))


CHILD_UNITS_FIELD = "service_units"  # child table on OT Schedule that stores units
HSU_DTYPE = "Healthcare Service Unit"
HSU_IS_OT_FIELD = "is_ot"


@frappe.whitelist()
def list_service_units_is_ot():
	"""Return Healthcare Service Units where is_ot = 1."""
	units = frappe.get_all(
		HSU_DTYPE,
		filters={HSU_IS_OT_FIELD: 1},
		fields=["name", "healthcare_service_unit_name as title", "service_unit_type"],
		order_by="healthcare_service_unit_name asc",
	)
	return {"count": len(units), "items": units}


@frappe.whitelist()
def add_service_units(schedule_name, unit_names):
	"""
	Append OT units (no duplicates) to the schedule's child table.
	Expects the child row to have a field named 'service_unit'.
	"""
	if isinstance(unit_names, str):
		try:
			unit_names = json.loads(unit_names)
		except Exception:
			unit_names = [unit_names]

	sched = frappe.get_doc("OT Schedule", schedule_name)
	_guard_locked(sched)

	existing = {
		r.service_unit for r in (sched.get(CHILD_UNITS_FIELD) or []) if getattr(r, "service_unit", None)
	}
	added, skipped = 0, 0

	for name in unit_names or []:
		if name in existing:
			skipped += 1
			continue
		row = sched.append(CHILD_UNITS_FIELD, {})
		row.service_unit = name
		added += 1
		existing.add(name)

	sched.save(ignore_permissions=True)
	return {"added": added, "skipped": skipped, "rows": len(sched.get(CHILD_UNITS_FIELD) or [])}


@frappe.whitelist()
def delete_entry(entry_name):
	"""
	Delete one OT Schedule Entry row from its parent child table and save the parent.
	Returns {deleted:1,parent:<name>,rows:<count>} on success.
	"""
	if not entry_name:
		frappe.throw(_("Missing entry_name"))

	meta = frappe.get_value(
		"OT Schedule Entry",
		entry_name,
		["parent", "parenttype", "parentfield"],
		as_dict=True,
	)

	if not meta or not meta.parent:
		frappe.throw(_("Entry not found or already removed."))

	parent = frappe.get_doc(meta.parenttype, meta.parent)

	# optional: locked guard (same guard you use elsewhere)
	if cint(getattr(parent, "is_locked", 0)):
		frappe.throw(_("This Schedule is locked."))

	# prune the child row from the table
	rows = parent.get("entries") or []
	parent.set("entries", [r for r in rows if r.name != entry_name])

	# saving will take care of deleting the child row
	parent.save(ignore_permissions=True)

	return {
		"deleted": 1,
		"parent": parent.name,
		"rows": len(parent.get(meta.parentfield or CHILD_TABLE_FIELDNAME) or []),
	}
