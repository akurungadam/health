# Authoring `custom_elements` — FHIR Resource Map

`custom_elements` is a JSON document on a **FHIR Resource Map** that defines how a
Frappe document is turned into a FHIR resource. It is the full-power authoring
surface: everything the visual mapping dialog can do (and everything it can't —
collections, slices, extensions, terminology) can be expressed here.

## Mental model

1. **On save**, the controller *compiles* the map (UI tables **+** `custom_elements`)
   into a single self-contained `compiled_mapping` blueprint.
2. **At generate time**, a dumb runtime consumes *only* that blueprint: it loads the
   declared **sources**, then fills each **element** path from its source.
3. `custom_elements` **wins** on a path clash with the UI grid, so you can override
   anything.

A map can be authored **entirely** in `custom_elements` (leave the grid empty) — set
`primary_doctype` + `resource_type` on the form and put the rest here.

## Top-level shape

```json
{
  "sources":    [ { ... } ],
  "elements":   [ { ... } ],
  "slices":     [ { ... } ],
  "extensions": [ { ... } ],
  "arrays":     [ "Fhir.path.to.force.as.array" ]
}
```

All keys are optional. Order doesn't matter.

---

## 1. Sources

A source is a doctype to read from. The `primary` source is implicit (it's the
form's `primary_doctype`); declare it explicitly only if you want to be tidy.

```json
{ "key": "components",
  "doctype": "Observation",
  "kind": "reverse_link",
  "parent": "primary",
  "link_fieldname": "parent_observation" }
```

| field | meaning |
|---|---|
| `key` | unique id you reference from elements (`"source": "components"`) |
| `doctype` | Frappe doctype to load |
| `kind` | how it relates to its parent (see below) |
| `is_primary` | `true` only for the primary doc |
| `parent` | key of the parent source (default `"primary"`) |
| `link_fieldname` | the link/child-table field used by the kind |
| `filters` | optional dict of extra filters |
| `fhir_path` | optional — force the collection backbone (else auto-derived) |

### Source kinds

| kind | meaning | `link_fieldname` is… |
|---|---|---|
| `document` | the primary doc itself | — |
| `direct_link` | a doc linked *from* the parent (a Link field) | the Link field on the parent |
| `child_table` | rows of a child table on the parent | the Table fieldname |
| `reverse_link` | docs that link *back* to the parent | the Link field on the child doctype |
| `dynamic_link` | docs linked via Frappe Dynamic Link (Address/Contact) | — |

`child_table`, `reverse_link`, `dynamic_link` are **collections** (many rows). The
compiler computes a **backbone** FHIR path for them (the repeating element they fill,
e.g. `Observation.component`) from the elements bound to that source — or you set
`fhir_path` explicitly. The runtime then emits **one item per row**.

---

## 2. Elements

An element maps one FHIR path to a value.

```json
{ "path": "Observation.effectiveDateTime",
  "source": "primary",
  "datatype": "dateTime",
  "value_spec": { "kind": "field", "fieldname": "posting_date" } }
```

| field | meaning |
|---|---|
| `path` | full FHIR path (e.g. `Observation.component.valueQuantity.value`) |
| `source` | source key (default `"primary"`) |
| `datatype` | FHIR datatype — drives coercion (see §7) |
| `value_spec` | how to produce the value (see §3) |
| `is_array` | force the path to be a JSON array |
| `is_required` | mark required (affects warn-only validation) |
| `reference` | for `datatype: "Reference"` (see §3.5) |

Paths are always **absolute** (start with the resource type). For a collection
source, still write the absolute path (`Observation.component.code.coding.code`); the
runtime places it under the right repeated item automatically.

**Flat shorthand** — instead of `value_spec` you may write `fieldname` / `fixed` /
`expression` directly on the element; it's inferred into a `value_spec`.

---

## 3. value_spec — producing the value

```json
"value_spec": { "kind": "field" | "fixed" | "json" | "expression", ... }
```

### 3.1 `field` — read a document field
```json
{ "kind": "field", "fieldname": "last_name" }
```
Dotted paths work: `"fieldname": "details.sex"`. Optional `"default": <x>` is used
when the field is empty.

### 3.2 `fixed` — a constant
```json
{ "kind": "fixed", "value": "phone" }
```
The value is used as-is (string, number, boolean).

### 3.3 `json` — a literal object/array (for complex datatypes)
Use this for `CodeableConcept`, `Coding`, `Identifier`, `Narrative`, etc. — anything
that isn't a primitive.
```json
{ "kind": "json",
  "value": { "coding": [ { "system": "http://loinc.org", "code": "85354-9",
                           "display": "Blood pressure panel" } ], "text": "Blood pressure" } }
```

### 3.4 `expression` — a safe Python expression over `doc`
```json
{ "kind": "expression", "expression": "doc.codification_table[0].code" }
```
`doc` is the loaded source document (a dict; child tables are lists of dicts). Runs
under `frappe.safe_eval`. Great for "first row of a child table" cases.

### 3.5 References (`datatype: "Reference"`)
```json
{ "path": "Observation.subject", "datatype": "Reference",
  "reference": { "resource_type": "Patient", "display_field": "patient_name" },
  "value_spec": { "kind": "field", "fieldname": "patient" } }
```
The field value becomes the referenced id → `{"reference":"Patient/<id>", "type":"Patient",
"display":"<display_field value>"}`. **Ids are slugified** to be FHIR-legal (a docname
`John Doe` → `Patient/John-Doe`; the original is kept in `display`).

### 3.6 `map` — inline code translation
A quick local→FHIR code table on a `field` spec. `*` is the fallback.
```json
{ "kind": "field", "fieldname": "sex",
  "map": { "Male": "male", "Female": "female", "*": "unknown" } }
```
Map **values may be objects** to build a CodeableConcept from a local code:
```json
{ "kind": "field", "fieldname": "marital_status",
  "map": { "Married": { "coding": [ { "system": ".../v3-MaritalStatus", "code": "M" } ] },
           "*": { "text": "Other" } } }
```

### 3.7 `translate` — terminology translation via Concept Map (preferred for codes)
Instead of hardcoding pairs, resolve the code from a **Concept Map** at generate time.
```json
{ "kind": "field", "fieldname": "status",
  "translate": { "system": "Healthcare Status Code", "target_system": "Observation Status" } }
```
- `system` — the local Code System the field's value belongs to.
- `target_system` — the FHIR Code System to translate into (one source can map to
  several systems; this picks the right one per resource).
- Output is shaped by the element `datatype`: a `code` element gets the bare code, a
  `CodeableConcept` element gets `{ "coding": [ ... ] }`.
- Takes precedence over `map`. No match → value omitted and a runtime issue logged
  (surfaced in the Preview banner).

See `Concept Map` / `Code Value` doctypes; codes in a `Code System` flagged **Name by
Code** are stored on documents by their bare word (e.g. `Final`).

---

## 4. arrays — forcing array cardinality

FHIR validators reject an object where an array is expected. When there's **no base
StructureDefinition** to tell the compiler an element repeats, list the absolute paths
to force into arrays:
```json
"arrays": [ "Observation.code.coding", "Observation.component.code.coding" ]
```
With a base SD present, repeating paths are detected automatically; collection
backbones and slice paths are already arrays and don't need listing.

---

## 5. Slices

Author repeating items with a fixed discriminator pattern (e.g. BP systolic/diastolic
components). Sub-element `path`s are **relative** to the slice `path`.
```json
{ "path": "Observation.component", "slice_name": "systolic", "source": "primary",
  "pattern": { "code": { "coding": [ { "system": "http://loinc.org", "code": "8480-6" } ] } },
  "elements": [
    { "path": "valueQuantity.value", "datatype": "decimal",
      "value_spec": { "kind": "field", "fieldname": "bp_systolic" } }
  ] }
```
Each slice becomes one item appended to the array at `path` (the deep-copied `pattern`
merged with the mapped sub-fields). A slice whose `elements` all resolve empty is
dropped.

> For components that are **separate child records** (the realistic BP case), prefer a
> `reverse_link` collection source over slices — see §8.

---

## 6. Extensions

```json
{ "url": "https://your-domain/fhir/StructureDefinition/religion",
  "host": "Patient",
  "value_type": "valueString",
  "is_modifier": false,
  "source": "primary",
  "value_spec": { "kind": "field", "fieldname": "religion" } }
```
| field | meaning |
|---|---|
| `url` | extension definition URL (**required**) |
| `host` | resource/path the extension attaches to (default = resource type) |
| `value_type` | the `value[x]` key, e.g. `valueString`, `valueBoolean`, `valueCode` |
| `is_modifier` | `true` → `modifierExtension` instead of `extension` |
| `value_spec` | as in §3 |

---

## 7. Datatypes & coercion

The runtime coerces primitives by `datatype`:

| datatype | behaviour |
|---|---|
| `boolean` | truthy strings (`1/true/yes`) → `true` |
| `integer`, `positiveInt`, `unsignedInt` | int |
| `decimal` | float |
| `date` | `YYYY-MM-DD` |
| `dateTime`, `instant` | tz-aware; a time gains the site timezone, a date-only value stays date-precision |
| `string`, `code`, `uri`, `id`, `markdown`, … | string |
| `Reference` | built into a reference object (§3.5) |
| `CodeableConcept`, `Coding`, `Quantity`, … | **not coerced** — supply via `kind: "json"`, a `pattern`, or `translate` |

Rule of thumb: **primitive → `field`/`fixed`/`map`/`translate`; complex → `json` /
`pattern` / `translate`.**

---

## 8. Worked example — Blood Pressure Observation (real Frappe Health data)

Panel `Observation` with `has_component=1`; Systolic/Diastolic are **child
Observations** reverse-linked by `parent_observation`; LOINC codes live in each doc's
`codification_table`; the workflow status is a local `Healthcare Status Code`.

```json
{
  "sources": [
    { "key": "primary", "doctype": "Observation", "is_primary": true },
    { "key": "components", "doctype": "Observation", "kind": "reverse_link",
      "parent": "primary", "link_fieldname": "parent_observation" },
    { "key": "panel_code", "doctype": "Codification Table", "kind": "child_table",
      "parent": "primary", "link_fieldname": "codification_table" }
  ],
  "arrays": ["Observation.component.code.coding"],
  "elements": [
    { "path": "Observation.status", "datatype": "code",
      "value_spec": { "kind": "field", "fieldname": "status",
        "translate": { "system": "Healthcare Status Code", "target_system": "Observation Status" } } },

    { "path": "Observation.category", "datatype": "CodeableConcept", "is_array": true,
      "value_spec": { "kind": "json", "value": { "coding": [
        { "system": "http://terminology.hl7.org/CodeSystem/observation-category",
          "code": "vital-signs", "display": "Vital Signs" } ] } } },

    { "path": "Observation.subject", "datatype": "Reference",
      "reference": { "resource_type": "Patient", "display_field": "patient_name" },
      "value_spec": { "kind": "field", "fieldname": "patient" } },

    { "path": "Observation.effectiveDateTime", "datatype": "dateTime",
      "value_spec": { "kind": "field", "fieldname": "posting_date" } },

    "//": "panel code from primary.codification_table (child_table collection -> Observation.code.coding)",
    { "path": "Observation.code.coding.code",    "source": "panel_code", "datatype": "code",
      "value_spec": { "kind": "field", "fieldname": "code" } },
    { "path": "Observation.code.coding.system",  "source": "panel_code", "datatype": "uri",
      "value_spec": { "kind": "field", "fieldname": "system" } },
    { "path": "Observation.code.coding.display", "source": "panel_code", "datatype": "string",
      "value_spec": { "kind": "field", "fieldname": "display" } },

    "//": "per-component code via expression over the child doc's codification table",
    { "path": "Observation.component.code.coding.code", "source": "components", "datatype": "code",
      "value_spec": { "kind": "expression", "expression": "doc.codification_table[0].code" } },
    { "path": "Observation.component.code.coding.system", "source": "components", "datatype": "uri",
      "value_spec": { "kind": "expression", "expression": "doc.codification_table[0].system" } },

    { "path": "Observation.component.valueQuantity.value", "source": "components", "datatype": "decimal",
      "value_spec": { "kind": "field", "fieldname": "result_data" } },
    { "path": "Observation.component.valueQuantity.unit", "source": "components", "datatype": "string",
      "value_spec": { "kind": "field", "fieldname": "permitted_unit" } },
    { "path": "Observation.component.valueQuantity.system", "source": "components", "datatype": "uri",
      "value_spec": { "kind": "fixed", "value": "http://unitsofmeasure.org" } }
  ]
}
```

(JSON has no comments; the `"//"` entries above are just for readability — drop them in
real maps.)

---

## 9. Gotchas

- **Complex datatypes must be objects.** A `CodeableConcept`/`Coding`/`Identifier` fed a
  bare string is rejected by validators — use `kind: "json"`, a slice `pattern`, or
  `translate`. The compiler warns on a likely "complex datatype fed a scalar".
- **`identifier.system` must be a real URI** — `example.org`/`example.com` are rejected.
- **Reference ids** are slugified to FHIR-legal tokens; if a docname has spaces the id
  becomes hyphenated and the original is preserved in `display`.
- **dateTime + timezone** is handled for you; don't append offsets manually.
- **Repeating elements** that come from a single doc (e.g. `Patient.name`) need to be in
  `arrays` (or have a base SD) or they'll emit an object instead of a list.
- Validation is **warn-only** — it never blocks save; warnings show via the form's
  `status` field + msgprint, and runtime issues show in the **Preview** banner.

---

## 10. Test & preview

- **Preview FHIR Resource** button on the form → pick a record → see the generated
  resource + any runtime issues.
- Endpoint: `generate_fhir_resource(resource_map_name, docname)` → `{resource, issues}`.
- Golden fixtures in `golden_fixtures/*.json` are runnable examples; the DB-free test
  suites (`test_fhir_compiler`, `test_fhir_runtime`, `test_fhir_golden`) exercise every
  feature above.
