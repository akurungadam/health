# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and Contributors
# See license.txt

"""
Golden-fixture regression tests for FHIRRuntime.

Each file in ``golden_fixtures/`` is a self-contained case:

    {
      "description": "...",                # human note, ignored by the runtime
      "compiled":   { ... },               # a compiled_mapping blueprint
      "sources":    { "primary": {...} },  # source docs, injected (no DB reads)
      "primary_id": "X-1",
      "expected":   { "resourceType": ... }# the FHIR resource the runtime must produce
    }

The runtime is fed the compiled mapping and the sources are injected directly (by
replacing ``_load_sources``), so the cases run without a database. This locks the
generated FHIR JSON for priority resources into CI; when an intentional change to
the engine alters the output, regenerate the ``expected`` blocks with:

    UPDATE_GOLDEN=1 bench --site <site> run-tests \
        --module healthcare.interoperability.doctype.fhir_resource_map.test_fhir_golden

Review the diff before committing - a regeneration is only correct if you meant to
change the output.
"""

import glob
import json
import os
import unittest

from healthcare.interoperability.doctype.fhir_resource_map.fhir_runtime import FHIRRuntime

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "golden_fixtures")


def generate(fixture):
	runtime = FHIRRuntime(fixture["compiled"])
	sources = fixture.get("sources", {})
	runtime._load_sources = lambda _pid: runtime.source_docs.update(sources)
	return runtime.generate(fixture.get("primary_id"))


class TestFHIRGoldenFixtures(unittest.TestCase):
	def test_golden_fixtures(self):
		paths = sorted(glob.glob(os.path.join(FIXTURE_DIR, "*.json")))
		self.assertTrue(paths, f"No golden fixtures found in {FIXTURE_DIR}")

		update = os.environ.get("UPDATE_GOLDEN") == "1"
		for path in paths:
			with self.subTest(fixture=os.path.basename(path)):
				with open(path, encoding="utf-8") as handle:
					fixture = json.load(handle)

				resource = generate(fixture)

				if update:
					fixture["expected"] = resource
					with open(path, "w", encoding="utf-8") as handle:
						json.dump(fixture, handle, indent=2, ensure_ascii=False)
						handle.write("\n")
					continue

				self.assertEqual(
					resource,
					fixture["expected"],
					f"{os.path.basename(path)} output drifted from its golden expected resource",
				)


if __name__ == "__main__":
	unittest.main()
