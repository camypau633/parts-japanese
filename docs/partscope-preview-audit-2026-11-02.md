# PartScope CatCar preview audit — 2026-11-02

## Scope

Audited the preview export published to `camypau633/partscope` at:

`public/data-preview/catcar/`

This is a fixture-based preview only. It is not a production catalog and the PartScope search loader currently reads `public/data/`, not this preview directory.

## Result

- Export report: 77 unique SKU records across 7 shards.
- Brand distribution observed in the published shards: Nissan 75 records, Toyota 2 records.
- The Nissan records belong to the Pixo (UA0) engine-mechanical catalog context.
- The Toyota records are two oil-filter OEM numbers for a Camry / 2AZFE context.
- JSON is keyed by cleaned SKU and the keys match each record's `sku`.
- The record fields are compatible with `normalizeRemote()` in PartScope `src/lib/parts.ts`:
  - `part_id`, `sku`, `name`, `brand`
  - `factory_parts` including `position`, `quantity`, `production_period`, `applicability`, `source_name`, `source_url`
  - `compatibility`
  - `diagram.diagramUrl` and `diagram.hotspots`
  - `analogs`, `specifications`, `technical_drawings`, `source`
- The exporter keeps OEM factory catalog rows separate from analogues.
- No fabricated analogues, dimensions, or hotspot coordinates were found in the export.

## Quality gaps before production use

1. Coverage is extremely small and uneven: 75 Nissan records versus 2 Toyota records. This is not representative coverage of either make.
2. Nissan compatibility currently contains make/model only; `engine` and `years` are empty in the exported records. Do not display these as known values.
3. The report confirms zero analogues, zero physical dimensions, and zero diagram hotspots. Those features must remain empty/unsupported for these records.
4. Diagram URLs are present, but this audit did not verify that every remote image URL responds successfully or that its image content is suitable.
5. The preview directory is intentionally not read by the app. No production data path or search behavior was changed.

## Decision

**Schema compatibility: pass. Production readiness: fail / not yet approved.**

Next work should improve source extraction and normalization for representative vehicle/catalog coverage, especially Nissan engine/year context, then add automated validation for every exported record and diagram URL. Only after that should a separate, explicitly reviewed change connect an approved dataset to the production `public/data/` path.


## Follow-up: Nissan vehicle period extraction fix

Commit `3642efc` updates the real-artifact validator to decode CatCar's existing `l=` filter in the captured Nissan URL. The filter explicitly contains:

- vehicle/catalog period: `2009-03-01` to `2013-08-01`;
- selected group period: `2012-01-01` to `2013-08-01`;
- catalog ID: `43`.

The normalized Nissan context now preserves both periods. The PartScope exporter maps the vehicle/catalog period to `compatibility[].years`; it does not replace the individual part-row production periods.

The captured filter does **not** expose an engine code. The validator deliberately leaves `engine_code` absent rather than deriving it from the model label. The validation report now also records whether engine and vehicle production-period metadata were present.

A unit test covers extraction of both date ranges and confirms that an absent engine code stays absent. The real-artifact and adapter-test workflows are triggered by these commits; their successful completion must be checked before replacing the existing preview artifact.
