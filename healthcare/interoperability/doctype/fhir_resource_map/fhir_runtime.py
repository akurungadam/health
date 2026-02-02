import json

import frappe

from healthcare.interoperability.doctype.fhir_resource_map.fhir_compiler import CompiledElement


class SourceResolver:
	def resolve(self, source, context):
		raise NotImplementedError


class FrappeSourceResolver(SourceResolver):
	def resolve(self, source, context):
		if source.is_primary:
			return self._resolve_primary(source, context)

		entity_type = source.entity_type

		if entity_type == "child_table":
			return self._resolve_child_table(source, context)
		elif entity_type == "direct_link":
			return self._resolve_direct_link(source, context)
		elif entity_type == "reverse_link":
			return self._resolve_reverse_link(source, context)
		else:
			return self._resolve_document(source, context)

	def _resolve_primary(self, source, context):
		primary_id = context.get("primary_id")
		if not primary_id:
			return None

		try:
			return frappe.get_cached_doc(source.entity, primary_id).as_dict()
		except Exception:
			frappe.log_error(f"Failed to resolve primary source: {source.entity}/{primary_id}")
			return None

	def _resolve_child_table(self, source, context):
		parent_key = source.parent_source_key or "primary"
		parent_doc = context.get(parent_key)

		if not parent_doc:
			return []

		field = source.link_field
		if not field:
			return []

		return parent_doc.get(field, [])

	def _resolve_direct_link(self, source, context):
		parent_key = source.parent_source_key or "primary"
		parent_doc = context.get(parent_key)

		if not parent_doc:
			return None

		link_field = source.link_field
		if not link_field:
			return None

		linked_id = parent_doc.get(link_field)
		if not linked_id:
			return None

		try:
			return frappe.get_cached_doc(source.entity, linked_id).as_dict()
		except Exception:
			frappe.log_error(f"Failed to resolve direct_link source: {source.entity}/{linked_id}")
			return None

	def _resolve_reverse_link(self, source, context):
		parent_key = source.parent_source_key or "primary"
		parent_doc = context.get(parent_key)

		if not parent_doc:
			return []

		link_field = source.link_field
		if not link_field:
			return []

		parent_id = parent_doc.get("name")
		if not parent_id:
			return []

		filters = {link_field: parent_id}
		if source.filters:
			filters.update(source.filters)

		try:
			docs = frappe.get_all(source.entity, filters=filters, fields=["name"])

			result = []
			for doc in docs:
				full_doc = frappe.get_cached_doc(source.entity, doc.name).as_dict()
				result.append(full_doc)

			return result
		except Exception:
			frappe.log_error(f"Failed to resolve reverse_link source: {source.entity}")
			return []

	def _resolve_document(self, source, context):
		if not source.filters:
			return None

		try:
			docs = frappe.get_all(source.entity, filters=source.filters, fields=["name"], limit=1)

			if not docs:
				return None

			return frappe.get_cached_doc(source.entity, docs[0].name).as_dict()
		except Exception:
			frappe.log_error(f"Failed to resolve document source: {source.entity}")
			return None


class ValueResolver:
	def resolve(self, element, sources_data):
		source_data = sources_data.get(element.source_key)

		if source_data is None:
			return self._apply_default(element, None)

		value = self._extract_value(element, source_data)
		value = self._apply_default(element, value)
		value = self._apply_pattern(element, value)

		# Build reference if this is a reference element
		if element.is_reference() and value is not None:
			value = self._build_reference(element, value, source_data)
		else:
			value = self._transform(element, value)

		return value

	def _extract_value(self, element, source_data):
		mapping_type = element.mapping_type

		if mapping_type == CompiledElement.MAPPING_FIXED:
			return self._parse_fixed_value(element.fixed_value)

		if mapping_type == CompiledElement.MAPPING_JSON:
			return element.json_value

		if mapping_type == CompiledElement.MAPPING_EXPRESSION:
			return self._evaluate_expression(element.expression, source_data)

		if mapping_type == CompiledElement.MAPPING_FIELD:
			return self._get_field_value(element.field, source_data)

		return None

	def _parse_fixed_value(self, value):
		if value is None:
			return None

		try:
			return json.loads(value)
		except (json.JSONDecodeError, TypeError):
			return value

	def _get_field_value(self, field, source_data):
		if not field:
			return None

		field_name = field.split("|")[0].strip()
		parts = field_name.split(".")

		value = source_data
		for part in parts:
			if value is None:
				return None
			if isinstance(value, dict):
				value = value.get(part)
			else:
				return None

		return value

	def _evaluate_expression(self, expression, source_data):
		if not expression:
			return None

		try:
			allowed_names = {
				"doc": source_data,
				"str": str,
				"int": int,
				"float": float,
				"bool": bool,
				"len": len,
				"None": None,
				"True": True,
				"False": False,
			}
			return eval(expression, {"__builtins__": {}}, allowed_names)
		except Exception:
			return None

	def _apply_default(self, element, value):
		if value is None or value == "":
			if element.default_value is not None:
				return self._parse_fixed_value(element.default_value)
		return value

	def _apply_pattern(self, element, value):
		if not element.pattern_value:
			return value

		if element.is_slice():
			return value

		pattern = element.pattern_value

		if isinstance(pattern, dict) and isinstance(value, dict):
			merged = dict(pattern)
			merged.update(value)
			return merged

		if value is None:
			return pattern

		return value

	def _build_reference(self, element, value, source_data):
		if value is None or value == "":
			return None

		# Contained reference uses # prefix
		if element.is_contained_reference:
			return {"reference": f"#{value}"}

		# Build full reference
		reference = {}

		if element.reference_type:
			reference["reference"] = f"{element.reference_type}/{value}"
			reference["type"] = element.reference_type
		else:
			reference["reference"] = str(value)

		# Add display if configured
		if element.reference_display_field:
			display = self._get_field_value(element.reference_display_field, source_data)
			if display:
				reference["display"] = str(display)

		return reference

	def _transform(self, element, value):
		if value is None:
			return None

		transformer = element.transformer
		if not transformer:
			return value

		return self._apply_transformer(transformer, value)

	def _apply_transformer(self, transformer, value):
		if transformer == "string":
			return str(value) if value is not None else None

		if transformer == "boolean":
			if isinstance(value, bool):
				return value
			if isinstance(value, str):
				return value.lower() in ("true", "1", "yes")
			return bool(value)

		if transformer == "integer":
			try:
				return int(value)
			except (ValueError, TypeError):
				return None

		if transformer == "decimal":
			try:
				return float(value)
			except (ValueError, TypeError):
				return None

		if transformer == "date":
			return self._format_date(value)

		if transformer == "datetime" or transformer == "instant":
			return self._format_datetime(value)

		if transformer in ("uri", "url", "canonical", "code", "id", "oid", "uuid", "markdown"):
			return str(value) if value is not None else None

		if transformer == "positiveint" or transformer == "unsignedint":
			try:
				val = int(value)
				return val if val >= 0 else None
			except (ValueError, TypeError):
				return None

		return value

	def _format_date(self, value):
		if not value:
			return None

		if hasattr(value, "strftime"):
			return value.strftime("%Y-%m-%d")

		return str(value)[:10]

	def _format_datetime(self, value):
		if not value:
			return None

		if hasattr(value, "isoformat"):
			return value.isoformat()

		return str(value)


class FHIRRuntime:
	def __init__(self, source_resolver):
		self.source_resolver = source_resolver
		self.value_resolver = ValueResolver()

	def generate(self, compiled, primary_id):
		sources_data = self._load_sources(compiled, primary_id)
		resolved_values = self._resolve_values(compiled, sources_data)
		extensions = self._resolve_extensions(compiled, sources_data)
		slices = self._resolve_slices(compiled, sources_data)
		result = self._build_resource(compiled, resolved_values, extensions, slices)
		result = self._prune(result)
		return result

	def _load_sources(self, compiled, primary_id):
		context = {"primary_id": primary_id}
		sources_data = {}

		primary_source = compiled.get_primary_source()
		if primary_source:
			primary_doc = self.source_resolver.resolve(primary_source, context)
			sources_data["primary"] = primary_doc
			context["primary"] = primary_doc

		for source in compiled.sources:
			if source.is_primary:
				continue

			doc = self.source_resolver.resolve(source, context)
			sources_data[source.key] = doc
			context[source.key] = doc

		return sources_data

	def _resolve_values(self, compiled, sources_data):
		resolved = {}

		for element in compiled.elements:
			if element.is_extension() or element.is_slice():
				continue

			if not element.mapping_type and not element.is_required:
				continue

			source_data = sources_data.get(element.source_key)

			# Check for child table field (dot notation)
			if element.field and "." in element.field.split("|")[0]:
				values = self._resolve_child_table_field(element, source_data)
				if values:
					resolved[element.path] = values
				continue

			if isinstance(source_data, list):
				values = []
				for item in source_data:
					item_sources = dict(sources_data)
					item_sources[element.source_key] = item
					value = self.value_resolver.resolve(element, item_sources)
					if value is not None:
						values.append(value)
				if values:
					resolved[element.path] = values
			else:
				value = self.value_resolver.resolve(element, sources_data)
				if value is not None:
					resolved[element.path] = value

		return resolved

	def _resolve_extensions(self, compiled, sources_data):
		extensions = {}

		for element in compiled.elements:
			if not element.is_extension():
				continue

			source_data = sources_data.get(element.source_key)

			if isinstance(source_data, list):
				for item in source_data:
					ext_obj = self._build_extension_object(element, item, sources_data)
					if ext_obj:
						key = self._get_extension_key(element)
						if key not in extensions:
							extensions[key] = []
						extensions[key].append(ext_obj)
			else:
				ext_obj = self._build_extension_object(element, source_data, sources_data)
				if ext_obj:
					key = self._get_extension_key(element)
					if key not in extensions:
						extensions[key] = []
					extensions[key].append(ext_obj)

		return extensions

	def _build_extension_object(self, element, source_data, sources_data):
		if source_data is None:
			return None

		item_sources = dict(sources_data)
		item_sources[element.source_key] = source_data

		value = self.value_resolver.resolve(element, item_sources)

		if value is None:
			return None

		return {"url": element.extension_url, element.extension_value_type: value}

	def _get_extension_key(self, element):
		parent_path = element.parent_path
		ext_type = "modifierExtension" if element.is_modifier_extension else "extension"
		return (parent_path, ext_type)

	def _resolve_slices(self, compiled, sources_data):
		slices = {}

		for element in compiled.elements:
			if not element.is_slice():
				continue

			source_data = sources_data.get(element.source_key)

			if source_data is None:
				continue

			if isinstance(source_data, list):
				for item in source_data:
					slice_obj = self._build_slice_object(element, item, sources_data)
					if slice_obj:
						slice_of = element.slice_of
						if slice_of not in slices:
							slices[slice_of] = []
						slices[slice_of].append(slice_obj)
			else:
				slice_obj = self._build_slice_object(element, source_data, sources_data)
				if slice_obj:
					slice_of = element.slice_of
					if slice_of not in slices:
						slices[slice_of] = []
					slices[slice_of].append(slice_obj)

		return slices

	def _build_slice_object(self, element, source_data, sources_data):
		if source_data is None:
			return None

		value = None

		if element.mapping_type == CompiledElement.MAPPING_FIELD:
			value = self._get_simple_field_value(element.field, source_data)
		elif element.mapping_type == CompiledElement.MAPPING_FIXED:
			value = self.value_resolver._parse_fixed_value(element.fixed_value)
		elif element.mapping_type == CompiledElement.MAPPING_EXPRESSION:
			value = self.value_resolver._evaluate_expression(element.expression, source_data)
		elif element.mapping_type == CompiledElement.MAPPING_JSON:
			value = element.json_value

		if value is not None and element.transformer:
			value = self.value_resolver._apply_transformer(element.transformer, value)

		if value is None or value == "":
			return None

		slice_obj = {}

		if element.pattern_value and isinstance(element.pattern_value, dict):
			slice_obj = self._deep_copy(element.pattern_value)

		slice_obj["value"] = value

		return slice_obj

	def _get_simple_field_value(self, field, source_data):
		if not field or not source_data:
			return None

		field_name = field.split("|")[0].strip()
		parts = field_name.split(".")

		value = source_data
		for part in parts:
			if value is None:
				return None
			if isinstance(value, dict):
				value = value.get(part)
			else:
				return None

		return value

	def _deep_copy(self, obj):
		if isinstance(obj, dict):
			return {k: self._deep_copy(v) for k, v in obj.items()}
		if isinstance(obj, list):
			return [self._deep_copy(item) for item in obj]
		return obj

	def _resolve_child_table_field(self, element, source_data):
		if not source_data:
			return []

		field_name = element.field.split("|")[0].strip()
		parts = field_name.split(".")

		if len(parts) != 2:
			return []

		child_table_field = parts[0]
		child_field = parts[1]

		child_table = source_data.get(child_table_field, [])
		if not isinstance(child_table, list):
			return []

		values = []
		for row in child_table:
			if isinstance(row, dict):
				value = row.get(child_field)
				if value is not None:
					# Handle reference elements in child tables
					if element.is_reference():
						ref_value = self.value_resolver._build_reference(element, value, row)
						if ref_value is not None:
							values.append(ref_value)
					else:
						transformed = self.value_resolver._apply_transformer(element.transformer, value)
						if transformed is not None:
							values.append(transformed)

		return values

	def _build_resource(self, compiled, resolved_values, extensions, slices):
		resource_type = compiled.metadata.resource_type
		result = {"resourceType": resource_type}

		child_table_parents = self._detect_child_table_parents(compiled.elements, resolved_values)

		root_ext_key = (resource_type, "extension")
		if root_ext_key in extensions:
			result["extension"] = extensions[root_ext_key]

		root_mod_ext_key = (resource_type, "modifierExtension")
		if root_mod_ext_key in extensions:
			result["modifierExtension"] = extensions[root_mod_ext_key]

		for child in compiled.resource_tree.children:
			if child.name in ("extension", "modifierExtension"):
				continue

			path = resource_type + "." + child.name
			value = self._build_node(child, path, resolved_values, extensions, slices, child_table_parents)

			if path in slices:
				slice_items = slices[path]
				if value is None:
					value = slice_items
				elif isinstance(value, list):
					value = value + slice_items
				else:
					value = [value] + slice_items

			if value is not None:
				result[child.name] = value

		return result

	def _detect_child_table_parents(self, elements, resolved_values):
		parents = {}

		for element in elements:
			if element.is_extension() or element.is_slice():
				continue

			value = resolved_values.get(element.path)
			if isinstance(value, list) and len(value) > 1:
				parent_path = element.parent_path
				if parent_path:
					if parent_path not in parents:
						parents[parent_path] = 0
					parents[parent_path] = max(parents[parent_path], len(value))

		return parents

	def _build_node(self, node, path, resolved_values, extensions, slices, child_table_parents):
		if path in child_table_parents:
			return self._build_spread_array(
				node, path, resolved_values, extensions, slices, child_table_parents
			)

		if node.is_primitive:
			value = resolved_values.get(path)
			if value is None:
				return None
			if node.is_array and not isinstance(value, list):
				return [value]
			if not node.is_array and isinstance(value, list):
				return value[0] if value else None
			return value

		direct_value = resolved_values.get(path)
		if direct_value is not None and isinstance(direct_value, dict):
			if node.is_array:
				return [direct_value]
			return direct_value

		result = {}

		ext_key = (path, "extension")
		if ext_key in extensions:
			result["extension"] = extensions[ext_key]

		mod_ext_key = (path, "modifierExtension")
		if mod_ext_key in extensions:
			result["modifierExtension"] = extensions[mod_ext_key]

		for child in node.children:
			if child.name in ("extension", "modifierExtension"):
				continue

			child_path = path + "." + child.name
			child_value = self._build_node(
				child, child_path, resolved_values, extensions, slices, child_table_parents
			)

			if child_path in slices:
				slice_items = slices[child_path]
				if child_value is None:
					child_value = slice_items
				elif isinstance(child_value, list):
					child_value = child_value + slice_items
				else:
					child_value = [child_value] + slice_items

			if child_value is not None:
				result[child.name] = child_value

		if not result:
			return None

		if node.is_array:
			return [result]

		return result

	def _build_spread_array(self, node, path, resolved_values, extensions, slices, child_table_parents):
		count = child_table_parents[path]
		items = []

		for i in range(count):
			item = {}

			for child in node.children:
				if child.name in ("extension", "modifierExtension"):
					continue

				child_path = path + "." + child.name
				value = resolved_values.get(child_path)

				if value is not None:
					if isinstance(value, list) and i < len(value):
						item[child.name] = value[i]
					elif not isinstance(value, list):
						item[child.name] = value

			if item:
				items.append(item)

		return items if items else None

	def _prune(self, obj):
		if isinstance(obj, dict):
			pruned = {}
			for key, value in obj.items():
				pruned_value = self._prune(value)
				if pruned_value is not None:
					pruned[key] = pruned_value
			return pruned if pruned else None

		if isinstance(obj, list):
			pruned = []
			for item in obj:
				pruned_item = self._prune(item)
				if pruned_item is not None:
					pruned.append(pruned_item)
			return pruned if pruned else None

		if obj == "" or obj is None:
			return None

		return obj
