"""
FHIR Resource Builder

Takes flat resolved values {element_path: value} and constructs nested FHIR resource JSON.

Handles:
- Dot notation paths (name.family -> {"name": {"family": ...}})
- Indexed array paths (name[0].given[0] -> {"name": [{"given": [...]}]})
- Spreading list values across indexed paths (for backbone elements)
- Collecting list values into arrays (for primitive arrays with is_array=True)
- Merging values into existing container objects
"""

import re


class FHIRResourceBuilder:
	def __init__(self, compiled_map):
		self.compiled_map = compiled_map or {}
		self.meta = self.compiled_map.get("meta") or {}
		self.elements = self.compiled_map.get("elements") or {}
		self.element_order = self.compiled_map.get("element_order") or []

	def build(self, resolved_values):
		"""
		Build nested FHIR resource from flat resolved values.

		Args:
		    resolved_values: dict of {element_path: value}

		Returns:
		    dict: Nested FHIR resource
		"""
		resource = {"resourceType": self.meta.get("resource_type") or "Unknown"}

		# Add id if present in meta
		resource_id = self.meta.get("id")
		if resource_id:
			resource["id"] = resource_id

		# Process elements in order
		order = self.element_order or list(resolved_values.keys())

		for element_path in order:
			if element_path not in resolved_values:
				continue

			value = resolved_values[element_path]
			if value is None:
				continue

			element = self.elements.get(element_path) or {}
			json_path = (element.get("path") or "").strip()
			is_array = element.get("is_array", False)

			if not json_path:
				continue

			# Skip bad container writes (but NOT if is_array=True)
			if self._should_skip(json_path, value, is_array):
				continue

			self._set_value(resource, json_path, value, is_array)

		return resource

	# =========================================================
	# Path Writing
	# =========================================================

	def _set_value(self, obj, path, value, is_array=False):
		"""Set a value at the given path, creating structure as needed."""
		if not path:
			return

		first_index = self._find_first_index(path)  # returns first index or None (2 if "telecom[2].value")

		# Handle is_array=True: wrap single values in list, then collect
		if is_array and first_index is not None:
			# Ensure value is a list for primitive arrays
			if not isinstance(value, list):
				value = [value]
			# COLLECT: Put entire list as the array value at this path
			# e.g., name[0].given[0] with ["John", "Smith"] -> name[0].given = ["John", "Smith"]
			# Strip the trailing index from the path
			collect_path = self._strip_last_index(path)
			self._set_single_value(obj, collect_path, value)
			return

		# Handle list values with is_array=False (spreading)
		if isinstance(value, list) and first_index is not None:
			# SPREAD: Distribute across container indexes
			# e.g., telecom[0].value with ["555-1234", "555-5678"] -> telecom[0].value, telecom[1].value
			for i, item in enumerate(value):
				indexed_path = self._replace_first_index(path, i)
				self._set_value(obj, indexed_path, item, is_array=False)
			return

		# Single value - just set it
		self._set_single_value(obj, path, value)

	def _set_single_value(self, obj, path, value):
		"""Set a single value at the path."""
		if not path:
			return

		# Merge dicts into existing container objects
		# _is_container_path: e.g., "telecom[0]" is a container, "telecom[0].value" is not.
		if self._is_container_path(path) and isinstance(value, dict):
			existing = self._get_value(obj, path)
			if isinstance(existing, dict):
				value = self._merge_dicts(existing, value)

		# Parse and navigate path
		parts = self._parse_path(path)
		current = obj

		# Navigate to parent, creating structure
		for key, index in parts[:-1]:
			current = self._ensure_path(current, key, index)

		# Set final value
		final_key, final_index = parts[-1]
		self._set_final(current, final_key, final_index, value)

	def _ensure_path(self, current, key, index):
		"""Ensure path segment exists and return next level."""
		if key not in current:
			current[key] = [] if index is not None else {}

		if index is not None:
			# Ensure list has enough elements
			if not isinstance(current[key], list):
				current[key] = []

			while len(current[key]) <= index:
				current[key].append({})

			if not isinstance(current[key][index], dict):
				current[key][index] = {}

			return current[key][index]
		else:
			if not isinstance(current[key], dict):
				current[key] = {}

			return current[key]

	def _set_final(self, current, key, index, value):
		"""Set the final value at a path endpoint."""
		if index is not None:
			# Array element
			if key not in current or not isinstance(current[key], list):
				current[key] = []

			while len(current[key]) <= index:
				current[key].append({})

			# Merge if both are dicts
			if isinstance(value, dict) and isinstance(current[key][index], dict):
				current[key][index].update(value)
			else:
				current[key][index] = value
		else:
			# Simple key
			current[key] = value

	def _get_value(self, obj, path):
		"""Get value at path, or None if not found."""
		parts = self._parse_path(path)
		current = obj

		for key, index in parts:
			if not isinstance(current, dict) or key not in current:
				return None

			current = current[key]

			if index is not None:
				if not isinstance(current, list) or len(current) <= index:
					return None
				current = current[index]

		return current

	def _merge_dicts(self, base, updates):
		"""Merge updates into base dict."""
		result = {}
		result.update(base)
		result.update(updates)
		return result

	# =========================================================
	# Path Parsing
	# =========================================================

	def _parse_path(self, path):
		"""
		Parse a FHIR path into segments.

		"name[0].given[1]" -> [("name", 0), ("given", 1)]
		"active" -> [("active", None)]
		"""
		parts = []

		for segment in (path or "").split("."):
			match = re.match(r"^(\w+)\[(\d+)\]$", segment)
			if match:
				parts.append((match.group(1), int(match.group(2))))
			else:
				parts.append((segment, None))

		return parts

	def _find_first_index(self, path):
		"""Find first array index in path, or None."""
		match = re.search(r"\[(\d+)\]", path or "")
		return int(match.group(1)) if match else None

	def _replace_first_index(self, path, new_index):
		"""Replace first array index in path."""
		return re.sub(r"\[\d+\]", f"[{new_index}]", path, count=1)

	def _strip_last_index(self, path):
		"""
		Strip the last array index from path.

		"name[0].given[0]" -> "name[0].given"
		"address[0].line[0]" -> "address[0].line"
		"""
		return re.sub(r"\[\d+\]$", "", path)

	def _is_container_path(self, path):
		"""
		Check if path points to a container object.

		Container paths end with [n] and have no further nesting.
		e.g., "telecom[0]" is a container, "telecom[0].value" is not.
		"""
		if not path:
			return False

		parts = self._parse_path(path)
		if not parts:
			return False

		last_key, last_index = parts[-1]
		return last_index is not None

	# =========================================================
	# Validation / Skip Logic
	# =========================================================

	def _should_skip(self, path, value, is_array=False):
		"""
		Determine if this value assignment should be skipped.

		Skips writing a list directly to a container path like "telecom[0]"
		UNLESS is_array=True (which means it's a primitive array that should
		be collected).
		"""
		if is_array:
			# Primitive arrays are allowed
			return False

		if not self._is_container_path(path):
			return False

		return isinstance(value, list)


class FHIRResourceCleaner:
	"""
	Cleans up a built FHIR resource.

	- Removes empty objects and arrays
	- Removes None values
	- Optionally removes empty strings
	"""

	def __init__(self, remove_empty_strings=False):
		self.remove_empty_strings = remove_empty_strings

	def clean(self, resource):
		"""Clean the resource in place and return it."""
		return self._clean_value(resource)

	def _clean_value(self, value):
		"""Recursively clean a value."""
		if isinstance(value, dict):
			return self._clean_dict(value)
		elif isinstance(value, list):
			return self._clean_list(value)
		else:
			return value

	def _clean_dict(self, d):
		"""Clean a dict, removing empty/null values."""
		cleaned = {}

		for key, value in d.items():
			clean_value = self._clean_value(value)

			if self._is_empty(clean_value):
				continue

			cleaned[key] = clean_value

		return cleaned if cleaned else None

	def _clean_list(self, lst):
		"""Clean a list, removing empty/null items."""
		cleaned = []

		for item in lst:
			clean_item = self._clean_value(item)

			if self._is_empty(clean_item):
				continue

			cleaned.append(clean_item)

		return cleaned if cleaned else None

	def _is_empty(self, value):
		"""Check if a value is empty."""
		if value is None:
			return True

		if isinstance(value, dict) and len(value) == 0:
			return True

		if isinstance(value, list) and len(value) == 0:
			return True

		if self.remove_empty_strings and value == "":
			return True

		return False


def build_fhir_resource(compiled_map, resolved_values, clean=True):
	"""
	Convenience function to build and optionally clean a FHIR resource.

	Args:
	    compiled_map: The compiled mapping configuration
	    resolved_values: Flat dict of {element_path: value}
	    clean: Whether to clean empty values (default True)

	Returns:
	    dict: The built FHIR resource
	"""
	builder = FHIRResourceBuilder(compiled_map)
	resource = builder.build(resolved_values)

	if clean:
		cleaner = FHIRResourceCleaner()
		resource = cleaner.clean(resource)

	return resource
