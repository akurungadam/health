import hashlib
import json

import frappe
from frappe.model.document import Document
from frappe.utils import cint, now_datetime


class FHIRSourceCompilationError(Exception):
	pass


class FHIRResourceMap(Document):
	def validate(self):
		self.compile_mapping()

	def compile_mapping(self):
		compiled_sources = self.compile_sources_to_compiled_mapping()
		compiled_elements = self.compile_elements_to_compiled_mapping(compiled_sources=compiled_sources)

		compiled = {
			"meta": {
				"primary_doctype": (self.primary_doctype or "").strip(),
				"base_structure_definition": (self.base_structure_definition or "").strip(),
				"resource_type": (self.resource_type or "").strip(),
				"compiled_at": str(now_datetime()),
			},
			"sources": compiled_sources,
			"elements": compiled_elements["elements"],
			"element_order": compiled_elements["element_order"],
		}

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

	def compile_sources_to_compiled_mapping(self):
		compiled_sources = {}

		# implicit primary
		primary_doctype = (self.primary_doctype or "").strip()
		if primary_doctype:
			compiled_sources["primary"] = {
				"key": "primary",
				"doctype": primary_doctype,
				"config": {"kind": "primary"},
			}

		for row in self.get("sources") or []:
			source_key = (row.get("source_key") or "").strip()
			source_doctype = (row.get("source_doctype") or "").strip()

			if not source_key or not source_doctype:
				continue

			config = self._parse_source_config(row.get("config"))
			config = self._normalize_source_config(config)

			# sanity: kinds that depend on another source must specify from_source_key
			kind = (config.get("kind") or "").strip()
			if kind in ("direct_link", "reverse_link", "dynamic_link"):
				from_key = (config.get("from_source_key") or "").strip()
				if not from_key:
					raise FHIRSourceCompilationError(
						f"Source '{source_key}': config.from_source_key is required for kind '{kind}'"
					)

			compiled_sources[source_key] = {
				"key": source_key,
				"doctype": source_doctype,
				"config": config,
			}

		# validate source graph references (catch typos early)
		for key, src in compiled_sources.items():
			cfg = src.get("config") or {}
			from_key = (cfg.get("from_source_key") or "").strip()
			if from_key and from_key not in compiled_sources:
				raise FHIRSourceCompilationError(
					f"Source '{key}': from_source_key '{from_key}' not found among sources (including 'primary')"
				)

		return compiled_sources

	def compile_elements_to_compiled_mapping(
		self,
		compiled_sources,
		include_unmapped=0,
	):
		if not isinstance(compiled_sources, dict):
			compiled_sources = {}

		out_elements = {}
		out_order = []
		warnings = []

		for row in self.get("element_maps") or []:
			element = self._compile_one_element_row(row)
			if not element or not isinstance(element, dict):
				continue

			fhir_path = (element.get("fhir_path") or "").strip()
			if not fhir_path:
				continue

			# Only compile mapped elements by default
			pointer = element.get("value_pointer")
			if not pointer:
				if include_unmapped:
					# keep but explicitly null pointer
					element["value_pointer"] = None
					out_elements[fhir_path] = element
					out_order.append(fhir_path)
				continue

			# normalize pointer.source to a source key when user stored doctype name
			pointer = self._normalize_pointer_source_safe(pointer, compiled_sources)
			element["value_pointer"] = pointer

			# validate pointer usability
			ok, reason = self._is_pointer_usable_safe(pointer, compiled_sources)
			if not ok:
				# mapped but invalid: skip + warn
				warnings.append(f"Skip '{fhir_path}': {reason}")
				continue

			# store
			out_elements[fhir_path] = element
			out_order.append(fhir_path)

		return {
			"elements": out_elements,
			"element_order": out_order,
			"warnings": warnings,
		}

	# -------------------------
	# Internals
	# -------------------------

	def _normalize_pointer_source_safe(self, pointer, compiled_sources):
		"""
		If pointer.kind == 'field' and pointer.source is a doctype name, map it to a source key.
		"""
		if not pointer or not isinstance(pointer, dict):
			return pointer

		kind = (pointer.get("kind") or "").strip()
		if kind != "field":
			return pointer

		source = (pointer.get("source") or "").strip()
		if not source:
			return pointer

		# already a source key
		if source in compiled_sources:
			return pointer

		# try doctype match
		for key, src in compiled_sources.items():
			if not isinstance(src, dict):
				continue
			if (src.get("doctype") or "").strip() == source:
				pointer["source"] = key
				return pointer

		return pointer

	def _is_pointer_usable_safe(self, pointer, compiled_sources):
		"""
		Return (ok, reason)
		Supports kinds: field, fixed
		"""
		if not pointer or not isinstance(pointer, dict):
			return (False, "value_pointer is not a dict")

		kind = (pointer.get("kind") or "").strip()

		if kind == "fixed":
			if "value" not in pointer:
				return (False, "fixed pointer missing 'value'")
			return (True, "")

		if kind == "field":
			source = (pointer.get("source") or "").strip()
			path = (pointer.get("path") or "").strip()

			if not source:
				return (False, "field pointer missing 'source'")
			if not path:
				return (False, "field pointer missing 'path'")
			if source not in compiled_sources:
				available = ", ".join(sorted(compiled_sources.keys()))
				return (False, f"source '{source}' not found. Available: {available}")
			return (True, "")

		return (False, f"unsupported kind '{kind}'")

	def _compile_one_element_row(self, row):
		fhir_path = (row.get("fhir_path") or "").strip()
		datatype = (row.get("datatype") or "").strip()
		max_value = (row.get("max") or "").strip()
		min_value = cint(row.get("min"))

		value_pointer = self._parse_value_pointer((row.get("value_pointer") or "").strip())
		if value_pointer:
			self._validate_pointer(value_pointer, fhir_path=fhir_path)

		is_required = row.get("is_required")
		if is_required in (1, True, "1", "true", "True"):
			is_required = 1
		else:
			is_required = 1 if min_value >= 1 else 0

		target_profiles = self._parse_json_list(row.get("target_profiles"))

		return {
			# identity
			"element_row_name": row.get("name"),
			"idx": cint(row.get("idx")),
			"fhir_path": fhir_path,
			# schema facts
			"datatype": datatype,
			"min": min_value,
			"max": max_value,
			# flags (keep your naming consistent with element_maps rows)
			"is_required": is_required,
			"is_choice_type": 1 if "[x]" in fhir_path else 0,
			# docs/metadata
			"short": (row.get("short") or "").strip(),
			# "definition": (row.get("definition") or "").strip(),
			# terminology
			"binding_strength": (row.get("binding_strength") or "").strip() or None,
			"valueset_url": (row.get("valueset_url") or "").strip() or None,
			"target_profiles": target_profiles,
			# profile marker
			"profile": (row.get("profile") or "").strip() or None,
			# mapping
			"value_pointer": value_pointer,
			# optional mapping fields (keep them because UI + debugging)
			"frappe_field": (row.get("frappe_field") or "").strip() or None,
			"fixed_value": (row.get("fixed_value") or "").strip() or None,
			"default_value": (row.get("default_value") or "").strip() or None,
			"pattern_value": (row.get("pattern_value") or "").strip() or None,
		}

	def _parse_source_config(self, raw, source_key=""):
		"""
		Config must be a JSON object (dict). Accepts:
		- empty -> {}
		- dict -> dict
		- string JSON object -> dict
		"""
		if raw is None:
			return {}

		# Sometimes Frappe may already give dict (rare). Accept it.
		if isinstance(raw, dict):
			return raw

		text = str(raw).strip()
		if not text:
			return {}

		try:
			val = json.loads(text)
		except Exception as e:
			snippet = text[:250].replace("\n", "\\n")
			raise FHIRSourceCompilationError(
				f"Source '{source_key}': config is not valid JSON object. Error: {e}. Raw: {snippet}"
			)

		if not isinstance(val, dict):
			raise FHIRSourceCompilationError(
				f"Source '{source_key}': config must be a JSON object ({{...}}), got {type(val).__name__}"
			)

		return val

	def _normalize_source_config(self, config):
		"""
		Normalize keys + defaults. Keep only supported keys to avoid garbage.
		"""
		kind = (config.get("kind") or "").strip() or None

		out = {"kind": kind}

		# common keys (for direct/reverse)
		if config.get("from_source_key") is not None:
			out["from_source_key"] = str(config.get("from_source_key") or "").strip() or None

		if config.get("link_fieldname") is not None:
			out["link_fieldname"] = str(config.get("link_fieldname") or "").strip() or None

		# filters_json: allow dict or JSON string
		filters_json = config.get("filters_json")
		if isinstance(filters_json, dict):
			out["filters_json"] = filters_json
		elif isinstance(filters_json, str) and filters_json.strip():
			try:
				parsed = json.loads(filters_json)
				out["filters_json"] = parsed if isinstance(parsed, dict) else None
			except Exception:
				raise FHIRSourceCompilationError("filters_json must be a JSON object")
		else:
			out["filters_json"] = None

		# order_by default
		order_by = self._normalize_order_by(config.get("order_by"))
		out["order_by"] = order_by or "creation desc"

		# dynamic_link specific
		for k in ("parenttype", "parentfield", "link_doctype"):
			if config.get(k) is not None:
				out[k] = str(config.get(k) or "").strip() or None

		# basic validation per kind
		if out["kind"] == "dynamic_link":
			if not out.get("parenttype") or not out.get("parentfield") or not out.get("link_doctype"):
				raise FHIRSourceCompilationError(
					"dynamic_link requires parenttype, parentfield, and link_doctype"
				)

		if out["kind"] in ("direct_link", "reverse_link"):
			if not out.get("link_fieldname"):
				raise FHIRSourceCompilationError(f"{out['kind']} requires link_fieldname")

		return out

	def _parse_value_pointer(self, raw):
		if not raw:
			return None
		try:
			val = json.loads(raw)
		except Exception:
			# strict? raise instead
			return None
		if not isinstance(val, dict):
			return None
		kind = (val.get("kind") or "").strip()
		if not kind:
			return None

		# normalize
		val["kind"] = kind
		if "source" in val and val["source"] is not None:
			val["source"] = str(val.get("source") or "").strip()
		if "path" in val and val["path"] is not None:
			val["path"] = str(val.get("path") or "").strip()

		return val

	def _validate_pointer(self, pointer, fhir_path=""):
		kind = (pointer.get("kind") or "").strip()

		if kind == "field":
			if not (pointer.get("source") and pointer.get("path")):
				raise FHIRSourceCompilationError(
					f"Invalid value_pointer for '{fhir_path}': field requires source + path"
				)
			return

		if kind == "fixed":
			if "value" not in pointer:
				raise FHIRSourceCompilationError(
					f"Invalid value_pointer for '{fhir_path}': fixed requires value"
				)
			return

		raise FHIRSourceCompilationError(f"Unsupported value_pointer kind '{kind}' for '{fhir_path}'")

	def _parse_json_list(self, raw):
		# supports: already-list, JSON string list, comma-separated
		if not raw:
			return []
		if isinstance(raw, list):
			return [str(x).strip() for x in raw if str(x).strip()]
		text = str(raw).strip()
		if not text:
			return []
		try:
			val = json.loads(text)
			if isinstance(val, list):
				return [str(x).strip() for x in val if str(x).strip()]
		except Exception:
			pass
		# fallback comma-separated
		return [x.strip() for x in text.split(",") if x.strip()]
		if not raw:
			return None
		if isinstance(raw, dict):
			return raw
		text = str(raw).strip()
		if not text:
			return None
		try:
			val = json.loads(text)
			return val if isinstance(val, dict) else None
		except Exception:
			return None

	def _normalize_order_by(self, value):
		"""
		Accept order_by as:
		- string: "creation desc"
		- list: ["idx asc", "creation desc"]
		Return a single string suitable for frappe.get_all(order_by=...).
		"""
		if value is None:
			return ""

		# already a string
		if isinstance(value, str):
			return value.strip()

		# list/tuple of strings
		if isinstance(value, (list, tuple)):
			parts = []
			for item in value:
				if item is None:
					continue
				if not isinstance(item, str):
					raise FHIRSourceCompilationError(
						f"config.order_by list items must be strings, got: {type(item)}"
					)
				item = item.strip()
				if item:
					parts.append(item)
			return ", ".join(parts)

		# anything else is invalid
		raise FHIRSourceCompilationError(
			f"config.order_by must be a string or list of strings, got: {type(value)}"
		)

	# =========================
	# Preview
	# =========================
	@frappe.whitelist()
	def resolve_sources_runtime(
		self,
		primary_name,
		compiled_mapping_json=None,
		include_docs=1,
		limit_per_source=20,
	):
		"""
		Resolve all sources for a given primary document name.
		- Used by client button (preview) and by resource generator (runtime).
		- Returns a single dict with resolved docs + errors.

		IMPORTANT:
		- Internally we ALWAYS store resolved docs as Frappe Document objects.
		- We only convert to {"name": ...} at the very end if include_docs == 0.
		"""
		primary_name = (primary_name or "").strip()
		if not primary_name:
			frappe.throw("primary_name is required")

		include_docs = cint(include_docs)
		limit_per_source = cint(limit_per_source) or 20

		compiled = self._load_compiled_mapping(compiled_mapping_json)
		sources = compiled.get("sources") or {}

		# normalize sources into dict
		if isinstance(sources, str):
			try:
				sources = json.loads(sources or "{}")
			except Exception:
				sources = {}
		if not isinstance(sources, dict):
			frappe.throw(f"sources must be a dict, got {type(sources)}")

		# -------------------------
		# primary: assume always "primary"
		# (as per your current compiled format)
		# -------------------------
		primary_source_key = "primary"
		primary_row = sources.get(primary_source_key) or {}
		primary_doctype = (primary_row.get("doctype") or "").strip()

		if not primary_doctype:
			frappe.throw("compiled_mapping is missing primary_doctype (sources.primary.doctype)")

		primary_doc = frappe.get_doc(primary_doctype, primary_name)

		errors = []
		resolved_docs = {primary_source_key: [primary_doc]}

		# resolve other sources
		for source_key, source_row in sources.items():
			if source_key == primary_source_key:
				continue

			try:
				doctype = (source_row.get("doctype") or "").strip()
				if not doctype:
					raise Exception("doctype is required")

				config = source_row.get("config") or {}
				kind = (config.get("kind") or "").strip()
				if not kind:
					raise Exception("config.kind is required")

				from_source_key = (config.get("from_source_key") or "").strip() or primary_source_key
				from_docs = resolved_docs.get(from_source_key) or []
				if not from_docs:
					raise Exception(f"from_source_key '{from_source_key}' not resolved")

				# For now: first doc is anchor
				from_doc = from_docs[0]

				docs = self._resolve_one_source_docs(
					source_key=source_key,
					doctype=doctype,
					config=config,
					from_doc=from_doc,
					limit_per_source=limit_per_source,
				)

				# Ensure list
				if docs is None:
					docs = []
				if not isinstance(docs, list):
					docs = [docs]

				resolved_docs[source_key] = docs

			except Exception as exc:
				errors.append({"source_key": source_key, "error": str(exc)})

		# -------------------------
		# build response payload last
		# -------------------------
		resolved = {}
		for k, docs in resolved_docs.items():
			row = sources.get(k) or {}
			doctype = (row.get("doctype") or "").strip() or (
				primary_doctype if k == primary_source_key else ""
			)
			kind = ((row.get("config") or {}).get("kind") or "").strip() or (
				"primary" if k == primary_source_key else ""
			)

			resolved[k] = self._make_resolved_payload(
				key=k,
				doctype=doctype,
				kind=kind,
				docs=docs,
				include_docs=include_docs,
			)

		return {
			"primary": {"doctype": primary_doctype, "name": primary_name, "source_key": primary_source_key},
			"resolved": resolved,
			"errors": errors,
		}

	# ----------------------------
	# preview helpers
	# ----------------------------

	def _load_compiled_mapping(self, compiled_mapping_json=None):
		if compiled_mapping_json:
			if isinstance(compiled_mapping_json, str):
				return json.loads(compiled_mapping_json)
			return compiled_mapping_json

		if not self.compiled_mapping:
			# compile on demand
			self.compile_map()

		return json.loads(self.compiled_mapping or "{}")

	def _make_resolved_payload(self, key, doctype, kind, docs, include_docs):
		docs = docs or []
		out = {
			"key": key,
			"doctype": doctype,
			"kind": kind,
			"count": len(docs),
		}

		out["docs"] = docs
		# if include_docs:
		# 	out["docs"] = docs
		# else:
		# 	out["docs"] = [{"name": d.name} for d in docs]
		return out

	def _resolve_one_source_docs(self, source_key, doctype, config, from_doc, limit_per_source):
		kind = (config.get("kind") or "").strip()

		if kind == "direct_link":
			return self._resolve_direct_link_docs(doctype, config, from_doc)

		if kind == "reverse_link":
			return self._resolve_reverse_link_docs(doctype, config, from_doc, limit_per_source)

		if kind == "dynamic_link":
			return self._resolve_dynamic_link_docs(doctype, config, from_doc, limit_per_source)

		raise Exception(f"Unsupported kind '{kind}'")

	def _resolve_direct_link_docs(self, doctype, config, from_doc):
		link_fieldname = (config.get("link_fieldname") or "").strip()
		if not link_fieldname:
			raise Exception("direct_link: link_fieldname is required")

		value = getattr(from_doc, link_fieldname, None)
		if not value:
			return []

		# If field is a Link to the target doctype, the value is name
		try:
			return [frappe.get_doc(doctype, value)]
		except Exception:
			return []

	def _resolve_reverse_link_docs(self, doctype, config, from_doc, limit_per_source):
		link_fieldname = (config.get("link_fieldname") or "").strip()
		if not link_fieldname:
			raise Exception("reverse_link: link_fieldname is required")

		order_by = (config.get("order_by") or "").strip() or "creation desc"
		filters = self._parse_filters_json(config.get("filters_json"))

		filters[link_fieldname] = from_doc.name

		names = frappe.get_all(
			doctype,
			filters=filters,
			fields=["name"],
			order_by=order_by,
			limit_page_length=limit_per_source,
		)
		return [frappe.get_doc(doctype, r["name"]) for r in names]

	def _resolve_dynamic_link_docs(self, doctype, config, from_doc, limit_per_source):
		# Dynamic Link rows live in `tabDynamic Link` with fields: link_doctype, link_name, parent, parenttype, parentfield
		link_doctype = (config.get("link_doctype") or "").strip()
		parenttype = (config.get("parenttype") or "").strip()
		parentfield = (config.get("parentfield") or "").strip()
		order_by = (config.get("order_by") or "").strip() or "idx asc, creation desc"

		if not link_doctype or not parenttype or not parentfield:
			raise Exception("dynamic_link: link_doctype, parenttype, parentfield are required")

		# NOTE: This is Dynamic Link doctype. It's how Frappe models “links”.
		rows = frappe.get_all(
			"Dynamic Link",  # TODO remove hard coding
			filters={
				"link_doctype": link_doctype,
				"link_name": from_doc.name,
				"parenttype": parenttype,
				"parentfield": parentfield,
			},
			fields=["parent", "idx"],
			order_by=order_by,
			limit_page_length=limit_per_source,
		)

		parent_names = [r["parent"] for r in rows if r.get("parent")]
		if not parent_names:
			return []

		# parent_names are Contact names in your example
		return [frappe.get_doc(doctype, name) for name in parent_names]

	def _parse_filters_json(self, filters_json):
		if not filters_json:
			return {}
		if isinstance(filters_json, dict):
			return filters_json
		try:
			return json.loads(filters_json)
		except Exception:
			return {}

	# ===========================
	# StructureDefinition overlay
	# ===========================

	@frappe.whitelist()
	def get_elements_from_structure_definitions(self, base_structure_definition):
		if not base_structure_definition:
			return []

		base_sd = self._get_structure_definition(base_structure_definition)
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
			key=lambda r: (
				0 if cint(getattr(r, "is_primary", 0)) else 1,
				cint(getattr(r, "idx", 0)),
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
		return [merged[k] for k in sorted(merged.keys())]

	def build_element_map_row(self, element_row):
		fhir_path = (element_row.get("path") or element_row.get("fhir_path") or "").strip()
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
