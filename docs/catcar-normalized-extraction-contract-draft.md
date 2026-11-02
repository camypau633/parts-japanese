# CatCar normalized extraction contract (draft)

Status: research draft, based on bounded Toyota, Nissan, Ford, and Volkswagen probes. This is not a production importer specification and does not authorize bulk collection.

## Design rule

Keep source-specific parsing in adapters, but emit a shared record model. Never discard the raw source values. A normalized field may be null when the source does not provide it; do not infer OEM equivalence or supersession.

## 1. Catalog context

Each extracted page belongs to a catalog context:

- `brand`
- `catalog_id` and source modification/model identifiers, when present
- `model_name`
- `modification_name`
- `engine_code`, when present
- `region` and steering configuration, when present
- `production_period_raw`
- optional normalized `production_start` / `production_end`

Retain original date strings. Normalize dates only when the source format is unambiguous. An open-ended period remains open-ended, not an invented end date.

## 2. Group tree

Represent catalog navigation as parent-child nodes:

- `source_group_id`
- `parent_group_id`
- `group_code`
- `label_raw`
- `label_normalized` (optional)
- `source_url`
- `sort_order` (only when explicitly observable)

This supports Ford's multi-level navigation without assuming that Toyota/Nissan/VAG have the same hierarchy.

## 3. Part row

A part row is the source's displayed position in a catalog diagram/table:

- `source_row_id`
- `diagram_position_code` — e.g. Ford's `Code`, Nissan's position identifier, or VAG's position column
- `part_number_raw`
- `description_raw`
- `production_period_raw`
- `quantity_raw`
- `row_kind`: `positioned`, `continuation`, `group_header`, or `unknown` when the source structure supports this distinction\n- `parent_position_code` (nullable; populate only when source markup or behavior confirms the continuation relationship)\n- `source_row_order`\n- `additional_source_fields`
- `source_status`: `available`, `no_applicable_data`, or `unresolved`

Do not assume `part_number_raw` is a confirmed OEM number in every adapter. Keep a separate OEM record collection only when the source explicitly exposes OEM values.

## 4. OEM / variation records

One source part row may resolve to multiple OEM records, and one OEM record may have its own period and applicability.

Each OEM record should retain:

- `oem_number_raw`
- `production_period_raw`
- `applicability_raw`
- `source_record_id`, if present
- `source_row_id`

Do not collapse multiple OEM records into one. Do not create replacement/supersession links from overlapping or adjacent dates alone. Any future inferred relationship must be stored separately with evidence and an explicit unverified status.

## 5. Diagram asset and hotspots

Diagram asset:

- `diagram_id`
- `source_image_url`
- `source_image_path` (only after a successful fetch)
- `source_format` / `content_type` (when verified)
- `source_group_id`

Hotspot:

- `hotspot_id`
- `diagram_id`
- `source_position_code`
- `source_row_id` (nullable; set only when one source row is uniquely identified)\n- `source_row_ids` (array; preserves one-to-many mappings when a single diagram position represents multiple part rows)
- `top_raw`, `left_raw`, `width_raw`, `height_raw`
- `coordinate_system` and image dimensions, when verified
- `resolution_status`: `matched`, `unmatched`, or `ambiguous`

Keep original coordinate values. Do not scale or rewrite coordinates until the original image dimensions and CatCar's coordinate behavior are verified. Multiple hotspots may refer to one part row. A single hotspot/position may also correspond to multiple source rows (for example, a Nissan position with separate part numbers across production periods); preserve all linked row IDs rather than selecting one arbitrarily.

## 6. Adapter behavior established so far

| Adapter | Table delivery | Diagram relationship |
|---|---|---|
| Toyota | AJAX row reveal using row token; OEM variation records returned separately | HTML hotspot coordinates; match by source row identifier |
| Nissan | Static HTML table | `srcNum` matches table part-row identifiers on tested page |
| Ford | Hierarchical group navigation; static leaf table | hotspot `name` matches table `Code` on tested page |\n| Volkswagen / VAG | Combined Audi/VW/Skoda/Seat catalog; static table with blank-position continuation rows | hotspot `name` matches table position column on tested page; one table marker `(40)` had no hotspot |

For VAG continuation rows, preserve raw row order and blank position cells. Do not inherit the preceding position code until the source markup or browser behavior proves that relationship. Treat the unmatched `(40)` marker as unresolved.\n\nThese are tested page patterns, not universal brand-wide guarantees.

## 7. Required quality checks per page

Before accepting an extracted page:

1. Record the requested URL, final URL, HTTP status, and fetch timestamp.
2. Save the raw HTML response for reproducibility.
3. Identify table headers before mapping columns.
4. Preserve every source row, including rows with no applicable data.
5. Count table rows and unique source position identifiers.
6. Count hotspots and compare their identifiers with table position identifiers.
7. Report matched, unmatched, and ambiguous hotspots separately.
8. Fetch at least one diagram asset and verify HTTP status and non-zero bytes.
9. Keep source-specific raw values beside normalized fields.
10. Fail validation on silent row loss, guessed OEM mappings, or unexplained identifier mismatches.

## 8. Not yet proven

- Coverage of every model, year, region, and page layout for any brand.
- Whether all CatCar makes share the same scripts or coordinate conventions.
- Complete applicability/vehicle-fitment extraction across brands.
- Universal OEM replacement relationships.
- Legal permission for automated or bulk collection.

Bulk collection remains disabled until the terms of use are reviewed and a representative set of page layouts has passed these checks.
