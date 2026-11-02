# Japanese catalogue export contract

Status: implementation contract draft for the Japanese-only data repository. It defines the boundary between factory catalogue records and data supplied by future analogue/dimension sources. It does not authorize bulk collection from any website.

## 1. Repository scope

This repository contains Japanese vehicle makes, models, factory part numbers, factory catalogue relationships, and factory diagrams only.

Toyota and Nissan are already represented in the bounded CatCar research samples. Other Japanese makes may be added only after their source layouts are separately validated. Do not include Ford, Volkswagen, or other non-Japanese makes in this repository's production export.

The adapter framework may remain reusable, but production selection must be explicitly allow-listed for Japanese makes. Research-only foreign fixtures must never enter the Japanese export.

## 2. Data domains must remain separate

The application must not treat every number found in a factory catalogue as an analogue.

### Factory catalogue data

CatCar is currently used for:
- vehicle make/model/modification/engine context;
- factory part rows and original OEM numbers;
- part descriptions and quantities when supplied;
- production periods and applicability records when supplied;
- factory diagram images and diagram-position/hotspot relationships.

CatCar hotspot coordinates identify a location on an illustration. They are not physical dimensions of the part.

CatCar samples examined so far do not establish a reliable source of physical measurements such as diameter, length, height, thread, pitch, or mounting dimensions. If a source page explicitly provides a physical measurement in the future, preserve it with its exact source evidence; otherwise leave the dimension dataset empty.

### Analogue data

Analogue/cross-reference records must come from a separate source adapter. A record must identify:
- the searched/source part number and brand;
- the proposed analogue part number and brand;
- the relationship type as supplied by the source (cross-reference, equivalent, replacement, supersession, etc.);
- source name and source URL or record identifier;
- verification status.

Do not infer equivalence from matching descriptions, shared diagram positions, adjacent production periods, or similar-looking numbers. Do not convert a factory OEM row into an analogue merely because it is another OEM number.

### Physical dimensions

Physical dimensions must come from a separate dimensions source adapter. Store each measurement as a structured value:
- stable key (for example, outer_diameter, inner_diameter, length, height, thread, pitch);
- display label;
- numeric or source-text value;
- unit;
- source name and source URL/record identifier;
- verification status.

Do not infer units or convert ambiguous source text. Preserve the original value and unit. A missing measurement is unknown, not zero.

### Drawings and factory diagrams

Keep drawing assets separate from physical measurements. A diagram or hotspot coordinate is not a dimension. Technical drawings may be supplied by a future source and linked to a part, but must retain their own provenance.

## 3. Application-facing record

The current PartScope loader reads compact JSON shards from `data/{first2}.json`, where `first2` is the first two characters of the cleaned SKU. Each shard is an object keyed by the full cleaned SKU.

The application currently recognizes these fields (exact property names are kept for compatibility):
- `part_id`, `sku`, `name`, `brand`;
- `factory_parts` — factory OEM rows with `sku`, `name`, optional `position`, `quantity`, `production_period`, `applicability`, and source provenance;
- `analogs` / `analogues`;
- `compatibility` / `applicability`;
- `specifications` / `specs`;
- `diagram` with image URL, dimensions and hotspots;
- `technical_drawings` / `technicalDrawings`.

The current UI has separate **Factory parts**, **Analogues**, **Applicability**, and **Drawings and dimensions** tabs. The `factory_parts` array contains factory catalogue rows only; never place these rows in `analogs` / `analogues`. Physical dimensions should be independently sourced and independently displayable from drawing files.

A later application change should expose separate views for:
1. Factory parts (`factory_parts`: OEM catalogue rows and their vehicle/period context);
2. Analogues (only confirmed source cross-references);
3. Applicability;
4. Dimensions (structured physical measurements);
5. Drawings/diagrams (illustrations and hotspot relationships).

Do not silently change the current shard path or JSON keying while implementing these views.

## 4. Provenance and confidence

Every imported record in each data domain must retain source provenance. At minimum:
- `source_name`;
- `source_url` or stable source record identifier;
- `retrieved_at` when known;
- `verification_status`.

Use explicit statuses such as `verified`, `source_reported`, `unverified`, and `not_found` where applicable. Do not display unverified inferred relationships as confirmed data.

Preserve all OEM rows, including multiple numbers for the same catalogue position and different production periods/applicability. Do not infer replacement chains from overlapping or adjacent periods alone.

## 5. Japanese-only export validation

Before a record enters the production export:
1. Confirm its make belongs to the Japanese-only scope.
2. Confirm the source adapter and source record.
3. Preserve original source values and row ordering where relevant.
4. Keep OEM, analogue, dimension, and drawing domains separate.
5. Validate every referenced diagram and hotspot relationship.
6. Reject fabricated analogue or dimension values.
7. Validate the final shard against the application contract.

The export must not include research fixtures for Ford, Volkswagen, or other non-Japanese makes.

## 6. Storage budgets

These are project guardrails, not GitHub platform limits:
- target total repository size: at most 500 MB;
- target maximum compact JSON shard: 2 MB;
- deduplicate repeated diagram assets and reference them by stable path/ID;
- optimize diagram images before publishing, without degrading readable labels/hotspots;
- do not commit raw HTML, screenshots, temporary downloads, logs, or intermediate extraction files to the production data directory;
- use compact JSON for published shards.

If a shard exceeds 2 MB, split or normalize the data before publishing; do not simply raise the limit.

## 7. Collection policy

The CatCar access-policy probe found a `Crawl-delay: 10` directive but did not establish a licence or permission to bulk extract and redistribute data. Do not start a mass crawl or public redistribution until the applicable terms/permission are established. Bounded research artifacts already captured may continue to be used for offline parser regression tests.
