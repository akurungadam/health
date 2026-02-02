import json
from datetime import datetime

import frappe


class CompilationMetadata:
	def __init__(self, fhir_version, profile_url, resource_type):
		self.fhir_version = fhir_version
		self.profile_url = profile_url
		self.resource_type = resource_type
		self.compiled_at = None

	def to_dict(self):
		return {
			"fhir_version": self.fhir_version,
			"profile_url": self.profile_url,
			"resource_type": self.resource_type,
			"compiled_at": str(self.compiled_at) if self.compiled_at else None,
		}

	@classmethod
	def from_dict(cls, data):
		instance = cls(data.get("fhir_version"), data.get("profile_url"), data.get("resource_type"))
		instance.compiled_at = data.get("compiled_at")
		return instance

	def __repr__(self):
		return f"CompilationMetadata({self.resource_type}, {self.fhir_version})"


class CompiledSource:
	def __init__(self, key, entity, entity_type):
		self.key = key
		self.entity = entity
		self.entity_type = entity_type
		self.filters = {}
		self.is_primary = False
		self.is_collection = False
		self.parent_source_key = None
		self.link_field = None
		self.config = {}

	def to_dict(self):
		return {
			"key": self.key,
			"entity": self.entity,
			"entity_type": self.entity_type,
			"filters": self.filters,
			"is_primary": self.is_primary,
			"is_collection": self.is_collection,
			"parent_source_key": self.parent_source_key,
			"link_field": self.link_field,
			"config": self.config,
		}

	@classmethod
	def from_dict(cls, data):
		instance = cls(data.get("key"), data.get("entity"), data.get("entity_type"))
		instance.filters = data.get("filters", {})
		instance.is_primary = data.get("is_primary", False)
		instance.is_collection = data.get("is_collection", False)
		instance.parent_source_key = data.get("parent_source_key")
		instance.link_field = data.get("link_field")
		instance.config = data.get("config", {})
		return instance

	def __repr__(self):
		return f"CompiledSource({self.key}, {self.entity})"


class CompiledElement:
	MAPPING_FIELD = "field"
	MAPPING_FIXED = "fixed"
	MAPPING_EXPRESSION = "expression"
	MAPPING_JSON = "json"

	def __init__(self, path, source_key):
		self.path = path
		self.source_key = source_key
		self.mapping_type = None
		self.field = None
		self.expression = None
		self.fixed_value = None
		self.json_value = None
		self.default_value = None
		self.pattern_value = None
		self.transformer = None
		self.is_array = False
		self.is_required = False
		self.parent_path = None

		# Extension support
		self.extension_url = None
		self.extension_value_type = None
		self.is_modifier_extension = False

		# Slice support
		self.slice_name = None
		self.slice_of = None

		# Reference support
		self.reference_type = None
		self.reference_display_field = None
		self.is_contained_reference = False

	def to_dict(self):
		return {
			"path": self.path,
			"source_key": self.source_key,
			"mapping_type": self.mapping_type,
			"field": self.field,
			"expression": self.expression,
			"fixed_value": self.fixed_value,
			"json_value": self.json_value,
			"default_value": self.default_value,
			"pattern_value": self.pattern_value,
			"transformer": self.transformer,
			"is_array": self.is_array,
			"is_required": self.is_required,
			"parent_path": self.parent_path,
			"extension_url": self.extension_url,
			"extension_value_type": self.extension_value_type,
			"is_modifier_extension": self.is_modifier_extension,
			"slice_name": self.slice_name,
			"slice_of": self.slice_of,
			"reference_type": self.reference_type,
			"reference_display_field": self.reference_display_field,
			"is_contained_reference": self.is_contained_reference,
		}

	@classmethod
	def from_dict(cls, data):
		instance = cls(data.get("path"), data.get("source_key"))
		instance.mapping_type = data.get("mapping_type")
		instance.field = data.get("field")
		instance.expression = data.get("expression")
		instance.fixed_value = data.get("fixed_value")
		instance.json_value = data.get("json_value")
		instance.default_value = data.get("default_value")
		instance.pattern_value = data.get("pattern_value")
		instance.transformer = data.get("transformer")
		instance.is_array = data.get("is_array", False)
		instance.is_required = data.get("is_required", False)
		instance.parent_path = data.get("parent_path")
		instance.extension_url = data.get("extension_url")
		instance.extension_value_type = data.get("extension_value_type")
		instance.is_modifier_extension = data.get("is_modifier_extension", False)
		instance.slice_name = data.get("slice_name")
		instance.slice_of = data.get("slice_of")
		instance.reference_type = data.get("reference_type")
		instance.reference_display_field = data.get("reference_display_field")
		instance.is_contained_reference = data.get("is_contained_reference", False)
		return instance

	def is_extension(self):
		return self.extension_url is not None

	def is_slice(self):
		return self.slice_name is not None

	def is_reference(self):
		return self.reference_type is not None

	def has_mapping(self):
		return (
			self.field is not None
			or self.expression is not None
			or self.fixed_value is not None
			or self.json_value is not None
		)

	def has_default(self):
		return self.default_value is not None

	def has_pattern(self):
		return self.pattern_value is not None

	def __repr__(self):
		return f"CompiledElement({self.path})"


class ResourceTreeNode:
	def __init__(self, name):
		self.name = name
		self.is_array = False
		self.is_primitive = False
		self.children = []

	def to_dict(self):
		result = {"name": self.name, "is_array": self.is_array, "is_primitive": self.is_primitive}

		if self.children:
			result["children"] = [child.to_dict() for child in self.children]

		return result

	@classmethod
	def from_dict(cls, data):
		instance = cls(data.get("name"))
		instance.is_array = data.get("is_array", False)
		instance.is_primitive = data.get("is_primitive", False)

		for child_data in data.get("children", []):
			instance.children.append(cls.from_dict(child_data))

		return instance

	def add_child(self, node):
		self.children.append(node)
		return node

	def find_child(self, name):
		for child in self.children:
			if child.name == name:
				return child
		return None

	def find_by_path(self, path):
		parts = path.split(".")
		current = self

		for part in parts:
			if current is None:
				return None
			if part == current.name:
				continue
			current = current.find_child(part)

		return current

	def __repr__(self):
		return f"ResourceTreeNode({self.name})"


class CompiledResource:
	def __init__(self, metadata):
		self.metadata = metadata
		self.sources = []
		self.elements = []
		self.resource_tree = None

	def to_dict(self):
		return {
			"metadata": self.metadata.to_dict(),
			"sources": [source.to_dict() for source in self.sources],
			"elements": [element.to_dict() for element in self.elements],
			"resource_tree": self.resource_tree.to_dict() if self.resource_tree else None,
		}

	@classmethod
	def from_dict(cls, data):
		metadata = CompilationMetadata.from_dict(data.get("metadata", {}))
		instance = cls(metadata)

		for source_data in data.get("sources", []):
			instance.sources.append(CompiledSource.from_dict(source_data))

		for element_data in data.get("elements", []):
			instance.elements.append(CompiledElement.from_dict(element_data))

		tree_data = data.get("resource_tree")
		if tree_data:
			instance.resource_tree = ResourceTreeNode.from_dict(tree_data)

		return instance

	def add_source(self, source):
		self.sources.append(source)
		return source

	def add_element(self, element):
		self.elements.append(element)
		return element

	def get_source(self, key):
		for source in self.sources:
			if source.key == key:
				return source
		return None

	def get_primary_source(self):
		for source in self.sources:
			if source.is_primary:
				return source
		return None

	def get_elements_by_source(self, source_key):
		result = []
		for element in self.elements:
			if element.source_key == source_key:
				result.append(element)
		return result

	def get_elements_by_parent_path(self, parent_path):
		result = []
		for element in self.elements:
			if element.parent_path == parent_path:
				result.append(element)
		return result

	def __repr__(self):
		return f"CompiledResource({self.metadata.resource_type}, {len(self.sources)} sources, {len(self.elements)} elements)"


class FHIRCompiler:
	def __init__(self, resource_map):
		self.resource_map = resource_map
		self.compiled = None
		self._element_map_lookup = {}
		self._custom_elements = None

	def compile(self):
		self._custom_elements = self._parse_custom_elements()
		self.compiled = CompiledResource(self._build_metadata())

		if self._is_custom_only_mode():
			self._compile_from_custom_elements()
		else:
			self._compile_from_ui_config()
			self._merge_custom_additions()

		self._build_resource_tree()

		self.compiled.metadata.compiled_at = datetime.now()
		return self.compiled

	def _is_custom_only_mode(self):
		"""Custom-only when sources in custom_elements AND no UI primary doctype"""
		if not self._custom_elements:
			return False

		has_custom_sources = bool(self._custom_elements.get("sources"))
		has_ui_primary = bool(self.resource_map.primary_doctype)

		return has_custom_sources and not has_ui_primary

	def _compile_from_custom_elements(self):
		"""Compile entirely from custom_elements JSON"""
		custom = self._custom_elements

		# Sources
		for source_def in custom.get("sources", []):
			source = self._compile_custom_source(source_def)
			if source:
				self.compiled.add_source(source)

		# Elements
		for element_def in custom.get("elements", []):
			element = self._compile_custom_element(element_def)
			if element:
				self.compiled.add_element(element)

		# Extensions
		for ext_def in custom.get("extensions", []):
			element = self._compile_extension(ext_def)
			if element:
				self.compiled.add_element(element)

		# Slices
		for slice_def in custom.get("slices", []):
			element = self._compile_slice(slice_def)
			if element:
				self.compiled.add_element(element)

	def _compile_from_ui_config(self):
		"""Compile from UI-defined sources and element maps"""
		self._build_element_map_lookup()
		self._compile_sources()
		self._compile_elements()

	def _merge_custom_additions(self):
		"""Merge custom sources, elements, extensions, slices into UI-compiled result"""
		if not self._custom_elements:
			return

		# Add custom sources (without replacing existing ones)
		for source_def in self._custom_elements.get("sources", []):
			source_key = source_def.get("key")
			if not source_key:
				continue

			# Skip if source already exists from UI config
			existing = self.compiled.get_source(source_key)
			if existing:
				continue

			compiled_source = self._compile_custom_source(source_def)
			if compiled_source:
				self.compiled.add_source(compiled_source)

		# Add custom elements
		for element_def in self._custom_elements.get("elements", []):
			element = self._compile_custom_element(element_def)
			if element:
				self.compiled.add_element(element)

		# Add extensions
		for ext_def in self._custom_elements.get("extensions", []):
			element = self._compile_extension(ext_def)
			if element:
				self.compiled.add_element(element)

		# Add slices
		for slice_def in self._custom_elements.get("slices", []):
			element = self._compile_slice(slice_def)
			if element:
				self.compiled.add_element(element)

	def _parse_custom_elements(self):
		if not hasattr(self.resource_map, "custom_elements"):
			return None

		if not self.resource_map.custom_elements:
			return None

		try:
			return json.loads(self.resource_map.custom_elements)
		except (json.JSONDecodeError, TypeError):
			frappe.log_error(f"Invalid custom_elements JSON in FHIR Resource Map: {self.resource_map.name}")
			return None

	def _build_metadata(self):
		fhir_version = None
		profile_url = None

		# First try custom_elements metadata
		if self._custom_elements and self._custom_elements.get("metadata"):
			meta = self._custom_elements["metadata"]
			fhir_version = meta.get("fhir_version")
			profile_url = meta.get("profile_url")

		# Fall back to resource_map fields
		if not fhir_version:
			fhir_version = self._get_fhir_version()

		if not profile_url:
			profile_url = self._get_profile_url()

		resource_type = self.resource_map.resource_type

		return CompilationMetadata(fhir_version, profile_url, resource_type)

	def _get_fhir_version(self):
		if not self.resource_map.base_structure_definition:
			return None

		try:
			sd = frappe.get_cached_doc(
				"FHIR Structure Definition", self.resource_map.base_structure_definition
			)
			return sd.fhir_version if hasattr(sd, "fhir_version") else None
		except Exception:
			return None

	def _get_profile_url(self):
		if not hasattr(self.resource_map, "profiles"):
			return None

		for profile in self.resource_map.profiles:
			if profile.is_primary:
				return profile.url

		if self.resource_map.profiles:
			return self.resource_map.profiles[0].url

		return None

	def _build_element_map_lookup(self):
		if not hasattr(self.resource_map, "element_maps"):
			return

		for element_row in self.resource_map.element_maps:
			self._element_map_lookup[element_row.fhir_path] = element_row

	def _compile_sources(self):
		if self.resource_map.primary_doctype:
			primary = CompiledSource(
				key="primary", entity=self.resource_map.primary_doctype, entity_type="document"
			)
			primary.is_primary = True
			self.compiled.add_source(primary)

		if not hasattr(self.resource_map, "sources"):
			return

		for source_row in self.resource_map.sources:
			source = CompiledSource(
				key=source_row.source_key,
				entity=source_row.source_doctype,
				entity_type=self._normalize_source_kind(source_row.kind),
			)
			source.is_collection = source_row.kind in ("child_table", "reverse_link")
			source.link_field = source_row.link_fieldname
			source.config = self._parse_config(source_row.config)

			if source_row.kind == "child_table":
				source.parent_source_key = "primary"

			self.compiled.add_source(source)

	def _compile_custom_source(self, source_def):
		key = source_def.get("key")
		if not key:
			frappe.log_error("Custom source missing 'key' in custom_elements")
			return None

		# Skip if source already exists
		existing = self.compiled.get_source(key)
		if existing:
			return None

		doctype = source_def.get("doctype")
		if not doctype:
			frappe.log_error(f"Custom source '{key}' missing 'doctype' in custom_elements")
			return None

		kind = source_def.get("kind", "document")

		source = CompiledSource(key=key, entity=doctype, entity_type=self._normalize_source_kind(kind))

		source.is_primary = source_def.get("is_primary", key == "primary")
		source.is_collection = kind in ("child_table", "reverse_link")
		source.link_field = source_def.get("link_field")
		source.parent_source_key = source_def.get("parent_source_key", "primary")
		source.filters = source_def.get("filters", {})
		source.config = source_def.get("config", {})

		return source

	def _normalize_source_kind(self, kind):
		if not kind:
			return "document"

		kind_lower = kind.lower()

		if kind_lower == "child_table":
			return "child_table"
		elif kind_lower == "direct_link":
			return "direct_link"
		elif kind_lower == "reverse_link":
			return "reverse_link"
		else:
			return "document"

	def _parse_config(self, config_str):
		if not config_str:
			return {}

		try:
			return json.loads(config_str)
		except (json.JSONDecodeError, TypeError):
			return {}

	def _compile_elements(self):
		if not hasattr(self.resource_map, "element_maps"):
			return

		for element_row in self.resource_map.element_maps:
			if not self._should_include_element(element_row):
				continue

			element = self._compile_element(element_row)
			self.compiled.add_element(element)

	def _should_include_element(self, element_row):
		if element_row.is_required or element_row.min > 0:
			return True

		if element_row.mapping_type:
			return True

		if element_row.pattern_value:
			return True

		return False

	def _compile_element(self, element_row):
		source_key = self._get_source_key(element_row)

		element = CompiledElement(path=element_row.fhir_path, source_key=source_key)

		element.mapping_type = self._normalize_mapping_type(element_row.mapping_type)
		element.field = self._get_field(element_row)
		element.expression = element_row.expression or None
		element.fixed_value = element_row.fixed_value or None
		element.json_value = self._parse_json_value(element_row)
		element.default_value = element_row.default_value or None
		element.pattern_value = self._parse_pattern_value(element_row.pattern_value)

		element.transformer = self._determine_transformer(element_row.datatype)
		element.is_array = self._is_array(element_row.max)
		element.is_required = element_row.is_required or element_row.min > 0
		element.parent_path = self._get_parent_path(element_row.fhir_path)

		return element

	def _compile_custom_element(self, element_def):
		path = element_def.get("path")
		if not path:
			frappe.log_error("Custom element missing 'path' in custom_elements")
			return None

		source_key = element_def.get("source_key", "primary")

		if not self.compiled.get_source(source_key):
			frappe.log_error(f"Custom element '{path}' references unknown source '{source_key}'")
			return None

		element = CompiledElement(path, source_key)

		element.mapping_type = self._normalize_mapping_type(element_def.get("mapping_type"))
		element.field = element_def.get("field")
		element.expression = element_def.get("expression")
		element.fixed_value = element_def.get("fixed_value")
		element.json_value = element_def.get("json_value")
		element.default_value = element_def.get("default_value")
		element.pattern_value = element_def.get("pattern_value")

		element.transformer = self._determine_transformer(element_def.get("datatype"))
		element.is_array = element_def.get("is_array", False)
		element.is_required = element_def.get("is_required", False)
		element.parent_path = self._get_parent_path(path)

		# Reference support
		if element_def.get("datatype") == "Reference" or element_def.get("reference_type"):
			element.reference_type = element_def.get("reference_type")
			element.reference_display_field = element_def.get("reference_display_field")
			element.is_contained_reference = element_def.get("is_contained_reference", False)

		return element

	def _compile_extension(self, ext_def):
		if not ext_def.get("url"):
			frappe.log_error("Extension missing 'url' in custom_elements")
			return None

		parent_path = ext_def.get("path")
		if not parent_path:
			frappe.log_error("Extension missing 'path' in custom_elements")
			return None

		source_key = ext_def.get("source_key", "primary")

		# Validate source exists
		if not self.compiled.get_source(source_key):
			frappe.log_error(f"Extension references unknown source '{source_key}' in custom_elements")
			return None

		is_modifier = ext_def.get("is_modifier", False)
		extension_field = "modifierExtension" if is_modifier else "extension"
		element_path = f"{parent_path}.{extension_field}"

		element = CompiledElement(element_path, source_key)

		element.mapping_type = self._normalize_mapping_type(ext_def.get("mapping_type"))
		element.field = ext_def.get("field")
		element.expression = ext_def.get("expression")
		element.fixed_value = ext_def.get("fixed_value")
		element.json_value = ext_def.get("json_value")
		element.default_value = ext_def.get("default_value")

		element.extension_url = ext_def.get("url")
		element.extension_value_type = ext_def.get("value_type", "valueString")
		element.is_modifier_extension = is_modifier

		element.transformer = self._extension_value_type_to_transformer(
			ext_def.get("value_type", "valueString")
		)
		element.is_array = True
		element.is_required = ext_def.get("is_required", False)
		element.parent_path = parent_path

		return element

	def _compile_slice(self, slice_def):
		if not slice_def.get("path"):
			frappe.log_error("Slice missing 'path' in custom_elements")
			return None

		if not slice_def.get("slice_name"):
			frappe.log_error("Slice missing 'slice_name' in custom_elements")
			return None

		source_key = slice_def.get("source_key", "primary")

		# Validate source exists
		if not self.compiled.get_source(source_key):
			frappe.log_error(f"Slice references unknown source '{source_key}' in custom_elements")
			return None

		base_path = slice_def.get("path")
		slice_name = slice_def.get("slice_name")
		element_path = f"{base_path}:{slice_name}"

		element = CompiledElement(element_path, source_key)

		element.mapping_type = self._normalize_mapping_type(slice_def.get("mapping_type"))
		element.field = slice_def.get("field")
		element.expression = slice_def.get("expression")
		element.fixed_value = slice_def.get("fixed_value")
		element.json_value = slice_def.get("json_value")
		element.default_value = slice_def.get("default_value")
		element.pattern_value = slice_def.get("discriminator_value")

		element.transformer = self._determine_transformer(slice_def.get("datatype"))
		element.is_array = slice_def.get("is_array", False)
		element.is_required = slice_def.get("is_required", False)
		element.parent_path = self._get_parent_path(base_path)

		element.slice_name = slice_name
		element.slice_of = base_path

		return element

	def _extension_value_type_to_transformer(self, value_type):
		if not value_type:
			return "string"

		mapping = {
			"valueString": "string",
			"valueCode": "code",
			"valueBoolean": "boolean",
			"valueInteger": "integer",
			"valueDecimal": "decimal",
			"valueDate": "date",
			"valueDateTime": "datetime",
			"valueInstant": "instant",
			"valueUri": "uri",
			"valueUrl": "url",
			"valueCanonical": "canonical",
			"valueId": "id",
			"valueOid": "oid",
			"valueUuid": "uuid",
			"valueMarkdown": "markdown",
			"valuePositiveInt": "positiveint",
			"valueUnsignedInt": "unsignedint",
		}

		return mapping.get(value_type)

	def _get_source_key(self, element_row):
		if hasattr(element_row, "source_name") and element_row.source_name:
			return element_row.source_name

		if hasattr(element_row, "value_pointer") and element_row.value_pointer:
			try:
				pointer = json.loads(element_row.value_pointer)
				if isinstance(pointer, dict) and pointer.get("source_key"):
					return pointer["source_key"]
			except (json.JSONDecodeError, TypeError):
				pass

		return "primary"

	def _get_field(self, element_row):
		if element_row.frappe_field:
			return element_row.frappe_field

		if hasattr(element_row, "value_pointer") and element_row.value_pointer:
			try:
				pointer = json.loads(element_row.value_pointer)
				if isinstance(pointer, dict) and pointer.get("kind") == "field":
					fieldname = pointer.get("fieldname")
					if fieldname:
						return fieldname
			except (json.JSONDecodeError, TypeError):
				pass

		return None

	def _normalize_mapping_type(self, mapping_type):
		if not mapping_type:
			return None

		mapping_type_lower = mapping_type.lower()

		if mapping_type_lower in ("frappe field", "field"):
			return CompiledElement.MAPPING_FIELD
		elif mapping_type_lower == "fixed":
			return CompiledElement.MAPPING_FIXED
		elif mapping_type_lower == "expression":
			return CompiledElement.MAPPING_EXPRESSION
		elif mapping_type_lower == "json":
			return CompiledElement.MAPPING_JSON

		return None

	def _parse_json_value(self, element_row):
		if element_row.mapping_type != "JSON":
			return None

		value = element_row.fixed_value or element_row.expression
		if not value:
			return None

		try:
			return json.loads(value)
		except (json.JSONDecodeError, TypeError):
			return None

	def _parse_pattern_value(self, pattern_value):
		if not pattern_value:
			return None

		if isinstance(pattern_value, dict):
			return pattern_value

		try:
			return json.loads(pattern_value)
		except (json.JSONDecodeError, TypeError):
			return pattern_value

	def _determine_transformer(self, datatype):
		if not datatype:
			return None

		datatype_lower = datatype.lower()

		primitive_types = {
			"string": "string",
			"boolean": "boolean",
			"integer": "integer",
			"decimal": "decimal",
			"date": "date",
			"datetime": "datetime",
			"instant": "instant",
			"time": "time",
			"uri": "uri",
			"url": "url",
			"canonical": "canonical",
			"code": "code",
			"id": "id",
			"oid": "oid",
			"uuid": "uuid",
			"markdown": "markdown",
			"base64binary": "base64binary",
			"positiveint": "positiveint",
			"unsignedint": "unsignedint",
		}

		return primitive_types.get(datatype_lower)

	def _is_array(self, max_cardinality):
		if not max_cardinality:
			return False

		if max_cardinality == "*":
			return True

		try:
			return int(max_cardinality) > 1
		except ValueError:
			return False

	def _get_parent_path(self, path):
		if not path or "." not in path:
			return None

		parts = path.rsplit(".", 1)
		return parts[0]

	def _build_resource_tree(self):
		resource_type = self.compiled.metadata.resource_type
		root = ResourceTreeNode(resource_type)
		root.is_array = False
		root.is_primitive = False

		for element in self.compiled.elements:
			self._add_path_to_tree(root, element)

		self.compiled.resource_tree = root

	def _add_path_to_tree(self, root, element):
		path = element.path

		# Handle slice paths
		if ":" in path:
			path = path.split(":")[0]

		# Skip extension paths
		if element.is_extension():
			return

		parts = path.split(".")

		if parts and parts[0] == root.name:
			parts = parts[1:]

		current = root
		current_path = root.name

		for i, part in enumerate(parts):
			current_path = current_path + "." + part
			is_last = i == len(parts) - 1

			child = current.find_child(part)

			if child is None:
				child = ResourceTreeNode(part)
				child.is_array = self._is_path_array_from_element(current_path)
				child.is_primitive = False
				current.add_child(child)

			if self._is_path_array_from_element(current_path):
				child.is_array = True

			if is_last:
				if element.is_array:
					child.is_array = True
				child.is_primitive = element.transformer is not None

			current = child

	def _is_path_array_from_element(self, path):
		# Check UI-defined elements
		element_row = self._element_map_lookup.get(path)
		if element_row:
			return self._is_array(element_row.max)

		# Check compiled elements
		for element in self.compiled.elements:
			if element.path == path:
				return element.is_array

		return False
