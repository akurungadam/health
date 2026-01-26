import frappe
from frappe.utils import cint


class FHIRStructureDefinitionLoader:
	"""Loads base structure definition + overlays profile structure definitions into one merged element list."""

	STRENGTH_RANK = {"example": 1, "preferred": 2, "extensible": 3, "required": 4}

	def __init__(self, resource_map):
		self.resource_map = resource_map
		self.resource_type = ""

	def load_merged_elements(self):
		base_sd_name = (self.resource_map.base_structure_definition or "").strip()
		if not base_sd_name:
			return []

		base_sd = frappe.get_cached_doc("FHIR Structure Definition", base_sd_name)
		base_rows = base_sd.get("element_paths") or []
		self.resource_type = (getattr(base_sd, "fhir_sd", None) or "").strip()

		merged = self._build_base_map(base_rows)

		profile_rows = list(self.resource_map.get("profiles") or [])
		profile_rows.sort(
			key=lambda row: (
				0 if cint(getattr(row, "is_primary", 0)) else 1,
				cint(getattr(row, "idx", 0)),
			)
		)

		for profile_row in profile_rows:
			self._overlay_profile_row(merged, profile_row)

		return self._to_sorted_rows(merged)

	# =========================================================
	# Build / Overlay
	# =========================================================

	def _build_base_map(self, base_rows):
		merged = {}
		for element_row in base_rows or []:
			row = self._build_element_row(element_row)
			if not row:
				continue

			# Skip the root "Patient" row (or whatever resourceType is)
			if self.resource_type and row.get("fhir_path") == self.resource_type:
				continue

			merged[row["fhir_path"]] = row
		return merged

	def _overlay_profile_row(self, merged, profile_row):
		sd_name = (getattr(profile_row, "fhir_structure_definition", None) or "").strip()
		if not sd_name:
			return

		profile_url = (getattr(profile_row, "url", None) or "").strip()
		if not profile_url:
			profile_url = (getattr(profile_row, "fhir_profile", None) or "").strip()

		profile_sd = frappe.get_cached_doc("FHIR Structure Definition", sd_name)
		profile_elements = profile_sd.get("element_paths") or []

		for element_row in profile_elements or []:
			overlay = self._build_element_row(element_row)
			if not overlay:
				continue

			if self.resource_type and overlay.get("fhir_path") == self.resource_type:
				continue

			path = overlay.get("fhir_path")
			if not path:
				continue

			if path not in merged:
				overlay["profile"] = profile_url
				merged[path] = overlay
				continue

			if self._apply_most_restrictive(merged[path], overlay):
				merged[path]["profile"] = profile_url

	def _to_sorted_rows(self, merged):
		return [merged[key] for key in sorted((merged or {}).keys())]

	# =========================================================
	# Row normalization
	# =========================================================

	def _build_element_row(self, element_row):
		fhir_path = (element_row.get("path") or "").strip()
		if not fhir_path:
			return None

		min_cardinality = cint(element_row.get("min"))
		return {
			"fhir_path": fhir_path,
			"datatype": (element_row.get("datatype") or "").strip(),
			"min": min_cardinality,
			"max": str(element_row.get("max") or "").strip(),
			"short": (element_row.get("short") or "").strip(),
			"definition": (element_row.get("definition") or "").strip(),
			"valueset_url": (element_row.get("valueset_url") or "").strip(),
			"binding_strength": (element_row.get("binding_strength") or "").strip(),
			"target_profiles": element_row.get("target_profiles"),
			"is_required": 1 if min_cardinality >= 1 else 0,
			"is_choice_type": 1 if ("[x]" in fhir_path) else 0,
			"profile": "",
		}

	# =========================================================
	# Most restrictive wins
	# =========================================================

	def _apply_most_restrictive(self, base, overlay):
		changed = False
		changed |= self._apply_min(base, overlay)
		changed |= self._apply_max(base, overlay)
		changed |= self._apply_binding_strength(base, overlay)
		changed |= self._apply_valueset(base, overlay)
		changed |= self._apply_datatype(base, overlay)
		changed |= self._apply_target_profiles(base, overlay)
		self._fill_metadata(base, overlay)
		return bool(changed)

	def _apply_min(self, base, overlay):
		if cint(overlay.get("min")) > cint(base.get("min")):
			base["min"] = cint(overlay.get("min"))
			base["is_required"] = 1 if cint(base["min"]) >= 1 else 0
			return True
		return False

	def _apply_max(self, base, overlay):
		base_max = (base.get("max") or "").strip()
		overlay_max = (overlay.get("max") or "").strip()
		if not overlay_max:
			return False

		if base_max == "*" and overlay_max != "*":
			base["max"] = overlay_max
			return True

		if (
			overlay_max != "*"
			and base_max != "*"
			and overlay_max.isdigit()
			and base_max.isdigit()
			and int(overlay_max) < int(base_max)
		):
			base["max"] = overlay_max
			return True

		return False

	def _apply_binding_strength(self, base, overlay):
		overlay_strength = (overlay.get("binding_strength") or "").strip()
		if not overlay_strength:
			return False

		overlay_rank = self.STRENGTH_RANK.get(overlay_strength.lower(), 0)
		base_rank = self.STRENGTH_RANK.get((base.get("binding_strength") or "").lower(), 0)

		if overlay_rank > base_rank:
			base["binding_strength"] = overlay_strength
			return True

		return False

	def _apply_valueset(self, base, overlay):
		overlay_valueset = (overlay.get("valueset_url") or "").strip()
		if overlay_valueset and overlay_valueset != (base.get("valueset_url") or "").strip():
			base["valueset_url"] = overlay_valueset
			return True
		return False

	def _apply_datatype(self, base, overlay):
		overlay_datatype = (overlay.get("datatype") or "").strip()
		if overlay_datatype and overlay_datatype != (base.get("datatype") or "").strip():
			base["datatype"] = overlay_datatype
			return True
		return False

	def _apply_target_profiles(self, base, overlay):
		overlay_targets = overlay.get("target_profiles")
		if overlay_targets and overlay_targets != base.get("target_profiles"):
			base["target_profiles"] = overlay_targets
			return True
		return False

	def _fill_metadata(self, base, overlay):
		if (overlay.get("short") or "").strip() and not (base.get("short") or "").strip():
			base["short"] = overlay.get("short")
		if (overlay.get("definition") or "").strip() and not (base.get("definition") or "").strip():
			base["definition"] = overlay.get("definition")
