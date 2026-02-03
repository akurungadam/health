import json
from datetime import datetime

import frappe

"""
FHIR Compiled Output Classes

Data classes representing the compiled output of a FHIR Resource Map.
These are serializable and can be stored/restored for efficient runtime generation.
"""


class CompilationMetadata:
	"""Metadata about the compilation"""

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
		instance = cls(
			data.get("fhir_version"),
			data.get("profile_url"),
			data.get("resource_type"),
		)
		compiled_at = data.get("compiled_at")
		if compiled_at:
			instance.compiled_at = compiled_at
		return instance

	def __repr__(self):
		return f"CompilationMetadata({self.resource_type}, {self.fhir_version})"


class CompiledSource:
	"""Compiled data source configuration"""

	def __init__(self, key, entity, entity_type="document"):
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
		instance = cls(
			data.get("key"),
			data.get("entity"),
			data.get("entity_type", "document"),
		)
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
	"""Compiled element mapping configuration"""

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
		self.contained_resource_map = None
		self.contained_id_field = None

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
			"contained_resource_map": self.contained_resource_map,
			"contained_id_field": self.contained_id_field,
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
		instance.contained_resource_map = data.get("contained_resource_map")
		instance.contained_id_field = data.get("contained_id_field")
		return instance

	def is_extension(self):
		return self.extension_url is not None

	def is_slice(self):
		return self.slice_name is not None

	def is_reference(self):
		return self.reference_type is not None or self.is_contained_reference

	def is_full_contained_reference(self):
		return self.is_contained_reference and self.contained_resource_map is not None

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
	"""Node in the FHIR resource structure tree"""

	def __init__(self, name):
		self.name = name
		self.is_array = False
		self.is_primitive = False
		self.children = []

	def add_child(self, child):
		self.children.append(child)
		return child

	def find_child(self, name):
		for child in self.children:
			if child.name == name:
				return child
		return None

	def find_by_path(self, path):
		parts = path.split(".")
		if not parts:
			return None

		if parts[0] == self.name:
			parts = parts[1:]

		current = self
		for part in parts:
			found = current.find_child(part)
			if not found:
				return None
			current = found

		return current

	def to_dict(self):
		result = {
			"name": self.name,
			"is_array": self.is_array,
			"is_primitive": self.is_primitive,
		}
		if self.children:
			result["children"] = [child.to_dict() for child in self.children]
		return result

	@classmethod
	def from_dict(cls, data):
		instance = cls(data.get("name"))
		instance.is_array = data.get("is_array", False)
		instance.is_primitive = data.get("is_primitive", False)
		for child_data in data.get("children", []):
			instance.add_child(cls.from_dict(child_data))
		return instance

	def __repr__(self):
		return f"ResourceTreeNode({self.name})"


class CompiledResource:
	"""Complete compiled resource representation"""

	def __init__(self, metadata):
		self.metadata = metadata
		self.sources = []
		self.elements = []
		self.resource_tree = None

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
		return [el for el in self.elements if el.source_key == source_key]

	def get_elements_by_parent_path(self, parent_path):
		return [el for el in self.elements if el.parent_path == parent_path]

	def to_dict(self):
		return {
			"metadata": self.metadata.to_dict(),
			"sources": [s.to_dict() for s in self.sources],
			"elements": [e.to_dict() for e in self.elements],
			"resource_tree": self.resource_tree.to_dict() if self.resource_tree else None,
		}

	@classmethod
	def from_dict(cls, data):
		metadata = CompilationMetadata.from_dict(data.get("metadata", {}))
		instance = cls(metadata)
		for source_data in data.get("sources", []):
			instance.add_source(CompiledSource.from_dict(source_data))
		for element_data in data.get("elements", []):
			instance.add_element(CompiledElement.from_dict(element_data))
		tree_data = data.get("resource_tree")
		if tree_data:
			instance.resource_tree = ResourceTreeNode.from_dict(tree_data)
		return instance

	def __repr__(self):
		return f"CompiledResource({self.metadata.resource_type}, {len(self.sources)} sources, {len(self.elements)} elements)"


"""
FHIR Resource Map Compiler

Compiles FHIR Resource Map configurations into optimized executable blueprints.
Supports UI-based configuration, custom_elements JSON, and hybrid modes.
"""


class FHIRCompilationError(Exception):
	"""Exception raised during FHIR resource map compilation"""

	def __init__(self, message, path=None, details=None):
		super().__init__(message)
		self.message = message
		self.path = path
		self.details = details or {}

	def to_dict(self):
		return {
			"message": self.message,
			"path": self.path,
			"details": self.details,
		}


class FHIRCompiler:
	"""Compiles FHIR Resource Map into executable blueprint"""

	# primitive FHIR datatypes that need transformers
	PRIMITIVE_TYPES = {
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

	def __init__(self, resource_map):
		self.resource_map = resource_map
		self._custom_elements = None
		self.compiled = None
		self.errors = []

	def get_errors(self):
		"""Return compilation errors"""
		return self.errors

	def compile(self):
		"""Compile the resource map into a CompiledResource"""
		self.errors = []
		self._custom_elements = self._parse_custom_elements()
		self.compiled = CompiledResource(self._build_metadata())  # uses self._custom_elements
		try:
			if self._is_custom_only_mode():
				self._compile_from_custom_elements()
			else:
				self._compile_from_ui_config()
				self._merge_custom_additions()

			self._build_resource_tree()
			self.compiled.metadata.compiled_at = datetime.now()

		except FHIRCompilationError:
			raise
		except Exception as e:
			frappe.log_error(f"FHIR compilation failed: {e!s}", "FHIR Compiler Error")
			raise FHIRCompilationError("Compilation failed unexpectedly", details={"error": str(e)})

		return self.compiled

	def _parse_custom_elements(self):
		"""Parse custom_elements JSON field"""
		if not self.resource_map.custom_elements:
			return None

		try:
			return json.loads(self.resource_map.custom_elements)
		except (json.JSONDecodeError, TypeError) as e:
			self.errors.append(
				{
					"type": "parse_error",
					"message": f"Invalid custom_elements JSON: {e!s}",
				}
			)
			return None

	def _is_custom_only_mode(self):
		"""
		Check if custom_elements defines sources - if so, use it exclusively.
		Custom-only mode when sources in custom_elements AND no UI primary doctype.
		"""
		if not self._custom_elements:
			return False

		has_custom_sources = bool(self._custom_elements.get("sources"))
		has_ui_primary = bool(self.resource_map.primary_doctype)

		return has_custom_sources and not has_ui_primary

	def _build_metadata(self):
		"""Build compilation metadata, using resource_map.resource_type"""
		fhir_version = None
		profile_url = None
		resource_type = None

		if self._custom_elements:
			custom_meta = self._custom_elements.get("metadata", {})
			fhir_version = custom_meta.get("fhir_version")
			profile_url = custom_meta.get("profile_url")
			resource_type = custom_meta.get("resource_type")

		# fallback to structure definition for fhir_version and profile_url
		if not fhir_version or not profile_url:
			sd = self.resource_map.base_structure_definition
			if sd:
				sd_doc = frappe.get_cached_doc("FHIR Structure Definition", sd)
				if not fhir_version:
					fhir_version = sd_doc.fhir_version
				if not profile_url:
					profile_url = sd_doc.url

		# NOTE: always use resource_map.resource_type for the resource type
		if not resource_type:
			resource_type = self.resource_map.resource_type

		return CompilationMetadata(fhir_version, profile_url, resource_type)

	# =========================================================================
	# UI Config Compilation
	# =========================================================================

	def _compile_from_ui_config(self):
		"""Compile from UI-configured tables"""
		self._compile_ui_sources()
		self._compile_ui_elements()

	def _compile_ui_sources(self):
		"""Compile sources from UI configuration"""
		# primary source
		if self.resource_map.primary_doctype:
			primary = CompiledSource("primary", self.resource_map.primary_doctype, "document")
			primary.is_primary = True
			primary.parent_source_key = "primary"
			self.compiled.add_source(primary)

		# additional sources from sources table
		for source_row in self.resource_map.sources:
			source = self._compile_ui_source_row(source_row)
			if source:
				self.compiled.add_source(source)

	def _compile_ui_source_row(self, row):
		"""Compile a single source row from UI"""
		key = row.get("source_key")
		if not key:
			return None

		entity = row.get("source_doctype")
		if not entity:
			return None

		entity_type = self._normalize_source_kind(row.get("kind"))
		source = CompiledSource(key, entity, entity_type)
		source.is_primary = row.get("is_primary", False)
		source.parent_source_key = row.get("parent_source_key") or "primary"
		source.link_field = row.get("link_fieldname")

		if entity_type in ("child_table", "reverse_link"):
			source.is_collection = True

		return source

	def _compile_ui_elements(self):
		"""Compile elements from UI configuration"""
		for row in self.resource_map.element_maps:
			element = self._compile_ui_element_row(row)
			if element:
				self.compiled.add_element(element)

	def _compile_ui_element_row(self, row):
		"""Compile a single element row from UI"""
		path = row.get("fhir_path")
		if not path:
			return None

		# skip if no mapping and not required
		mapping_type = row.get("mapping_type")
		has_mapping = mapping_type and mapping_type != "None"
		is_required = row.get("min") and int(row.get("min", 0)) > 0

		if not has_mapping and not is_required:
			return None

		# extract source key from value_pointer or use primary
		source_key = self._extract_source_key(row)
		element = CompiledElement(path, source_key)

		# mapping configuration
		element.mapping_type = self._normalize_mapping_type(mapping_type)

		if element.mapping_type == CompiledElement.MAPPING_FIELD:
			element.field = row.get("frappe_field") or row.get("field")
		elif element.mapping_type == CompiledElement.MAPPING_FIXED:
			element.fixed_value = row.get("fixed_value")
		elif element.mapping_type == CompiledElement.MAPPING_EXPRESSION:
			element.expression = row.get("expression")
		elif element.mapping_type == CompiledElement.MAPPING_JSON:
			element.json_value = self._parse_json_value(row.get("json_value"))

		# Transformer
		element.transformer = self._determine_transformer(row.get("datatype"))

		# Cardinality
		element.is_array = self._is_array(row.get("max"))
		element.is_required = is_required

		# Parent path
		element.parent_path = self._get_parent_path(path)

		return element

	def _extract_source_key(self, row):
		"""Extract source key from value_pointer JSON or return 'primary'"""
		value_pointer = row.get("value_pointer")
		if not value_pointer:
			return "primary"

		try:
			pointer_data = json.loads(value_pointer)
			return pointer_data.get("source_key") or "primary"
		except (json.JSONDecodeError, TypeError):
			return "primary"

	# =========================================================================
	# Custom Elements Compilation
	# =========================================================================

	def _compile_from_custom_elements(self):
		"""Compile entirely from custom_elements JSON"""
		self._compile_custom_sources()
		self._compile_custom_elements()
		self._compile_custom_extensions()
		self._compile_custom_slices()

	def _compile_custom_sources(self):
		"""Compile sources from custom_elements"""
		sources = self._custom_elements.get("sources", [])
		seen_keys = set()

		for source_def in sources:
			key = source_def.get("key")
			if not key:
				self.errors.append(
					{
						"type": "validation_error",
						"message": "Source missing 'key'",
						"details": source_def,
					}
				)
				continue

			if key in seen_keys:
				self.errors.append(
					{
						"type": "validation_error",
						"message": f"Duplicate source key: {key}",
						"details": source_def,
					}
				)
				continue

			source = self._compile_custom_source(source_def)
			if source:
				self.compiled.add_source(source)
				seen_keys.add(key)

	def _compile_custom_source(self, source_def):
		"""Compile a single custom source definition"""
		key = source_def.get("key")
		doctype = source_def.get("doctype")

		if not key or not doctype:
			self.errors.append(
				{
					"type": "validation_error",
					"message": "Source missing 'key' or 'doctype'",
					"details": source_def,
				}
			)
			return None

		entity_type = self._normalize_source_kind(source_def.get("kind"))
		source = CompiledSource(key, doctype, entity_type)
		source.is_primary = source_def.get("is_primary", False)
		source.is_collection = source_def.get("is_collection", False)
		source.parent_source_key = source_def.get("parent_source_key", "primary")
		source.link_field = source_def.get("link_field")
		source.filters = source_def.get("filters", {})

		if entity_type in ("child_table", "reverse_link"):
			source.is_collection = True

		return source

	def _compile_custom_elements(self):
		"""Compile elements from custom_elements"""
		elements = self._custom_elements.get("elements", [])

		for element_def in elements:
			element = self._compile_custom_element(element_def)
			if element:
				self.compiled.add_element(element)

	def _compile_custom_element(self, element_def):
		"""Compile a single custom element definition"""
		path = element_def.get("path")
		if not path:
			self.errors.append(
				{
					"type": "validation_error",
					"message": "Element missing 'path'",
					"details": element_def,
				}
			)
			return None

		source_key = element_def.get("source_key", "primary")

		if not self.compiled.get_source(source_key):
			self.errors.append(
				{
					"type": "validation_error",
					"message": f"Element '{path}' references unknown source '{source_key}'",
					"details": element_def,
				}
			)
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
		if (
			element_def.get("datatype") == "Reference"
			or element_def.get("reference_type")
			or element_def.get("is_contained_reference")
		):
			element.reference_type = element_def.get("reference_type")
			element.reference_display_field = element_def.get("reference_display_field")
			element.is_contained_reference = element_def.get("is_contained_reference", False)
			element.contained_resource_map = element_def.get("contained_resource_map")
			element.contained_id_field = element_def.get("contained_id_field")

		return element

	def _compile_custom_extensions(self):
		"""Compile extensions from custom_elements"""
		extensions = self._custom_elements.get("extensions", [])

		for ext_def in extensions:
			element = self._compile_extension(ext_def)
			if element:
				self.compiled.add_element(element)

	def _compile_extension(self, ext_def):
		"""Compile a single extension definition"""
		url = ext_def.get("url")
		path = ext_def.get("path")

		if not url or not path:
			self.errors.append(
				{
					"type": "validation_error",
					"message": "Extension missing 'url' or 'path'",
					"details": ext_def,
				}
			)
			return None

		source_key = ext_def.get("source_key", "primary")

		if not self.compiled.get_source(source_key):
			self.errors.append(
				{
					"type": "validation_error",
					"message": f"Extension references unknown source '{source_key}'",
					"details": ext_def,
				}
			)
			return None

		is_modifier = ext_def.get("is_modifier", False)
		ext_field = "modifierExtension" if is_modifier else "extension"

		# extension path is parent.extension or parent.modifierExtension
		if path.endswith(".extension") or path.endswith(".modifierExtension"):
			ext_path = path
		else:
			ext_path = f"{path}.{ext_field}"

		element = CompiledElement(ext_path, source_key)
		element.extension_url = url
		element.extension_value_type = ext_def.get("value_type", "valueString")
		element.is_modifier_extension = is_modifier

		element.mapping_type = self._normalize_mapping_type(ext_def.get("mapping_type"))
		element.field = ext_def.get("field")
		element.expression = ext_def.get("expression")
		element.fixed_value = ext_def.get("fixed_value")
		element.json_value = ext_def.get("json_value")

		element.transformer = self._extension_value_type_to_transformer(element.extension_value_type)
		element.is_array = True
		element.parent_path = path

		return element

	def _compile_custom_slices(self):
		"""Compile slices from custom_elements"""
		slices = self._custom_elements.get("slices", [])

		for slice_def in slices:
			element = self._compile_slice(slice_def)
			if element:
				self.compiled.add_element(element)

	def _compile_slice(self, slice_def):
		"""Compile a single slice definition"""
		path = slice_def.get("path") or slice_def.get("slice_of")
		slice_name = slice_def.get("slice_name")

		if not path or not slice_name:
			self.errors.append(
				{
					"type": "validation_error",
					"message": "Slice missing 'path' or 'slice_name'",
					"details": slice_def,
				}
			)
			return None

		source_key = slice_def.get("source_key", "primary")

		if not self.compiled.get_source(source_key):
			self.errors.append(
				{
					"type": "validation_error",
					"message": f"Slice references unknown source '{source_key}'",
					"details": slice_def,
				}
			)
			return None

		# slice path format: base_path:slice_name
		slice_path = f"{path}:{slice_name}"

		element = CompiledElement(slice_path, source_key)
		element.slice_name = slice_name
		element.slice_of = path

		element.mapping_type = self._normalize_mapping_type(slice_def.get("mapping_type"))
		element.field = slice_def.get("field")
		element.expression = slice_def.get("expression")
		element.fixed_value = slice_def.get("fixed_value")
		element.json_value = slice_def.get("json_value")

		element.transformer = self._determine_transformer(slice_def.get("datatype"))
		element.is_array = slice_def.get("is_array", False)
		element.is_required = slice_def.get("is_required", False)
		element.parent_path = self._get_parent_path(path)

		# Pattern/discriminator value
		element.pattern_value = (
			slice_def.get("pattern") or slice_def.get("pattern_value") or slice_def.get("discriminator_value")
		)

		return element

	# =========================================================================
	# Hybrid Mode - Merge Custom into UI
	# =========================================================================

	def _merge_custom_additions(self):
		"""Merge custom sources, elements, extensions, slices into UI-compiled result"""
		if not self._custom_elements:
			return

		# Add custom sources (without replacing existing ones)
		for source_def in self._custom_elements.get("sources", []):
			source_key = source_def.get("key")
			if not source_key:
				continue

			existing = self.compiled.get_source(source_key)
			if existing:
				continue

			source = self._compile_custom_source(source_def)
			if source:
				self.compiled.add_source(source)

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

	# =========================================================================
	# Resource Tree Building
	# =========================================================================

	def _build_resource_tree(self):
		"""Build the resource structure tree from compiled elements"""
		resource_type = self.compiled.metadata.resource_type
		root = ResourceTreeNode(resource_type)

		for element in self.compiled.elements:
			self._add_path_to_tree(root, element)

		self.compiled.resource_tree = root

	def _add_path_to_tree(self, root, element):
		"""Add an element's path to the tree"""
		if element.is_extension():
			return

		path = element.path

		# Handle slice paths (remove :slice_name)
		if ":" in path:
			path = path.split(":")[0]

		parts = path.split(".")

		# Strip root if it matches resource type
		if parts and parts[0] == root.name:
			parts = parts[1:]

		if not parts:
			return

		current = root
		for i, part in enumerate(parts):
			child = current.find_child(part)
			if child is None:
				child = ResourceTreeNode(part)
				current.add_child(child)

			# Update node properties from element (last part)
			if i == len(parts) - 1:
				if element.is_array:
					child.is_array = True
				if element.transformer:
					child.is_primitive = True

			current = child

	# =========================================================================
	# Helper Methods
	# =========================================================================

	def _normalize_mapping_type(self, mapping_type):
		"""Normalize mapping type string to constant"""
		if not mapping_type:
			return None

		mapping_type_lower = mapping_type.lower().replace(" ", "_")

		if mapping_type_lower in ("frappe_field", "field"):
			return CompiledElement.MAPPING_FIELD
		if mapping_type_lower == "fixed":
			return CompiledElement.MAPPING_FIXED
		if mapping_type_lower == "expression":
			return CompiledElement.MAPPING_EXPRESSION
		if mapping_type_lower == "json":
			return CompiledElement.MAPPING_JSON

		return None

	def _normalize_source_kind(self, kind):
		"""Normalize source kind to entity_type"""
		if not kind:
			return "document"

		kind_lower = kind.lower().replace(" ", "_")

		if kind_lower in ("document", "child_table", "direct_link", "reverse_link"):
			return kind_lower

		return "document"

	def _determine_transformer(self, datatype):
		"""Determine transformer for a datatype"""
		if not datatype:
			return None

		datatype_lower = datatype.lower()
		return self.PRIMITIVE_TYPES.get(datatype_lower)

	def _extension_value_type_to_transformer(self, value_type):
		"""Convert extension value type to transformer"""
		if not value_type:
			return "string"

		mapping = {
			"valueString": "string",
			"valueBoolean": "boolean",
			"valueInteger": "integer",
			"valueDecimal": "decimal",
			"valueDate": "date",
			"valueDateTime": "datetime",
			"valueInstant": "instant",
			"valueCode": "code",
			"valueUri": "uri",
			"valueUrl": "url",
			"valueCanonical": "canonical",
			"valueId": "id",
			"valueMarkdown": "markdown",
			"valuePositiveInt": "positiveint",
			"valueUnsignedInt": "unsignedint",
		}

		return mapping.get(value_type)

	def _is_array(self, max_cardinality):
		"""Check if element is an array based on max cardinality"""
		if max_cardinality is None:
			return False

		if max_cardinality == "*":
			return True

		try:
			return int(max_cardinality) > 1
		except (ValueError, TypeError):
			return False

	def _get_parent_path(self, path):
		"""Get parent path from element path"""
		if not path:
			return None

		if ":" in path:
			path = path.split(":")[0]

		parts = path.rsplit(".", 1)

		# Root level path (no dots) returns None
		if len(parts) == 1:
			return None

		return parts[0]

	def _parse_json_value(self, json_str):
		"""Parse JSON string value"""
		if not json_str:
			return None

		try:
			return json.loads(json_str)
		except (json.JSONDecodeError, TypeError):
			return None
