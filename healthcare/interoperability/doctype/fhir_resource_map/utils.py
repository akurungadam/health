import re

# =========================================================
# Common Utilities
# =========================================================


class FHIRUtils:
	"""Shared utility methods used across FHIR classes."""

	@staticmethod
	def get_dotted_value(data, fieldname):
		"""
		Traverse nested dict/list using dot notation.
		- If a list is encountered, returns that list (caller decides how to handle).
		- Works with dicts and objects.
		"""
		if data is None or not fieldname:
			return None

		parts = str(fieldname).split(".")
		current = data

		for part in parts:
			if current is None:
				return None

			if isinstance(current, dict):
				current = current.get(part)
			elif isinstance(current, list):
				return current
			else:
				current = getattr(current, part, None)

		return current

	@staticmethod
	def is_empty(value):
		"""Check if value is None or empty list/dict/string."""
		if value is None:
			return True
		if isinstance(value, str) and not value.strip():
			return True
		if isinstance(value, list) and len(value) == 0:
			return True
		if isinstance(value, dict) and len(value) == 0:
			return True
		return False

	@staticmethod
	def parse_path(path):
		"""
		Parse JSON path into segments.
		e.g., "identifier[0].value" -> ["identifier", 0, "value"]
		"""
		if not path:
			return []

		segments = []
		parts = str(path).split(".")

		for part in parts:
			match = re.match(r"(\w+)\[(\d+)\]", part)
			if match:
				segments.append(match.group(1))
				segments.append(int(match.group(2)))
			else:
				segments.append(part)

		return segments
