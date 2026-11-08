# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

"""The day's schedule as a sheet: theatre by theatre, or practitioner by practitioner, for the
board's company and department and the cases its practitioner, patient and theatre filters leave
clear, for the board to print."""

import frappe
from frappe import _
from frappe.utils import format_date, get_datetime

from healthcare.healthcare.doctype.ot_booking.board import get_board

TEMPLATE = "healthcare/healthcare/doctype/ot_booking/day_sheet.html"


@frappe.whitelist()
def get_day_sheet(
	date: str,
	company: str | None = None,
	department: str | None = None,
	mode: str = "theatre",
	practitioner: str | None = None,
	patient: str | None = None,
	theatre: str | None = None,
) -> str:
	sheet = DaySheet(date, company, department, mode, practitioner, patient, theatre)
	return sheet.html()


class DaySheet:
	def __init__(self, date, company, department, mode, practitioner, patient, theatre):
		self.board = get_board(date, company, department)  # checks the caller may read the board
		self.department = department
		self.mode = "practitioner" if mode == "practitioner" else "theatre"
		self.practitioner, self.patient, self.theatre = practitioner, patient, theatre
		self.cases = sorted(
			(booking for booking in self.board["bookings"] if self.shown(booking)),
			key=lambda booking: get_datetime(booking.scheduled_start),
		)

	def shown(self, booking):
		"""As the board's filters leave it clear"""
		if self.practitioner and self.practitioner not in booking.team_names:
			return False
		if self.patient and booking.patient_name != self.patient:
			return False
		return not self.theatre or booking.theatre == self.theatre

	def title(self):
		by = _("Practitioner") if self.mode == "practitioner" else _("Theatre")
		where = " · ".join(filter(None, [self.board["company"], self.department]))
		return _("OT Schedule by {0} · {1} · {2}").format(by, format_date(self.board["date"]), where)

	def html(self):
		sections = self.by_practitioner() if self.mode == "practitioner" else self.by_theatre()
		context = {"title": self.title(), "sections": sections, "mode": self.mode}
		return frappe.render_template(TEMPLATE, context)

	def by_theatre(self):
		theatres = [theatre for group in self.board["complexes"] for theatre in group["theatres"]]
		sections = [
			{
				"heading": " · ".join(filter(None, [theatre.label, theatre.service_unit_type])),
				"cases": [self.row(case) for case in self.cases if case.theatre == theatre.name],
			}
			for theatre in theatres
		]
		return [section for section in sections if section["cases"]]

	def by_practitioner(self):
		names = sorted({name for case in self.cases for name in case.team_names})
		if self.practitioner:
			names = [name for name in names if name == self.practitioner]
		return [
			{
				"heading": name,
				"cases": [self.row(case, name) for case in self.cases if name in case.team_names],
			}
			for name in names
		]

	def row(self, case, practitioner=None):
		theatres = {
			theatre.name: theatre.label for group in self.board["complexes"] for theatre in group["theatres"]
		}
		return {
			"time": f"{get_datetime(case.scheduled_start):%H:%M}–{get_datetime(case.scheduled_end):%H:%M}",
			"theatre": theatres.get(case.theatre, case.theatre),
			"role": next((m["role"] for m in case.team_roles if m["name"] == practitioner), ""),
			"patient": " · ".join(
				filter(None, [case.patient_name, case.get("age"), (case.get("sex") or "")[:1]])
			),
			"procedures": ", ".join(case.procedures),
			"team": ", ".join(case.team_names),
			"priority": case.priority_label,
			"status": _(case.status),
		}
