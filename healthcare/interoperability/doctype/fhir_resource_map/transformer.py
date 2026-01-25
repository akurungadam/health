"""
FHIR Transformer

Transforms Frappe documents into FHIR resources using compiled mappings.

Usage:
    from fhir_transformer import FHIRTransformer

    transformer = FHIRTransformer(compiled_map)
    resource = transformer.transform("PAT-001")

    # Or with validation
    resource, errors = transformer.transform_with_validation("PAT-001")
"""

import frappe

from healthcare.interoperability.doctype.fhir_resource_map.builder import (
	FHIRResourceBuilder,
	FHIRResourceCleaner,
)
from healthcare.interoperability.doctype.fhir_resource_map.value_resolver import FHIRValueResolver


class FHIRTransformer:
	"""
	Main entry point for transforming Frappe documents to FHIR resources.
	"""

	def __init__(self, compiled_map, clean_output=True):
		"""
		Initialize transformer with a compiled mapping.

		Args:
		    compiled_map: Compiled FHIR mapping configuration
		    clean_output: Whether to remove empty values (default True)
		"""
		self.compiled_map = compiled_map or {}
		self.clean_output = clean_output

		self.resolver = None
		self.builder = FHIRResourceBuilder(compiled_map)
		self.cleaner = FHIRResourceCleaner() if clean_output else None

	def transform(self, primary_name):
		"""
		Transform a Frappe document to a FHIR resource.

		Args:
		    primary_name: Name of the primary document

		Returns:
		    dict: FHIR resource
		"""
		# Resolve values
		self.resolver = FHIRValueResolver(self.compiled_map, primary_name)
		resolved = self.resolver.resolve()

		# Build resource
		resource = self.builder.build(resolved)

		# Clean if enabled
		if self.cleaner:
			resource = self.cleaner.clean(resource)

		return resource

	def transform_with_validation(self, primary_name):
		"""
		Transform with validation of required fields.

		Args:
		    primary_name: Name of the primary document

		Returns:
		    tuple: (resource, errors)
		        - resource: FHIR resource dict
		        - errors: List of validation error dicts
		"""
		resource = self.transform(primary_name)
		errors = self.resolver.validate_required() if self.resolver else []
		return resource, errors

	def get_resolved_values(self):
		"""Get the flat resolved values from last transform."""
		if self.resolver:
			return self.resolver.resolved_values
		return {}

	def get_source_data(self):
		"""Get the loaded source documents from last transform."""
		if self.resolver:
			return self.resolver.source_data
		return {}


class FHIRBatchTransformer:
	"""
	Transform multiple documents efficiently.
	"""

	def __init__(self, compiled_map, clean_output=True):
		self.compiled_map = compiled_map
		self.clean_output = clean_output

	def transform_many(self, primary_names, stop_on_error=False):
		"""
		Transform multiple documents.

		Args:
		    primary_names: List of document names
		    stop_on_error: Stop on first error (default False)

		Returns:
		    dict: {
		        "resources": [list of resources],
		        "errors": {name: [errors]},
		        "failed": [names that failed]
		    }
		"""
		result = {
			"resources": [],
			"errors": {},
			"failed": [],
		}

		for name in primary_names:
			try:
				transformer = FHIRTransformer(self.compiled_map, self.clean_output)
				resource, errors = transformer.transform_with_validation(name)

				result["resources"].append(resource)

				if errors:
					result["errors"][name] = errors

			except Exception as e:
				result["failed"].append(name)
				result["errors"][name] = [
					{
						"type": "transform_error",
						"message": str(e),
					}
				]

				if stop_on_error:
					break

		return result

	def transform_bundle(self, primary_names, bundle_type="collection"):
		"""
		Transform multiple documents into a FHIR Bundle.

		Args:
		    primary_names: List of document names
		    bundle_type: Bundle type (default "collection")

		Returns:
		    dict: FHIR Bundle resource
		"""
		batch_result = self.transform_many(primary_names)

		entries = []
		for resource in batch_result["resources"]:
			if resource:
				entries.append({"resource": resource})

		bundle = {
			"resourceType": "Bundle",
			"type": bundle_type,
			"total": len(entries),
			"entry": entries,
		}

		return bundle


# =========================================================
# Convenience Functions
# =========================================================


def transform_to_fhir(compiled_map, primary_name, clean=True):
	"""
	Quick transform of a single document.

	Args:
	    compiled_map: Compiled mapping configuration
	    primary_name: Document name
	    clean: Remove empty values (default True)

	Returns:
	    dict: FHIR resource
	"""
	transformer = FHIRTransformer(compiled_map, clean_output=clean)
	return transformer.transform(primary_name)


def transform_to_bundle(compiled_map, primary_names, bundle_type="collection"):
	"""
	Transform multiple documents to a FHIR Bundle.

	Args:
	    compiled_map: Compiled mapping configuration
	    primary_names: List of document names
	    bundle_type: Bundle type

	Returns:
	    dict: FHIR Bundle
	"""
	batch = FHIRBatchTransformer(compiled_map)
	return batch.transform_bundle(primary_names, bundle_type)
