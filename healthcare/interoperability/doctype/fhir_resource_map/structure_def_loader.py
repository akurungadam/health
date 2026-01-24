import frappe
from frappe.utils import cint

# =========================================================
# Structure Definition Loader
# =========================================================


class FHIRStructureDefinitionLoader:
	"""Loads and merges structure definition elements."""

	def __init__(self, resource_map):
		self.resource_map = resource_map

	def load_merged_elements(self):
		if not (self.resource_map.base_structure_definition or "").strip():
			return []

		base_sd = frappe.get_cached_doc(
			"FHIR Structure Definition", self.resource_map.base_structure_definition
		)
		base_rows = base_sd.get("element_paths") or []
		resource_type = (getattr(base_sd, "fhir_sd", None) or "").strip()

		merger = FHIRStructureDefinitionMerger(resource_type=resource_type)
		merged = merger.build_base_map(base_rows)

		profile_rows = list(self.resource_map.get("profiles") or [])
		profile_rows.sort(
			key=lambda row: (0 if cint(getattr(row, "is_primary", 0)) else 1, cint(getattr(row, "idx", 0)))
		)

		for profile_row in profile_rows:
			sd_name = (getattr(profile_row, "fhir_structure_definition", None) or "").strip()
			if not sd_name:
				continue

			profile_url = (getattr(profile_row, "url", None) or "").strip() or (
				getattr(profile_row, "fhir_profile", None) or ""
			).strip()

			profile_sd = frappe.get_cached_doc("FHIR Structure Definition", sd_name)
			profile_elements = profile_sd.get("element_paths") or []

			merger.overlay_profile_rows(
				merged=merged,
				profile_url=profile_url,
				profile_elements=profile_elements,
			)

		return merger.to_sorted_rows(merged)


class FHIRStructureDefinitionMerger:
	"""Merges base and profile structure definitions with most-restrictive-wins logic."""

	STRENGTH_RANK = {"example": 1, "preferred": 2, "extensible": 3, "required": 4}

	def __init__(self, resource_type):
		self.resource_type = (resource_type or "").strip()

	def build_base_map(self, base_rows):
		merged = {}
		for element_row in base_rows or []:
			row = self._build_element_row(element_row)
			if not row:
				continue
			if self.resource_type and row.get("fhir_path") == self.resource_type:
				continue
			merged[row["fhir_path"]] = row
		return merged

	def overlay_profile_rows(self, merged, profile_url, profile_elements):
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

	def to_sorted_rows(self, merged):
		return [merged[key] for key in sorted((merged or {}).keys())]

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
		overlay_rank = self.STRENGTH_RANK.get((overlay.get("binding_strength") or "").lower(), 0)
		base_rank = self.STRENGTH_RANK.get((base.get("binding_strength") or "").lower(), 0)

		if overlay_rank > base_rank and overlay.get("binding_strength"):
			base["binding_strength"] = overlay.get("binding_strength")
			return True
		return False

	def _apply_valueset(self, base, overlay):
		if overlay.get("valueset_url") and overlay.get("valueset_url") != base.get("valueset_url"):
			base["valueset_url"] = overlay.get("valueset_url")
			return True
		return False

	def _apply_datatype(self, base, overlay):
		if overlay.get("datatype") and overlay.get("datatype") != base.get("datatype"):
			base["datatype"] = overlay.get("datatype")
			return True
		return False

	def _apply_target_profiles(self, base, overlay):
		if overlay.get("target_profiles") and overlay.get("target_profiles") != base.get("target_profiles"):
			base["target_profiles"] = overlay.get("target_profiles")
			return True
		return False

	def _fill_metadata(self, base, overlay):
		if overlay.get("short") and not base.get("short"):
			base["short"] = overlay.get("short")
		if overlay.get("definition") and not base.get("definition"):
			base["definition"] = overlay.get("definition")
