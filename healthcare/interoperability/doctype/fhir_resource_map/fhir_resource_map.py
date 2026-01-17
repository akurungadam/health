# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import hashlib
import json
import re

import frappe
from frappe.model.document import Document
from frappe.utils import cint, now_datetime


class FHIRMappingCompilationError(Exception):
	pass


class FHIRRuntimeBuildError(Exception):
	pass


_INDEX_RE = re.compile(r"^(?P<key>[A-Za-z0-9_]+)\[(?P<index>\d+)\]$")


class FHIRResourceMap(Document):
	# =========================================================
	# Lifecycle
	# =========================================================

	def validate(self):
		compiled = self.compile_mapping()
		compiled_json = json.dumps(
			compiled,
			sort_keys=True,
			separators=(",", ":"),
			ensure_ascii=False,
			indent=1,
		)
		self.compiled_mapping = compiled_json
		self.compiled_hash = hashlib.sha256(compiled_json.encode("utf-8")).hexdigest()
		self.compiled_at = now_datetime()

	@frappe.whitelist()
	def compile_mapping(self):
		"""
		Compiled format goals:
		- One key per element (keyed by FHIR path).
		- Generator executes element_order + elements[*].path + elements[*].value_spec.
		- No runtime_plan duplication.

		Compiled shape (v1):
		{
		  compiled_version,
		  meta: {...},
		  sources: {...},
		  element_order: [...],
		  elements: { "Patient.birthDate": {...}, ... },
		  repeating_containers: {...},   # optional debug/support
		  placement: {...},              # optional debug/support
		  compile_warnings: [...]
		}
		"""
		compiled = {
			"compiled_version": "fhir-map-compiled/v1",
			"meta": {
				"primary_doctype": (self.primary_doctype or "").strip(),
				"base_structure_definition": (self.base_structure_definition or "").strip(),
				"resource_type": (self.resource_type or "").strip(),
				"compiled_at": str(now_datetime()),
			},
			"sources": self._compile_sources(),
		}

		element_state = self._compile_element_maps(compiled_sources=compiled["sources"])
		compiled["elements"] = element_state["elements"]
		compiled["element_order"] = element_state["element_order"]
		compiled["compile_warnings"] = element_state["compile_warnings"]

		# repeating containers only from SD (base+profiles) but kept ONLY if mapped descendants exist
		repeating_containers = self._compile_repeating_containers(elements=compiled["elements"])
		compiled["repeating_containers"] = repeating_containers

		# placement rules derived from repeating containers (default index 0)
		placement = self.compile_repeating_container_placement_rules(
			repeating_containers=repeating_containers
		)
		compiled["placement"] = placement

		# apply placement to all element paths (concrete runtime plan path lives with the element)
		self._apply_placement_to_compiled_elements(compiled, placement=placement)

		self._validate_compiled(compiled)
		return compiled

	# =========================================================
	# Sources compilation
	# =========================================================

	def _compile_sources(self):
		primary_doctype = (self.primary_doctype or "").strip()
		if not primary_doctype:
			raise FHIRMappingCompilationError("primary_doctype is required.")

		compiled_sources = {
			"primary": {
				"source_key": "primary",
				"kind": "primary",
				"doctype": primary_doctype,
			}
		}

		for row in self.get("sources") or []:
			source_key = (row.get("source_key") or "").strip()
			kind = (row.get("kind") or "").strip()
			doctype = (row.get("source_doctype") or row.get("doctype") or "").strip()

			if not source_key or not kind or not doctype:
				continue

			if source_key == "primary":
				raise FHIRMappingCompilationError(
					"Do not add a source with key 'primary' in the sources table."
				)

			if kind not in {"direct_link", "reverse_link"}:
				raise FHIRMappingCompilationError(
					f"Source '{source_key}': unsupported kind '{kind}'. Supported: ['direct_link','reverse_link']"
				)

			if source_key in compiled_sources:
				raise FHIRMappingCompilationError(f"Duplicate source_key '{source_key}'.")

			link_fieldname = (row.get("link_fieldname") or "").strip()
			if not link_fieldname:
				raise FHIRMappingCompilationError(
					f"Source '{source_key}': link_fieldname is required for '{kind}'."
				)

			spec = {
				"source_key": source_key,
				"kind": kind,
				"doctype": doctype,
				"link_fieldname": link_fieldname,
				"filters": self._parse_json_object(row.get("filters_json")) or {},
				"order_by": (row.get("order_by") or "").strip() or "creation desc",
			}

			# Optional: dependency chain
			from_source_key = (row.get("from_source_key") or "").strip()
			if from_source_key:
				spec["from_source_key"] = from_source_key

			if row.get("limit"):
				spec["limit"] = int(row.get("limit"))

			lookup_fieldname = (row.get("lookup_fieldname") or "").strip()
			if lookup_fieldname:
				spec["lookup_fieldname"] = lookup_fieldname

			compiled_sources[source_key] = spec

		return compiled_sources

	# =========================================================
	# Element maps compilation
	# =========================================================

	def _compile_element_maps(self, compiled_sources):
		"""
		Build elements keyed by fhir_path.

		We store:
		- op = "set"
		- base_json_path = "identifier.value" (resource prefix stripped)
		- path (concrete) computed later after repeating/placement are known
		- value_spec (field/fixed)
		- metadata for validation at runtime (datatype/regex/min/max/bindings/choice)
		"""
		elements = {}
		element_order = []
		compile_warnings = []

		for row in self.get("element_maps") or []:
			fhir_path = (row.get("fhir_path") or "").strip()
			if not fhir_path:
				continue

			pointer = self._parse_value_pointer(row.get("value_pointer"))
			if not pointer:
				continue  # not mapped, skip

			try:
				value_spec = self._cleanup_value_pointer(
					pointer=pointer,
					fhir_path=fhir_path,
					compiled_sources=compiled_sources,
				)
			except Exception as exc:
				compile_warnings.append(f"Skip '{fhir_path}': {exc}")
				continue

			if fhir_path in elements:
				raise FHIRMappingCompilationError(f"Duplicate element mapping for fhir_path '{fhir_path}'.")

			base_json_path = self._to_json_path(fhir_path)

			elements[fhir_path] = {
				"fhir_path": fhir_path,
				"op": "set",
				"base_json_path": base_json_path,  # will be transformed to concrete "path"
				"path": "",  # filled later
				"value_spec": value_spec,
				"datatype": (row.get("datatype") or "").strip(),
				"regex": row.get("regex"),
				"min": cint(row.get("min")),
				"max": str(row.get("max") or "").strip(),
				"valueset_url": (row.get("valueset_url") or "").strip(),
				"binding_strength": (row.get("binding_strength") or "").strip(),
				"is_choice_type": 1 if ("[x]" in fhir_path) else cint(row.get("is_choice_type")),
				"profile": (row.get("profile") or "").strip(),
				"target_profiles": self.normalize_string_list(row.get("target_profiles")),
			}

			element_order.append(fhir_path)

		element_order.sort()

		return {
			"elements": elements,
			"element_order": element_order,
			"compile_warnings": compile_warnings,
		}

	# =========================================================
	# Repeating Containers
	# =========================================================

	def _compile_repeating_containers(self, elements):
		"""
		Compute repeating containers from merged SD rows (base + profiles),
		but ONLY include containers that have at least one mapped descendant.

		Return dict like {"Patient.telecom": 1, ...}
		"""
		resource_type = (self.resource_type or "").strip()
		if not resource_type:
			raise FHIRMappingCompilationError("resource_type is required to compute repeating_containers.")

		if not (self.base_structure_definition or "").strip():
			return {}

		if not isinstance(elements, dict) or not elements:
			return {}

		mapped_paths = [str(p).strip() for p in elements.keys() if str(p).strip()]
		if not mapped_paths:
			return {}

		rows = self.get_elements_from_structure_definitions() or []

		repeating_sd = []
		for row in rows:
			fhir_path = (row.get("fhir_path") or "").strip()
			max_value = str(row.get("max") or "").strip()
			if fhir_path and max_value == "*":
				repeating_sd.append(fhir_path)

		if not repeating_sd:
			return {}

		repeating = {}
		for container_path in repeating_sd:
			prefix = container_path + "."
			for mapped_path in mapped_paths:
				if mapped_path.startswith(prefix):
					repeating[container_path] = 1
					break

		return repeating

	# =========================================================
	# Placement rules + apply placement
	# =========================================================

	def compile_repeating_container_placement_rules(self, repeating_containers):
		"""
		Return mapping like:
		{
		  "identifier": {"default_index": 0},
		  "contact": {"default_index": 0},
		  "link": {"default_index": 0},
		  "telecom": {"default_index": 0}
		}
		"""
		placement = {}
		for container_fhir_path in (repeating_containers or {}).keys():
			container_json_path = self.strip_resource_prefix(container_fhir_path)
			# only the first segment is index-applied by default
			first = (container_json_path or "").split(".", 1)[0].strip()
			if not first:
				continue
			placement[first] = {"default_index": 0}
		return placement

	def strip_resource_prefix(self, fhir_path):
		parts = (fhir_path or "").split(".", 1)
		return parts[1] if len(parts) == 2 else fhir_path

	def apply_repeating_placement(self, json_path, placement):
		"""
		json_path examples:
		- "identifier.use" => "identifier[0].use"
		- "contact.gender" => "contact[0].gender"
		- "birthDate" => unchanged
		"""
		if not json_path:
			return json_path

		segments = [s for s in str(json_path).split(".") if s]
		if not segments:
			return json_path

		first = segments[0]
		if first in (placement or {}):
			index = cint((placement[first] or {}).get("default_index", 0))
			segments[0] = f"{first}[{index}]"

		return ".".join(segments)

	def _apply_placement_to_compiled_elements(self, compiled, placement):
		elements = compiled.get("elements") or {}
		for _key, element in elements.items():
			if not isinstance(element, dict):
				continue
			base_json_path = (element.get("base_json_path") or "").strip()
			if not base_json_path:
				element["path"] = ""
				continue
			element["path"] = self.apply_repeating_placement(
				json_path=base_json_path,
				placement=placement,
			)

	# =========================================================
	# Compiled validation
	# =========================================================

	def _validate_compiled(self, compiled):
		meta = compiled.get("meta") or {}
		if not (meta.get("resource_type") or "").strip():
			raise FHIRMappingCompilationError("resource_type is required.")

		sources = compiled.get("sources") or {}
		if not isinstance(sources, dict) or not sources:
			raise FHIRMappingCompilationError("sources are missing from compiled output.")

		if "primary" not in sources:
			raise FHIRMappingCompilationError("primary source missing in compiled output.")

		if not frappe.in_test:
			elements = compiled.get("elements") or {}
			if not isinstance(elements, dict) or not elements:
				raise FHIRMappingCompilationError("No compiled element mappings found.")

	# =========================================================
	# Small JSON helpers
	# =========================================================

	def _parse_json_object(self, value):
		if not value:
			return {}
		if isinstance(value, dict):
			return value
		text = str(value).strip()
		if not text:
			return {}
		try:
			parsed = json.loads(text)
			return parsed if isinstance(parsed, dict) else {}
		except Exception:
			raise FHIRMappingCompilationError("filters_json must be a JSON object.")

	def _parse_value_pointer(self, raw):
		"""
		value_pointer supports:
		- dict already
		- JSON string dict
		Returns dict or None
		"""
		if raw is None:
			return None

		if isinstance(raw, dict):
			pointer = raw
		else:
			text = str(raw).strip()
			if not text:
				return None
			try:
				pointer = json.loads(text)
			except Exception:
				return None

		if not isinstance(pointer, dict):
			return None

		if not (pointer.get("kind") or "").strip():
			return None

		return pointer

	def _cleanup_value_pointer(self, pointer, fhir_path, compiled_sources):
		kind = (pointer.get("kind") or "").strip()

		if kind == "fixed":
			if "value" not in pointer:
				raise FHIRMappingCompilationError(f"'{fhir_path}': fixed pointer missing 'value'")
			return {"kind": "fixed", "value": pointer.get("value")}

		if kind == "field":
			source_key = (pointer.get("source_key") or "").strip()
			if not source_key:
				raise FHIRMappingCompilationError(f"'{fhir_path}': field pointer missing 'source_key'")

			fieldname = (pointer.get("fieldname") or "").strip()
			if not fieldname:
				raise FHIRMappingCompilationError(f"'{fhir_path}': field pointer missing 'fieldname'")

			if source_key not in compiled_sources:
				raise FHIRMappingCompilationError(
					f"'{fhir_path}': unknown source_key '{source_key}'. "
					f"Available: {sorted(compiled_sources.keys())}"
				)

			return {"kind": "field", "source_key": source_key, "fieldname": fieldname}

		raise FHIRMappingCompilationError(f"'{fhir_path}': unsupported pointer kind '{kind}'")

	def _to_json_path(self, fhir_path):
		fhir_path = (fhir_path or "").strip()
		resource_type = (self.resource_type or "").strip()

		prefix = resource_type + "."
		if resource_type and fhir_path.startswith(prefix):
			return fhir_path[len(prefix) :].strip()

		return fhir_path

	def normalize_string_list(self, value):
		"""
		Normalizes:
		- None -> []
		- list -> [stripped non-empty]
		- "single" -> ["single"]
		- '["a","b"]' -> ["a","b"]
		"""
		if value is None:
			return []

		if isinstance(value, list):
			return [str(v).strip() for v in value if str(v).strip()]

		if isinstance(value, str):
			text = value.strip()
			if not text:
				return []

			if text.startswith("[") and text.endswith("]"):
				try:
					parsed = json.loads(text)
					if isinstance(parsed, list):
						return [str(v).strip() for v in parsed if str(v).strip()]
				except Exception:
					return []

			return [text]

		return []

	# =========================================================
	# Runtime Value Resolution (preview)
	# =========================================================

	@frappe.whitelist()
	def resolve_values_runtime(self, primary_name, include_docs=0):
		primary_name = (primary_name or "").strip()
		if not primary_name:
			frappe.throw("primary_name is required")

		include_docs = 1 if str(include_docs) in ("1", "true", "True") else 0

		compiled = self._load_compiled()
		sources = compiled.get("sources") or {}
		elements = compiled.get("elements") or {}
		element_order = compiled.get("element_order") or []

		resolution = self._resolve_sources_runtime(
			sources=sources,
			primary_name=primary_name,
			include_docs=include_docs,
		)

		values_state = self._resolve_values_from_elements(
			elements=elements,
			element_order=element_order,
			resolved_docs=resolution["resolved_docs"],
		)

		return {
			"primary": {
				"source_key": "primary",
				"doctype": sources.get("primary", {}).get("doctype"),
				"name": primary_name,
			},
			"sources": resolution["sources_summary"],
			"source_issues": resolution["issues"],
			"values_by_path": values_state["values_by_path"],
			"value_issues": values_state["issues"],
		}

	def _load_compiled(self):
		if self.compiled_mapping:
			if isinstance(self.compiled_mapping, str):
				return json.loads(self.compiled_mapping)
			return self.compiled_mapping

		compiled = self.compile_mapping()
		return compiled

	# =========================================================
	# Source resolution
	# =========================================================

	def _resolve_sources_runtime(self, sources, primary_name, include_docs):
		issues = []
		resolved_docs = {}

		primary = sources.get("primary") or {}
		primary_doctype = (primary.get("doctype") or "").strip()
		if not primary_doctype:
			frappe.throw("Compiled sources missing primary.doctype")

		try:
			primary_doc = frappe.get_doc(primary_doctype, primary_name)
		except Exception as exc:
			frappe.throw(f"Could not load primary doc: {primary_doctype} '{primary_name}'. {exc}")

		resolved_docs["primary"] = primary_doc

		pending_keys = [k for k in sources.keys() if k != "primary"]
		pending_keys = sorted(pending_keys)

		for _pass in range(len(pending_keys) + 2):
			progress = False

			for source_key in list(pending_keys):
				spec = sources.get(source_key) or {}
				kind = (spec.get("kind") or "").strip()
				from_source_key = (spec.get("from_source_key") or "primary").strip() or "primary"

				if from_source_key not in resolved_docs:
					continue

				try:
					if kind == "direct_link":
						doc = self._resolve_direct_link_doc(spec, resolved_docs)
						resolved_docs[source_key] = doc

					elif kind == "reverse_link":
						docs = self._resolve_reverse_link_docs(spec, resolved_docs)
						resolved_docs[source_key] = docs

					else:
						raise Exception(f"Unsupported kind '{kind}'")

				except Exception as exc:
					issues.append({"source_key": source_key, "error": str(exc)})
					resolved_docs[source_key] = None

				pending_keys.remove(source_key)
				progress = True

			if not pending_keys:
				break

			if not progress:
				for source_key in pending_keys:
					spec = sources.get(source_key) or {}
					from_source_key = (spec.get("from_source_key") or "primary").strip() or "primary"
					issues.append(
						{
							"source_key": source_key,
							"error": f"Could not resolve source because dependency '{from_source_key}' was not resolved.",
						}
					)
					resolved_docs[source_key] = None
				pending_keys = []
				break

		sources_summary = {}
		for key, spec in sources.items():
			item = resolved_docs.get(key)
			if isinstance(item, list):
				count = len(item)
				names = [d.name for d in item]
			elif item:
				count = 1
				names = [item.name]
			else:
				count = 0
				names = []

			sources_summary[key] = {
				"source_key": key,
				"kind": spec.get("kind"),
				"doctype": spec.get("doctype"),
				"count": count,
				"names": names if not include_docs else None,
				"docs": item if include_docs else None,
			}

		return {"resolved_docs": resolved_docs, "issues": issues, "sources_summary": sources_summary}

	def _get_from_docs_for_source(self, spec, resolved_docs):
		from_source_key = (spec.get("from_source_key") or "primary").strip() or "primary"
		from_item = resolved_docs.get(from_source_key)

		if not from_item:
			return []

		if isinstance(from_item, list):
			return [d for d in from_item if d]

		return [from_item]

	def _resolve_direct_link_doc(self, spec, resolved_docs):
		doctype = (spec.get("doctype") or "").strip()
		link_fieldname = (spec.get("link_fieldname") or "").strip()
		if not doctype:
			raise Exception("Missing doctype")
		if not link_fieldname:
			raise Exception("Missing link_fieldname")

		from_docs = self._get_from_docs_for_source(spec, resolved_docs)
		if not from_docs:
			return None

		for from_doc in from_docs:
			link_value = getattr(from_doc, link_fieldname, None)
			if not link_value:
				continue

			try:
				return frappe.get_doc(doctype, link_value)
			except Exception:
				continue

		return None

	def _resolve_reverse_link_docs(self, spec, resolved_docs):
		doctype = (spec.get("doctype") or "").strip()
		link_fieldname = (spec.get("link_fieldname") or "").strip()
		if not doctype:
			raise Exception("Missing doctype")
		if not link_fieldname:
			raise Exception("Missing link_fieldname")

		order_by = (spec.get("order_by") or "creation desc").strip()
		limit = spec.get("limit")
		limit = int(limit) if limit not in (None, "", 0) else None

		filters = spec.get("filters") or {}
		if not isinstance(filters, dict):
			raise Exception("filters must be a dict")

		from_docs = self._get_from_docs_for_source(spec, resolved_docs)
		if not from_docs:
			return []

		out = []
		for from_doc in from_docs:
			if not from_doc:
				continue

			where_filters = dict(filters)
			where_filters[link_fieldname] = from_doc.name

			rows = frappe.get_all(
				doctype,
				filters=where_filters,
				fields=["name"],
				order_by=order_by,
				limit_page_length=limit or 0,
			)

			for r in rows:
				out.append(frappe.get_doc(doctype, r.name))

		return out

	def _resolve_values_from_elements(self, elements, element_order, resolved_docs):
		values_by_path = {}
		issues = []

		for element_key in element_order:
			element = (elements or {}).get(element_key) or {}
			value_spec = element.get("value_spec") or {}

			try:
				values_by_path[element_key] = _resolve_value(
					value_spec=value_spec, resolved_docs=resolved_docs
				)
			except Exception as exc:
				issues.append({"fhir_path": element_key, "error": str(exc)})
				values_by_path[element_key] = None

		return {"values_by_path": values_by_path, "issues": issues}

	# =========================================================
	# StructureDefinition overlay (base + profiles)
	# =========================================================

	@frappe.whitelist()
	def get_elements_from_structure_definitions(self):
		if not self.base_structure_definition:
			return []

		base_sd = self._get_structure_definition(self.base_structure_definition)
		base_rows = self._get_element_rows(base_sd)
		if not base_rows:
			return []

		resource_type = self._get_resource_type(base_sd)
		merged = self._build_base_element_map(base_rows, resource_type)

		self._overlay_profiles(merged, resource_type)

		return self._sorted_rows(merged)

	def _get_structure_definition(self, name):
		return frappe.get_cached_doc("FHIR Structure Definition", name)

	def _get_element_rows(self, sd):
		return sd.get("element_paths") or []

	def _get_resource_type(self, sd):
		return (getattr(sd, "fhir_sd", None) or "").strip()

	def _is_root_row(self, row, resource_type):
		return bool(resource_type) and (row.get("fhir_path") == resource_type)

	def _build_base_element_map(self, rows, resource_type):
		merged = {}
		for element_row in rows:
			row = self.build_element_map_row(element_row)
			if not row:
				continue
			if self._is_root_row(row, resource_type):
				continue
			merged[row["fhir_path"]] = row
		return merged

	def _overlay_profiles(self, merged, resource_type):
		for profile_row in self._get_sorted_profile_rows():
			sd_name = self._get_profile_structure_definition(profile_row)
			if not sd_name:
				continue

			profile_url = self._get_profile_url(profile_row)
			profile_sd = self._get_structure_definition(sd_name)
			profile_elements = self._get_element_rows(profile_sd)

			for element_row in profile_elements:
				overlay = self.build_element_map_row(element_row)
				if not overlay:
					continue

				path = overlay.get("fhir_path")
				if not path or self._is_root_row(overlay, resource_type):
					continue

				if path not in merged:
					overlay["profile"] = profile_url
					merged[path] = overlay
					continue

				if self._apply_most_restrictive_overlay(merged[path], overlay):
					merged[path]["profile"] = profile_url

	def _get_sorted_profile_rows(self):
		rows = list(self.get("profiles") or [])
		rows.sort(
			key=lambda row: (
				0 if cint(getattr(row, "is_primary", 0)) else 1,
				cint(getattr(row, "idx", 0)),
			)
		)
		return rows

	def _get_profile_structure_definition(self, profile_row):
		return (getattr(profile_row, "fhir_structure_definition", None) or "").strip()

	def _get_profile_url(self, profile_row):
		return (getattr(profile_row, "url", None) or "").strip() or (
			getattr(profile_row, "fhir_profile", None) or ""
		).strip()

	def _apply_most_restrictive_overlay(self, base, overlay):
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
		if self._strength_rank(overlay.get("binding_strength")) > self._strength_rank(
			base.get("binding_strength")
		):
			if overlay.get("binding_strength"):
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

	def _strength_rank(self, strength):
		return {"example": 1, "preferred": 2, "extensible": 3, "required": 4}.get((strength or "").lower(), 0)

	def _sorted_rows(self, merged):
		return [merged[key] for key in sorted(merged.keys())]

	def build_element_map_row(self, element_row):
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
			"fixed_value": element_row.get("fixed_value"),
			"frappe_field": "",
			"pattern_value": "",
			"default_value": "",
			"profile": "",
		}


# =========================================================
# Resource Generation (runtime)
# =========================================================


def build_resource_from_compiled_mapping(compiled_mapping, resolved_docs):
	meta = compiled_mapping.get("meta") or {}
	resource_type = (meta.get("resource_type") or "").strip()
	if not resource_type:
		raise FHIRRuntimeBuildError("Compiled mapping missing meta.resource_type")

	resource = {"resourceType": resource_type}

	elements = compiled_mapping.get("elements") or {}
	element_order = compiled_mapping.get("element_order") or []

	for element_key in element_order:
		element = elements.get(element_key) or {}
		if (element.get("op") or "").strip() != "set":
			continue

		target_path = (element.get("path") or "").strip()
		value_spec = element.get("value_spec") or {}
		if not target_path or not value_spec:
			continue

		raw_value = _resolve_value(value_spec=value_spec, resolved_docs=resolved_docs)
		if _is_empty_value(raw_value):
			continue

		_set_value_at_plan_path(resource, target_path, raw_value)

	return resource


def _resolve_value(value_spec, resolved_docs):
	kind = (value_spec.get("kind") or "").strip()

	if kind == "fixed":
		return value_spec.get("value")

	if kind == "field":
		source_key = (value_spec.get("source_key") or "").strip()
		fieldname = (value_spec.get("fieldname") or "").strip()
		if not source_key or not fieldname:
			return None

		doc_or_list = (resolved_docs or {}).get(source_key)

		# reverse_link may resolve to list; take first (already ordered)
		if isinstance(doc_or_list, list):
			doc_or_list = doc_or_list[0] if doc_or_list else None

		if not doc_or_list:
			return None

		return doc_or_list.get(fieldname)

	raise FHIRRuntimeBuildError(f"Unsupported value_spec.kind '{kind}'")


def _set_value_at_plan_path(resource, plan_path, value):
	"""
	Set a value using compiled element path syntax:
	- "birthDate"
	- "contact[0].gender"
	- "identifier[0].value"
	Creates dict/list containers as required.
	"""
	segments = _split_plan_path(plan_path)
	if not segments:
		return

	current = resource
	for segment in segments[:-1]:
		key, index = _parse_segment(segment)

		if index is None:
			child = current.get(key)
			if not isinstance(child, dict):
				child = {}
				current[key] = child
			current = child
			continue

		items = current.get(key)
		if not isinstance(items, list):
			items = []
			current[key] = items

		while len(items) <= index:
			items.append({})

		item = items[index]
		if not isinstance(item, dict):
			item = {}
			items[index] = item

		current = item

	leaf_key, leaf_index = _parse_segment(segments[-1])
	if leaf_index is None:
		current[leaf_key] = value
		return

	items = current.get(leaf_key)
	if not isinstance(items, list):
		items = []
		current[leaf_key] = items
	while len(items) <= leaf_index:
		items.append(None)
	items[leaf_index] = value


def _split_plan_path(plan_path):
	return [p for p in (plan_path or "").split(".") if p]


def _parse_segment(segment):
	match = _INDEX_RE.match(segment)
	if not match:
		return segment, None
	return match.group("key"), int(match.group("index"))


def _is_empty_value(value):
	if value is None:
		return True
	if isinstance(value, str) and not value.strip():
		return True
	if isinstance(value, (list, tuple, dict)) and len(value) == 0:
		return True
	return False


@frappe.whitelist()
def build_resource_from_compiled(fhir_resource_map, primary_name, include_docs=0):
	fhir_resource_map = (fhir_resource_map or "").strip()
	primary_name = (primary_name or "").strip()
	if not fhir_resource_map:
		frappe.throw("fhir_resource_map is required")
	if not primary_name:
		frappe.throw("primary_name is required")

	doc = frappe.get_doc("FHIR Resource Map", fhir_resource_map)
	compiled = doc._load_compiled()

	resolved = doc._resolve_sources_runtime(
		sources=(compiled.get("sources") or {}),
		primary_name=primary_name,
		include_docs=1 if str(include_docs) in ("1", "true", "True") else 0,
	)

	resource = build_resource_from_compiled_mapping(
		compiled_mapping=compiled,
		resolved_docs=resolved.get("resolved_docs") or {},
	)

	return {
		"resource": resource,
		"source_issues": resolved.get("issues") or [],
	}
