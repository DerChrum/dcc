# DCC ontology single-table template (ROBOT/ODK friendly)

This document sketches a single CSV sheet for defining the DCC ontology. The layout borrows from ROBOT templates used by the Ontology Development Kit while preserving the row-per-entity ergonomics of the existing `Mapping_SOSASSN.xlsx` TBox sheet.

## Column set

| Column | Purpose / allowed values | Notes |
| --- | --- | --- |
| `id` | Required CURIE/IRI for the entity. | One row per entity; stable identifier. |
| `label` | Preferred label. | Language-tagged literals permitted. |
| `entity_type` | One of `Class`, `ObjectProperty`, `DataProperty`, `AnnotationProperty`, `Individual`. | Drives validation and export rules. |
| `dccx_alignment` | CURIE pointing to the authoritative DCC schema class/property this entity refines or mirrors. | For classes/properties only; use `dccx:None` when intentionally unaligned. |
| `status` | `proposed`, `experimental`, `stable`, `deprecated`. | Deprecation requires `replaced_by`. |
| `replaced_by` | CURIE of successor entity. | Mandatory when `status=deprecated`. |
| `definition` | Textual definition. | Annotation property `IAO:0000115`. |
| `comment` | Free-form notes. | Optional. |
| `example` | Usage illustration. | Optional. |
| `source` | URI or citation for provenance. | Optional. |
| `subclass_of` | Comma-separated parent IRIs/curies. | Classes only. |
| `equivalent_to` | Manchester or OWL expression. | Classes only; export via ROBOT. |
| `disjoint_with` | Comma-separated IRIs/curies. | Classes only. |
| `on_property` | Property IRI for restrictions. | Paired with restriction columns below. |
| `restriction_type` | `some`, `only`, `min`, `max`, `exact`. | Classes only; one restriction per row; use multiple rows per class for multiple restrictions. |
| `restriction_filler` | Filler class/datatype IRI. | Required when `restriction_type` is set. |
| `cardinality_value` | Integer for `min`/`max`/`exact`. | Optional otherwise. |
| `property_domain` | Domain class IRI. | Properties only. |
| `property_range` | Range class/datatype IRI. | Properties only. |
| `property_characteristic` | `functional`, `inverseFunctional`, `symmetric`, `asymmetric`, `reflexive`, `irreflexive`, `transitive`. | Object/data properties only; multiple values separated by `|`. |
| `inverse_of` | Inverse property IRI. | Object properties only. |
| `annotation_predicate` | For supplemental annotations. | Optional; use additional rows per predicate. |
| `annotation_value` | Literal/IRI for the annotation. | Pair with `annotation_predicate`. |

> Why row-per-entity? This format stays compatible with ROBOT templates (`--template`) while keeping the sheet human-auditable. Multiple logical axioms for a class/property are handled by adding extra rows with the same `id` and filling only the relevant axiom columns.

## Minimal required columns per entity type
- **Classes:** `id`, `label`, `entity_type`, `dccx_alignment`, `subclass_of` (or `equivalent_to`), and any restrictions.
- **Object/Data properties:** `id`, `label`, `entity_type`, `dccx_alignment`, `property_domain`, `property_range`; add `property_characteristic`/`inverse_of` as needed.
- **Individuals:** `id`, `label`, `entity_type`, `type` (via `subclass_of` or `equivalent_to`), plus annotations.

## Validation rules
- `id` must be unique and use approved prefixes; `label` unique within its language.
- `dccx_alignment` mandatory for classes and properties; must resolve to an existing DCC schema identifier or `dccx:None` if intentionally new.
- Only annotation columns may carry literals; all structural columns must be IRIs/curies.
- Restriction columns (`on_property`, `restriction_type`, `restriction_filler`) must be filled together; `cardinality_value` required for `min`/`max`/`exact`.
- `property_domain` and `property_range` are required unless explicitly marked `open`.
- Deprecated rows require `replaced_by` and should not carry new logical axioms.

## Example rows (CSV excerpt)
```
id,label,entity_type,dccx_alignment,status,subclass_of,on_property,restriction_type,restriction_filler,cardinality_value,property_domain,property_range,property_characteristic
"dcc:Sensor","Sensor",Class,"dccx:Sensor","stable","sosa:Sensor","dcc:observes","some","dcc:ObservedProperty",,,,
"dcc:observes","observes",ObjectProperty,"dccx:observes","stable",,,,,"dcc:Sensor","dcc:Observation","functional"
"dcc:Observation","Observation",Class,"dccx:Observation","stable","sosa:Observation","dcc:hasResult","some","xsd:anyURI",,,,
```

These rows can be exported with ROBOT’s template command (e.g., `robot template --template dcc_template.csv --prefix "dcc: <http://example.org/dcc#>" --output dcc.owl`) to produce the OWL axioms.

## Should classes and properties be split into separate sheets?

The template works as a single sheet, but splitting improves governance when the ontology grows:

- **Class sheet:** keep conceptual hierarchy, restrictions, disjointness, and annotations together. Multiple rows per class capture each restriction, disjointness, or extra annotation.
- **Property sheet:** focus on domains/ranges, characteristics, inverses, and DCCX alignment. This avoids wide sparsity from class-only columns and makes ROBOT validation rules (`--validate`) simpler per sheet.

Both sheets can share the same column headers; ROBOT will merge them during export. Use a third, optional **annotation sheet** if curators want to bulk-add comments/definitions without touching logical axioms.

## Can the expanded DCC ontology be transformed into this template?

Yes. The expanded TTL already carries the information needed for each column:

- **Identifiers, labels, and definitions** are present for classes and properties (e.g., `dcc:hasAdministrativeData` with domain/range, labels, and definition).【F:Resources/dcc/dcc_ontology_expanded.ttl†L100-L116】
- **Alignment to DCC schema** exists via `skos:exactMatch dccx:*`, which populates `dccx_alignment` (e.g., `dcc:DigitalCalibrationCertificate` aligns to `dccx:digitalCalibrationCertificate`).【F:Resources/dcc/dcc_ontology_expanded.ttl†L1403-L1435】
- **Domains, ranges, and property characteristics** (e.g., `owl:FunctionalProperty`) map directly to the property columns.【F:Resources/dcc/dcc_ontology_expanded.ttl†L100-L116】
- **Cardinality restrictions** on classes can be represented with repeated rows filling `on_property`, `restriction_type`, `restriction_filler`, and `cardinality_value`. The `DigitalCalibrationCertificate` class includes qualified cardinalities on component containers and data properties that map cleanly to these columns.【F:Resources/dcc/dcc_ontology_expanded.ttl†L1404-L1428】

Automated extraction is feasible with ROBOT (`robot query` or `robot convert` + SPARQL) or the existing ontology generation script: parse entities, emit one row per logical axiom/annotation, and preserve `skos:exactMatch` for DCCX alignment.

## Automating export/import and round-trip checks

Use `dcc_tabular_transform.py` to extract the expanded TTL into the CSV column set above, regenerate TTL from the sheet, and report coverage:

```bash
# Export TTL → CSV
python "Resources/ontology generation/dcc_tabular_transform.py" \
  --mode export \
  --input-ttl Resources/dcc/dcc_ontology_expanded.ttl \
  --output-csv /tmp/dcc_tabular.csv

# Import CSV → TTL
python "Resources/ontology generation/dcc_tabular_transform.py" \
  --mode import \
  --input-csv /tmp/dcc_tabular.csv \
  --output-ttl /tmp/dcc_from_table.ttl

# Round-trip comparison (TTL → CSV → TTL) with triple counts
python "Resources/ontology generation/dcc_tabular_transform.py" \
  --mode roundtrip \
  --input-ttl Resources/dcc/dcc_ontology_expanded.ttl \
  --output-csv /tmp/dcc_tabular.csv \
  --roundtrip-ttl /tmp/dcc_roundtrip.ttl
```

The round-trip report surfaces how many triples were captured, which is useful for validating that the tabular format preserves the intended axioms before publishing updates.

Add `--schema-xsd Resources/dcc/dcc.xsd` in any mode to validate that each `dccx_alignment` (SKOS `exactMatch`) points to a term declared in the official DCC XML schema namespace; the CLI prints how many alignments were resolved vs. still missing.
