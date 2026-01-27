import re

_INDEX_TOKEN_RE = re.compile(r"^(?P<key>[A-Za-z0-9_]+)\[(?P<index>\d+)\]$")


class FHIRJsonPathWriter:
	"""
	Write values into nested dicts using dotted paths like 'identifier.value'.
	Supports indexed tokens like 'telecom[0].value' if you ever decide to use them.
	"""

	def set_value(self, root, dotted_path, value):
		if not dotted_path:
			return

		tokens = [p for p in str(dotted_path).split(".") if p]
		current = root

		for i, raw_token in enumerate(tokens):
			is_last = i == (len(tokens) - 1)
			key, index = self._parse_index_token(raw_token)

			if index is None:
				if is_last:
					current[key] = value
					return

				if key not in current or not isinstance(current.get(key), (dict, list)):
					current[key] = {}
				current = current[key]
				continue

			if key not in current or not isinstance(current.get(key), list):
				current[key] = []

			while len(current[key]) <= index:
				current[key].append({})

			if is_last:
				current[key][index] = value
				return

			if not isinstance(current[key][index], dict):
				current[key][index] = {}
			current = current[key][index]

	def _parse_index_token(self, token):
		match = _INDEX_TOKEN_RE.match(token or "")
		if not match:
			return token, None
		return match.group("key"), int(match.group("index"))
