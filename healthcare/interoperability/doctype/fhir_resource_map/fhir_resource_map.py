# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import hashlib
import json

import frappe
from frappe.model.document import Document
from frappe.model.meta import get_meta
from frappe.utils import cint, now_datetime


class FHIRSourceCompilationError(Exception):
	pass


class FHIRResourceMap(Document):
	def on_update(self):
		"""
		Compile mapping every save.
		"""
		self.compile_map()
		self.db_set(
			{
				"compiled_mapping": self.compiled_mapping,
				"compiled_hash": self.compiled_hash,
				"compiled_at": self.compiled_at,
			}
		)

	@frappe.whitelist()
	def compile_map(self):
		compiled = {}

		compiled["primary_doctype"] = (self.primary_doctype or "").strip()
		compiled["base_structure_definition"] = (self.base_structure_definition or "").strip()
		compiled["profiles"] = self._compile_profiles_summary()

		compiled_sources = self._compile_sources_only()
		compiled["sources"] = compiled_sources

		elements_payload = self._compile_elements(compiled_sources)
		compiled["elements"] = elements_payload["elements"]
		compiled["missing_required"] = elements_payload["missing_required"]
		compiled["counts"] = elements_payload["counts"]

		compiled_text = json.dumps(compiled, indent=2, ensure_ascii=False)

		self.compiled_mapping = compiled_text
		self.compiled_hash = self._hash_compiled_mapping(compiled)
		self.compiled_at = now_datetime()

		# if compiled.get("missing_required"):
		# 	raise FHIRSourceCompilationError(
		# 		"Missing required element mappings: "
		# 		+ ", ".join([r["fhir_path"] for r in compiled["missing_required"][:20]])
		# 		+ (" ..." if len(compiled["missing_required"]) > 20 else "")
		# 	)

		return {"compiled_hash": self.compiled_hash, "compiled_at": str(self.compiled_at)}

	# -------------------------
	# Sources compilation
	# -------------------------

	def _compile_sources_only(self):
		primary_doctype = (self.primary_doctype or "").strip()
		if not primary_doctype:
			raise FHIRSourceCompilationError("Primary DocType is required to compile sources.")

		primary_meta = get_meta(primary_doctype)

		compiled_sources = {
			"primary": {
				"kind": "primary",
				"doctype": primary_doctype,
				"required": True,
				"cache": True,
			}
		}

		for row in self.sources or []:
			source_key = (row.source_key or "").strip()
			source_doctype = (row.source_doctype or "").strip()
			config_text = (row.config or "").strip()

			if not source_key:
				raise FHIRSourceCompilationError("Source Key is required for all source rows.")
			if source_key == "primary":
				raise FHIRSourceCompilationError("Source Key 'primary' is reserved (implicit).")
			if source_key in compiled_sources:
				raise FHIRSourceCompilationError(f"Duplicate Source Key: {source_key}")
			if not source_doctype:
				raise FHIRSourceCompilationError(f"Source '{source_key}': Source DocType is required.")

			config = self._parse_config_json(config_text, source_key)

			kind = (config.get("kind") or "").strip()
			if not kind:
				raise FHIRSourceCompilationError(
					f"Source '{source_key}': config.kind is required (only 'direct_link' supported now)."
				)

			if kind == "direct_link":
				compiled_sources[source_key] = self._compile_direct_link_source(
					source_key=source_key,
					source_doctype=source_doctype,
					config=config,
					primary_meta=primary_meta,
					primary_doctype=primary_doctype,
				)
			elif kind == "dynamic_link":
				compiled_sources[source_key] = self._compile_dynamic_link_source(
					source_key=source_key,
					source_doctype=source_doctype,
					config=config,
					primary_meta=primary_meta,
					primary_doctype=primary_doctype,
				)
			elif kind == "reverse_dynamic_link":
				compiled_sources[source_key] = self._compile_reverse_dynamic_link_source(
					source_key=source_key,
					source_doctype=source_doctype,
					config=config,
					primary_doctype=primary_doctype,
				)
			elif kind == "reverse_link":
				compiled_sources[source_key] = self._compile_reverse_link_source(
					source_key=source_key,
					source_doctype=source_doctype,
					config=config,
					# primary_meta=primary_meta,
					primary_doctype=primary_doctype,
				)
			else:
				raise FHIRSourceCompilationError(
					f"Source '{source_key}': Unsupported kind '{kind}'. Supported: direct_link, reverse_link."
				)

		return compiled_sources

	def _compile_direct_link_source(
		self,
		source_key,
		source_doctype,
		config,
		primary_meta,
		primary_doctype,
	):
		link_fieldname = (config.get("link_fieldname") or "").strip()
		if not link_fieldname:
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (direct_link): config.link_fieldname is required."
			)

		field = primary_meta.get_field(link_fieldname)
		if not field:
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (direct_link): link_fieldname '{link_fieldname}' not found "
				f"in primary doctype '{primary_doctype}'."
			)

		if field.fieldtype != "Link":
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (direct_link): field '{link_fieldname}' must be Link, "
				f"found '{field.fieldtype}'."
			)

		linked_doctype = (field.options or "").strip()
		if linked_doctype and linked_doctype != source_doctype:
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (direct_link): field '{link_fieldname}' links to '{linked_doctype}', "
				f"but Source DocType is '{source_doctype}'."
			)

		required = self._to_bool(config.get("required"))
		cache = self._to_bool_default_true(config.get("cache"))

		return {
			"kind": "direct_link",
			"doctype": source_doctype,
			"link_fieldname": link_fieldname,
			"required": required,
			"cache": cache,
		}

	def _compile_dynamic_link_source(
		self,
		source_key,
		source_doctype,
		config,
		primary_meta,
		primary_doctype,
	):
		link_fieldname = (config.get("link_fieldname") or "").strip()
		if not link_fieldname:
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (dynamic_link): config.link_fieldname is required."
			)

		field = primary_meta.get_field(link_fieldname)
		if not field:
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (dynamic_link): link_fieldname '{link_fieldname}' not found "
				f"in primary doctype '{primary_doctype}'."
			)

		if field.fieldtype != "Dynamic Link":
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (dynamic_link): field '{link_fieldname}' must be Dynamic Link, "
				f"found '{field.fieldtype}'."
			)

		# In Frappe, Dynamic Link field.options == fieldname that stores the linked doctype
		doctype_fieldname = (field.options or "").strip()
		if not doctype_fieldname:
			# allow override as escape hatch
			doctype_fieldname = (config.get("doctype_fieldname") or "").strip()

		if not doctype_fieldname:
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (dynamic_link): could not infer doctype field. "
				f"Set Dynamic Link field.options or provide config.doctype_fieldname."
			)

		# source_doctype is treated as "expected doctype". Use "*" to allow any.
		expected_doctype = (source_doctype or "").strip() or "*"
		if expected_doctype.lower() == "any":
			expected_doctype = "*"

		required = self._to_bool(config.get("required"))
		cache = self._to_bool_default_true(config.get("cache"))

		return {
			"kind": "dynamic_link",
			"doctype": expected_doctype,  # "*" means allow any doctype at runtime
			"link_fieldname": link_fieldname,  # the Dynamic Link field storing the name
			"doctype_fieldname": doctype_fieldname,  # the field storing the doctype
			"required": required,
			"cache": cache,
		}

	def _compile_reverse_dynamic_link_source(self, source_key, source_doctype, config, primary_doctype):
		parentfield = (config.get("parentfield") or "").strip()
		if not parentfield:
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (reverse_dynamic_link): config.parentfield is required (e.g. 'links')."
			)

		required = self._to_bool(config.get("required"))
		cache = self._to_bool_default_true(config.get("cache"))
		multiple = self._to_bool(config.get("multiple"))

		limit = config.get("limit")
		if limit in (None, "", "null", "None"):
			limit = 1 if not multiple else 20
		limit = cint(limit)
		if limit <= 0:
			limit = 1 if not multiple else 20

		order_by = config.get("order_by") or []
		if isinstance(order_by, str):
			order_by = [order_by]
		if not isinstance(order_by, list):
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (reverse_dynamic_link): config.order_by must be a list."
			)

		return {
			"kind": "reverse_dynamic_link",
			"doctype": source_doctype,  # e.g. Contact
			"parenttype": source_doctype,  # Contact
			"parentfield": parentfield,  # links
			"link_doctype": primary_doctype,  # Patient
			"order_by": order_by,
			"limit": limit,
			"multiple": bool(multiple),
			"required": required,
			"cache": cache,
		}

	def _compile_reverse_link_source(self, source_key, source_doctype, config, primary_doctype):
		link_fieldname = (config.get("link_fieldname") or "").strip()
		if not link_fieldname:
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (reverse_link): config.link_fieldname is required."
			)

		source_meta = get_meta(source_doctype)
		field = source_meta.get_field(link_fieldname)
		if not field:
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (reverse_link): link_fieldname '{link_fieldname}' not found "
				f"in source doctype '{source_doctype}'."
			)

		if field.fieldtype != "Link":
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (reverse_link): field '{link_fieldname}' must be Link, "
				f"found '{field.fieldtype}'."
			)

		linked_doctype = (field.options or "").strip()
		if linked_doctype and linked_doctype != primary_doctype:
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (reverse_link): field '{link_fieldname}' links to '{linked_doctype}', "
				f"but primary doctype is '{primary_doctype}'."
			)

		required = self._to_bool(config.get("required"))
		cache = self._to_bool_default_true(config.get("cache"))
		multiple = self._to_bool(config.get("multiple"))

		limit = config.get("limit")
		if limit in (None, "", "null", "None"):
			limit = 1 if not multiple else 20
		limit = cint(limit)
		if limit <= 0:
			limit = 1 if not multiple else 20

		order_by = config.get("order_by") or []
		if isinstance(order_by, str):
			# tolerate single string, but store canonical list
			order_by = [order_by]
		if not isinstance(order_by, list):
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (reverse_link): config.order_by must be a list."
			)

		filters = config.get("filters") or {}
		if not isinstance(filters, dict):
			raise FHIRSourceCompilationError(
				f"Source '{source_key}' (reverse_link): config.filters must be a JSON object."
			)

		return {
			"kind": "reverse_link",
			"doctype": source_doctype,
			"link_fieldname": link_fieldname,
			"filters": filters,
			"order_by": order_by,
			"limit": limit,
			"multiple": bool(multiple),
			"required": required,
			"cache": cache,
		}

	# -------------------------
	# Elements compilation
	# -------------------------

	def _compile_elements(self, compiled_sources):
		"""
		Runtime compile:
		- Only mapped elements go into compiled["elements"]
		- Required-but-unmapped go into compiled["missing_required"]
		"""
		rows = list(self.element_maps or [])

		source_key_by_doctype = self._build_source_key_by_doctype_index(compiled_sources)

		compiled_elements = []
		missing_required = []

		for row in rows:
			fhir_path = (row.fhir_path or "").strip()
			if not fhir_path:
				continue

			is_required = cint(row.min) >= 1

			pointer = self._parse_pointer(row.value_pointer)
			pointer = self._normalize_pointer(pointer, compiled_sources, source_key_by_doctype)
			is_mapped = bool(pointer and pointer.get("kind"))

			if not is_mapped:
				if is_required:
					missing_required.append(
						{
							"fhir_path": fhir_path,
							"datatype": (row.datatype or "").strip(),
							"min": cint(row.min),
							"max": str(row.max or "").strip(),
						}
					)
				continue

			# Keep runtime payload lean: only what generator needs
			compiled_elements.append(
				{
					"fhir_path": fhir_path,
					"datatype": (row.datatype or "").strip(),
					"min": cint(row.min),
					"max": str(row.max or "").strip(),
					"pointer": pointer,
					# keep these only if you use them during generation/validation
					"binding_strength": (row.binding_strength or "").strip(),
					"valueset_url": (row.valueset_url or "").strip(),
					"target_profiles": row.target_profiles,
				}
			)

		return {
			"elements": compiled_elements,
			"missing_required": missing_required,
			"counts": {
				"total_rows": len(rows),
				"mapped": len(compiled_elements),
				"missing_required": len(missing_required),
			},
		}

	def _build_source_key_by_doctype_index(self, compiled_sources):
		"""
		If multiple source_keys point to same doctype, we don't auto-map by doctype
		(because it's ambiguous).
		"""
		doctype_to_keys = {}
		for key, meta in (compiled_sources or {}).items():
			dt = (meta.get("doctype") or "").strip()
			if not dt:
				continue
			doctype_to_keys.setdefault(dt, []).append(key)

		unique = {}
		for dt, keys in doctype_to_keys.items():
			if len(keys) == 1:
				unique[dt] = keys[0]
		return unique

	def _parse_pointer(self, value_pointer_text):
		text = (value_pointer_text or "").strip()
		if not text:
			return {}
		try:
			parsed = json.loads(text)
		except Exception:
			return {}
		return parsed if isinstance(parsed, dict) else {}

	def _normalize_pointer(self, pointer, compiled_sources, source_key_by_doctype):
		if not pointer or not isinstance(pointer, dict):
			return {}

		kind = (pointer.get("kind") or "").strip()
		if not kind:
			return {}

		# Normalize source
		source_raw = (pointer.get("source") or "").strip()
		if not source_raw:
			source_raw = "primary"

		# If source was stored as a doctype name, map it to the matching source_key (if unique)
		if source_raw not in (compiled_sources or {}):
			mapped_key = source_key_by_doctype.get(source_raw)
			if mapped_key:
				source_raw = mapped_key

		# If still unknown => hard fail to unmapped (prevents runtime surprises)
		if kind in ("field", "json", "expr") and source_raw not in (compiled_sources or {}):
			return {}

		# Normalize fields by kind
		if kind == "field":
			path = (pointer.get("path") or "").strip()
			if not path:
				return {}
			return {"kind": "field", "source": source_raw, "path": path, **self._pick_default(pointer)}

		if kind == "json":
			path = (pointer.get("path") or "").strip()
			if not path:
				return {}
			return {"kind": "json", "source": source_raw, "path": path, **self._pick_default(pointer)}

		if kind == "expr":
			expr = (pointer.get("expr") or "").strip()
			if not expr:
				return {}
			return {"kind": "expr", "source": source_raw, "expr": expr, **self._pick_default(pointer)}

		if kind == "fixed":
			# value can be any JSON type
			return {"kind": "fixed", "value": pointer.get("value"), **self._pick_default(pointer)}

		# Unknown kind => drop
		return {}

	def _pick_default(self, pointer):
		if not isinstance(pointer, dict):
			return {}
		if "default" in pointer:
			return {"default": pointer.get("default")}
		return {}

	# -------------------------
	# Preview (server)
	# -------------------------

	@frappe.whitelist()
	def preview_sources(self, primary_name):
		self._ensure_compiled(recompile=True)

		compiled = json.loads(self.compiled_mapping or "{}")
		sources = compiled.get("sources") or {}

		if not sources or "primary" not in sources:
			return {"errors": ["No compiled sources found. Save / compile map first."]}

		primary_doctype = (sources.get("primary") or {}).get("doctype")
		if not primary_doctype:
			return {"errors": ["Primary doctype missing in compiled sources."]}

		errors = []

		try:
			primary_doc = frappe.get_doc(primary_doctype, primary_name)
		except Exception as e:
			return {"errors": [f"Could not load primary doc: {e}"]}

		resolved_docs = {"primary": primary_doc}
		source_summaries = [
			{
				"source_key": "primary",
				"kind": "primary",
				"doctype": primary_doctype,
				"required": True,
				"resolved": {"doctype": primary_doctype, "name": primary_doc.name},
			}
		]

		for key, meta in sources.items():
			if key == "primary":
				continue

			kind = (meta.get("kind") or "").strip()
			doctype = (meta.get("doctype") or "").strip()
			required = bool(meta.get("required"))

			if kind == "direct_link":
				link_fieldname = (meta.get("link_fieldname") or "").strip()
				link_value = primary_doc.get(link_fieldname)

				if not link_value:
					resolved_docs[key] = None
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": doctype,
							"required": required,
							"resolved": None,
						}
					)
					continue

				try:
					doc = frappe.get_doc(doctype, link_value)
					resolved_docs[key] = doc
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": doctype,
							"required": required,
							"resolved": {"doctype": doc.doctype, "name": doc.name},
						}
					)
					continue
				except Exception as e:
					errors.append(f"Source '{key}' resolve failed: {e}")
					resolved_docs[key] = None
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": doctype,
							"required": required,
							"resolved": None,
						}
					)
					continue

			elif kind == "dynamic_link":
				link_fieldname = (meta.get("link_fieldname") or "").strip()
				doctype_fieldname = (meta.get("doctype_fieldname") or "").strip()
				expected_doctype = (meta.get("doctype") or "").strip() or "*"

				link_name = primary_doc.get(link_fieldname)
				link_doctype = primary_doc.get(doctype_fieldname)

				if not link_name or not link_doctype:
					resolved_docs[key] = None
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": expected_doctype,
							"required": required,
							"resolved": None,
						}
					)
					continue

				if expected_doctype != "*" and link_doctype != expected_doctype:
					errors.append(
						f"Source '{key}' dynamic_link doctype mismatch: expected '{expected_doctype}', got '{link_doctype}'."
					)
					resolved_docs[key] = None
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": expected_doctype,
							"required": required,
							"resolved": None,
						}
					)
					continue

				try:
					doc = frappe.get_doc(link_doctype, link_name)
					resolved_docs[key] = doc
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": doc.doctype,
							"required": required,
							"resolved": {"doctype": doc.doctype, "name": doc.name},
						}
					)
					continue
				except Exception as e:
					errors.append(f"Source '{key}' resolve failed: {e}")
					resolved_docs[key] = None
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": expected_doctype,
							"required": required,
							"resolved": None,
						}
					)
					continue

			elif kind == "reverse_link":
				link_fieldname = (meta.get("link_fieldname") or "").strip()
				filters = dict(meta.get("filters") or {})
				order_by = meta.get("order_by") or []
				limit = cint(meta.get("limit") or 1)
				multiple = bool(meta.get("multiple"))

				filters[link_fieldname] = primary_doc.name

				# order_by stored as list -> join for frappe.get_all
				order_by_text = ", ".join([o for o in order_by if isinstance(o, str) and o.strip()])

				names = frappe.get_all(
					doctype,
					filters=filters,
					fields=["name"],
					order_by=order_by_text or None,
					limit=limit,
				)

				if not names:
					resolved_docs[key] = [] if multiple else None
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": doctype,
							"required": required,
							"resolved": None,
						}
					)
					continue

				if multiple:
					docs = [frappe.get_doc(doctype, r["name"]) for r in names]
					resolved_docs[key] = docs
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": doctype,
							"required": required,
							"resolved": [{"doctype": doctype, "name": d.name} for d in docs[:10]],
						}
					)
					continue

				doc = frappe.get_doc(doctype, names[0]["name"])
				resolved_docs[key] = doc
				source_summaries.append(
					{
						"source_key": key,
						"kind": kind,
						"doctype": doctype,
						"required": required,
						"resolved": {"doctype": doctype, "name": doc.name},
					}
				)
				continue
			elif kind == "reverse_dynamic_link":
				target_doctype = (meta.get("doctype") or "").strip()  # e.g. "Contact"
				parenttype = (meta.get("parenttype") or "").strip() or target_doctype
				parentfield = (meta.get("parentfield") or "").strip()  # e.g. "links"
				link_doctype = (meta.get("link_doctype") or "").strip()  # e.g. "Patient"
				order_by = meta.get("order_by") or []
				source_limit = cint(meta.get("limit") or 1)
				multiple = bool(meta.get("multiple"))
				required = bool(meta.get("required"))

				# If config is incomplete, treat as unresolved (dont blow up preview)
				if not (target_doctype and parenttype and parentfield and link_doctype):
					resolved_docs[key] = [] if multiple else None
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": target_doctype,
							"required": required,
							"resolved": None,
						}
					)
					continue

				order_by_text = ", ".join([o for o in order_by if isinstance(o, str) and o.strip()])

				dl_rows = frappe.get_all(
					"Dynamic Link",
					filters={
						"link_doctype": link_doctype,
						"link_name": primary_doc.name,
						"parenttype": parenttype,
						"parentfield": parentfield,
					},
					fields=["parent", "idx"],
					order_by=order_by_text or "idx asc",
					limit=source_limit,
				)

				if not dl_rows:
					resolved_docs[key] = [] if multiple else None
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": target_doctype,
							"required": required,
							"resolved": None,
						}
					)
					continue

				# keep order, de-dupe
				parent_names = []
				seen = set()
				for r in dl_rows:
					p = r.get("parent")
					if p and p not in seen:
						seen.add(p)
						parent_names.append(p)

				if not parent_names:
					resolved_docs[key] = [] if multiple else None
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": target_doctype,
							"required": required,
							"resolved": None,
						}
					)
					continue

				try:
					if multiple:
						docs = [frappe.get_doc(target_doctype, n) for n in parent_names]
						resolved_docs[key] = docs
						source_summaries.append(
							{
								"source_key": key,
								"kind": kind,
								"doctype": target_doctype,
								"required": required,
								"resolved": [{"doctype": target_doctype, "name": d.name} for d in docs[:10]],
							}
						)
					else:
						doc = frappe.get_doc(target_doctype, parent_names[0])
						resolved_docs[key] = doc
						source_summaries.append(
							{
								"source_key": key,
								"kind": kind,
								"doctype": target_doctype,
								"required": required,
								"resolved": {"doctype": target_doctype, "name": doc.name},
							}
						)
				except Exception as e:
					errors.append(f"Source '{key}' reverse_dynamic_link resolve failed: {e}")
					resolved_docs[key] = [] if multiple else None
					source_summaries.append(
						{
							"source_key": key,
							"kind": kind,
							"doctype": target_doctype,
							"required": required,
							"resolved": None,
						}
					)

				continue
			else:
				errors.append(f"Unsupported kind '{kind}' for source '{key}'.")
				resolved_docs[key] = None
				source_summaries.append(
					{
						"source_key": key,
						"kind": kind,
						"doctype": doctype,
						"required": required,
						"resolved": None,
					}
				)
				continue

		return {
			"primary_source_key": "primary",
			"primary": {"doctype": primary_doctype, "name": primary_name},
			"source_summaries": source_summaries,
			"errors": errors,
			"compiled_hash": compiled.get("compiled_hash") or self.compiled_hash,
		}

	@frappe.whitelist()
	def preview_values(self, primary_name, mapped_only=1, limit=250):
		self._ensure_compiled(recompile=True)

		compiled = json.loads(self.compiled_mapping or "{}")
		sources = compiled.get("sources") or {}
		elements = compiled.get("elements") or []

		if "primary" not in sources:
			return {"errors": ["No compiled primary source. Save / compile map first."]}

		primary_doctype = (sources.get("primary") or {}).get("doctype")
		if not primary_doctype:
			return {"errors": ["Primary doctype missing in compiled sources."]}

		# resolve docs once
		try:
			primary_doc = frappe.get_doc(primary_doctype, primary_name)
		except Exception as e:
			return {"errors": [f"Could not load primary doc: {e}"]}

		resolved_docs = {"primary": primary_doc}

		for key, meta in sources.items():
			if key == "primary":
				continue

			kind = (meta.get("kind") or "").strip()

			if kind == "direct_link":
				link_fieldname = (meta.get("link_fieldname") or "").strip()
				target_doctype = (meta.get("doctype") or "").strip()
				link_value = primary_doc.get(link_fieldname)

				if not link_value:
					resolved_docs[key] = None
					continue

				try:
					resolved_docs[key] = frappe.get_doc(target_doctype, link_value)
				except Exception:
					resolved_docs[key] = None
				continue

			if kind == "dynamic_link":
				link_fieldname = (meta.get("link_fieldname") or "").strip()
				doctype_fieldname = (meta.get("doctype_fieldname") or "").strip()
				expected_doctype = (meta.get("doctype") or "").strip() or "*"

				link_name = primary_doc.get(link_fieldname)
				link_doctype = primary_doc.get(doctype_fieldname)

				if not link_name or not link_doctype:
					resolved_docs[key] = None
					continue

				if expected_doctype != "*" and link_doctype != expected_doctype:
					resolved_docs[key] = None
					continue

				try:
					resolved_docs[key] = frappe.get_doc(link_doctype, link_name)
				except Exception:
					resolved_docs[key] = None
				continue

			if kind == "reverse_link":
				link_fieldname = (meta.get("link_fieldname") or "").strip()
				target_doctype = (meta.get("doctype") or "").strip()
				filters = dict(meta.get("filters") or {})
				order_by = meta.get("order_by") or []
				source_limit = cint(meta.get("limit") or 1)
				multiple = bool(meta.get("multiple"))

				filters[link_fieldname] = primary_doc.name
				order_by_text = ", ".join([o for o in order_by if isinstance(o, str) and o.strip()])

				names = frappe.get_all(
					target_doctype,
					filters=filters,
					fields=["name"],
					order_by=order_by_text or None,
					limit=source_limit,
				)

				if not names:
					resolved_docs[key] = [] if multiple else None
					continue

				if multiple:
					resolved_docs[key] = [frappe.get_doc(target_doctype, r["name"]) for r in names]
				else:
					resolved_docs[key] = frappe.get_doc(target_doctype, names[0]["name"])
				continue

			if kind == "reverse_dynamic_link":
				target_doctype = (meta.get("doctype") or "").strip()  # e.g. "Contact"
				parenttype = (meta.get("parenttype") or "").strip() or target_doctype
				parentfield = (meta.get("parentfield") or "").strip()  # e.g. "links"
				link_doctype = (meta.get("link_doctype") or "").strip()  # e.g. "Patient"
				order_by = meta.get("order_by") or []
				source_limit = cint(meta.get("limit") or 1)
				multiple = bool(meta.get("multiple"))

				if not (target_doctype and parenttype and parentfield and link_doctype):
					resolved_docs[key] = [] if multiple else None
					continue

				order_by_text = ", ".join([o for o in order_by if isinstance(o, str) and o.strip()])

				dl_rows = frappe.get_all(
					"Dynamic Link",
					filters={
						"link_doctype": link_doctype,
						"link_name": primary_doc.name,
						"parenttype": parenttype,
						"parentfield": parentfield,
					},
					fields=["parent", "idx"],
					order_by=order_by_text or "idx asc",
					limit=source_limit,
				)

				if not dl_rows:
					resolved_docs[key] = [] if multiple else None
					continue

				# keep order, de-dupe
				parent_names = []
				seen = set()
				for r in dl_rows:
					p = r.get("parent")
					if p and p not in seen:
						seen.add(p)
						parent_names.append(p)

				if not parent_names:
					resolved_docs[key] = [] if multiple else None
					continue

				try:
					if multiple:
						resolved_docs[key] = [frappe.get_doc(target_doctype, n) for n in parent_names]
					else:
						resolved_docs[key] = frappe.get_doc(target_doctype, parent_names[0])
				except Exception:
					resolved_docs[key] = [] if multiple else None
				continue

			# else:
			resolved_docs[key] = None

		results = []
		errors = []
		count = 0
		max_rows = int(limit or 250)

		for element in elements:
			if count >= max_rows:
				break

			pointer = element.get("pointer") or {}
			kind = (pointer.get("kind") or "").strip()

			if cint(mapped_only) and not kind:
				continue

			value = None
			row_errors = []

			try:
				if kind == "field":
					source_key = (pointer.get("source") or "").strip() or "primary"
					path = (pointer.get("path") or "").strip()
					doc = resolved_docs.get(source_key)
					if isinstance(doc, list):
						value = [d.get(path) for d in doc]
					else:
						value = doc.get(path) if doc else None

				elif kind == "json":
					# Intentionally strict for now (no JSONPath evaluation)
					value = None

				elif kind == "fixed":
					value = pointer.get("value")

				elif kind == "expr":
					value = {"note": "Expression preview not executed", "expr": pointer.get("expr")}

				else:
					value = None

			except Exception as e:
				row_errors.append(str(e))

			results.append(
				{
					"fhir_path": element.get("fhir_path"),
					"datatype": element.get("datatype"),
					"pointer": pointer or None,
					"value": value,
					"errors": row_errors,
				}
			)
			count += 1

		return {"results": results, "errors": errors, "compiled_hash": self.compiled_hash}

	def _ensure_compiled(self, recompile=False):
		if recompile:
			self.compile_map()
			return

		if not self.compiled_mapping:
			self.compile_map()

	# -------------------------
	# Profiles summary (optional)
	# -------------------------

	def _compile_profiles_summary(self):
		out = []
		for r in self.get("profiles") or []:
			out.append(
				{
					"fhir_profile": (getattr(r, "fhir_profile", None) or "").strip(),
					"url": (getattr(r, "url", None) or "").strip(),
					"fhir_structure_definition": (
						getattr(r, "fhir_structure_definition", None) or ""
					).strip(),
					"is_primary": cint(getattr(r, "is_primary", 0)),
					"idx": cint(getattr(r, "idx", 0)),
				}
			)
		return out

	# -------------------------
	# Helpers
	# -------------------------

	def _parse_config_json(self, config_text, source_key):
		if not config_text:
			return {}

		try:
			parsed = json.loads(config_text)
		except Exception:
			raise FHIRSourceCompilationError(f"Source '{source_key}': config must be valid JSON.")

		if not isinstance(parsed, dict):
			raise FHIRSourceCompilationError(f"Source '{source_key}': config must be a JSON object.")

		return parsed

	def _to_bool(self, value):
		return value in (1, True, "1", "true", "True", "YES", "yes", "y", "Y")

	def _to_bool_default_true(self, value):
		if value in (None, "", "null", "None"):
			return True
		return self._to_bool(value)

	def _hash_compiled_mapping(self, compiled_mapping_dict):
		normalized = json.dumps(compiled_mapping_dict, sort_keys=True, separators=(",", ":"))
		return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

	# =========================
	# StructureDefinition overlay
	# =========================

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

	# ==========================
	# PREVIEW FHIR RESOURCE
	# ==========================
	@frappe.whitelist()
	def preview_runtime_resource(self, primary_name, strict=1):
		"""
		Runtime preview: resolve sources + generate final FHIR JSON using the real generator.

		Returns:
			{
				"resource": {...} | None,
				"errors": [..],
				"warnings": [..],
				"source_summary": {...}
			}
		"""
		errors = []
		warnings = []

		if not primary_name:
			frappe.throw("primary_name is required")

		compiled = self._load_compiled_mapping_for_preview(errors)
		if errors:
			return {"resource": None, "errors": errors, "warnings": warnings, "source_summary": {}}

		primary_source_key = (compiled.get("primary_source_key") or "primary").strip()
		sources = compiled.get("sources") or {}

		try:
			resolved_docs, resolve_errors = self._resolve_all_sources(
				sources=sources,
				primary_source_key=primary_source_key,
				primary_name=primary_name,
			)
			if resolve_errors:
				errors.extend(resolve_errors)

			if errors and int(strict):
				return {
					"resource": None,
					"errors": errors,
					"warnings": warnings,
					"source_summary": self._build_source_summary(resolved_docs),
				}

			resource, gen_errors, gen_warnings = self._generate_fhir_from_compiled(
				compiled_mapping=compiled,
				resolved_docs=resolved_docs,
				primary_source_key=primary_source_key,
				strict=int(strict),
			)
			errors.extend(gen_errors or [])
			warnings.extend(gen_warnings or [])

			return {
				"resource": resource,
				"errors": errors,
				"warnings": warnings,
				"source_summary": self._build_source_summary(resolved_docs),
			}

		except Exception:
			frappe.log_error(title="FHIR runtime preview failed", message=frappe.get_traceback())
			return {
				"resource": None,
				"errors": ["Runtime preview crashed. Check error logs (Error Log)."],
				"warnings": warnings,
				"source_summary": {},
			}

	def _load_compiled_mapping_for_preview(self, errors):
		raw = (self.compiled_mapping or "").strip()
		if not raw:
			errors.append("No compiled_mapping found. Save the document to compile first.")
			return None

		try:
			compiled = json.loads(raw)
		except Exception:
			errors.append("compiled_mapping is not valid JSON. Re-save to recompile.")
			return None

		return compiled

	def _build_source_summary(self, resolved_docs):
		"""
		Safe debug summary for UI (no huge payloads).
		"""
		out = {}
		resolved_docs = resolved_docs or {}

		for key, value in resolved_docs.items():
			if not value:
				out[key] = {"status": "missing"}
				continue

			if isinstance(value, list):
				out[key] = {
					"status": "ok",
					"doctype": getattr(value[0], "doctype", None) if value else None,
					"count": len(value),
				}
			else:
				out[key] = {
					"status": "ok",
					"doctype": getattr(value, "doctype", None),
					"name": getattr(value, "name", None),
				}

		return out

	def _generate_fhir_from_compiled(
		self,
		compiled_mapping,
		resolved_docs,
		primary_source_key,
		strict,
	):
		"""
		Adapter layer so your generator stays the single source of truth.
		Replace the import + call to match your real generator entrypoint.
		"""
		errors = []
		warnings = []

		# 👇 Change this import to wherever your generator lives
		from healthcare.interoperability.fhir_engine.fhir_resource_gen import (
			FHIRResourceGenerator,
		)

		generator = FHIRResourceGenerator(
			compiled_mapping=compiled_mapping,
			resolved_docs=resolved_docs,
			primary_source_key=primary_source_key,
			strict=int(strict),
		)

		resource = generator.generate()

		# If your generator already tracks errors/warnings, pull them here:
		if hasattr(generator, "errors"):
			errors.extend(generator.errors or [])
		if hasattr(generator, "warnings"):
			warnings.extend(generator.warnings or [])

		return resource, errors, warnings


@frappe.whitelist()
def get_doctype_field_tree(doctype):
	doctype = (doctype or "").strip()
	if not doctype:
		return {"fields": [], "child_tables": []}

	meta = frappe.get_meta(doctype)

	out_fields = []
	child_tables = []

	skip_fieldtypes = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Fold"}

	for df in meta.fields or []:
		if not df.fieldname:
			continue

		if df.fieldtype == "Table" and df.options:
			child_meta = frappe.get_meta(df.options)
			child_fields = []
			for cdf in child_meta.fields or []:
				if not cdf.fieldname:
					continue
				if cdf.fieldtype in skip_fieldtypes:
					continue
				child_fields.append({"fieldname": cdf.fieldname, "label": (cdf.label or cdf.fieldname)})

			child_tables.append(
				{
					"table_field": df.fieldname,
					"label": (df.label or df.fieldname),
					"child_doctype": df.options,
					"fields": child_fields,
				}
			)
			continue

		if df.fieldtype in skip_fieldtypes:
			continue

		out_fields.append({"fieldname": df.fieldname, "label": (df.label or df.fieldname)})

	return {"fields": out_fields, "child_tables": child_tables}
