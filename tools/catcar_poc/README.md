# CatCar extraction adapters — POC

This package is the first implementation of the shared parser, brand/layout adapters, and draft JSON normalization layer. It is intentionally **not** a crawler, downloader, or production importer.

## Runtime

- Executed in GitHub Actions on Python 3.12.
- Parser and adapters use the Python standard library.
- Development tests use `jsonschema` to validate normalized output.
- No local Windows/Python setup is required.

## Current adapters

- `ToyotaAdapter`: extracts Toyota source-row identifiers and `getArticles` AJAX tokens; parses OEM, production-period, and applicability cells from an AJAX response. Blank AJAX cells remain blank and do not shift adjacent values.
- `NissanAdapter`: reads the tested static table column order and matches `srcNum` hotspots to the first table column.
- `FordAdapter`: reads the Ford leaf table and matches hotspot `name` values to the `Code` column.
- `VagAdapter`: reads the combined VAG table, preserves blank-position continuation rows, and matches hotspot `name` values to the first position column.

## Output behavior

`normalize_page()` converts adapter results into the draft shared JSON structure defined by `schemas/catcar-extraction-v0.1.schema.json`. It preserves one-to-many hotspot-to-row mappings and accepts Toyota OEM variation records linked to their source row.

Raw strings, table order, and original hotspot geometry are retained. The code does not:

- fetch pages or images;
- traverse vehicle/group navigation;
- inherit a VAG continuation row's position;
- infer OEM replacement/supersession;
- normalize ambiguous date formats;
- write a production database or PartScope files.

## Tests

GitHub Actions runs parser, adapter, regression, and JSON Schema tests on Python 3.12. Tests use synthetic HTML fragments based on the verified page structures. They are regression tests, not proof of full brand coverage.

Before a production importer is considered, the adapters still need fixture-based validation against additional real page variants and an explicit permission review.
