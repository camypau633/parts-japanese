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
- `VagAdapter`: reads the combined VAG table, preserves blank-position continuation rows, and matches hotspot `name` values to the first position column. The `ST`, remark, and model-data columns remain separate raw fields; `ST` is not treated as quantity.

## Output behavior

`normalize_page()` converts adapter results into the draft shared JSON structure defined by `schemas/catcar-extraction-v0.1.schema.json`. It preserves one-to-many hotspot-to-row mappings and accepts Toyota OEM variation records linked to their source row.

Raw strings, all original static-table cells, table order, and original hotspot geometry are retained. Image parsing distinguishes confirmed diagram images (`img.resize`) from logos, loaders, and other images; only confirmed diagram images enter the normalized `diagrams` collection. The code does not:

- fetch pages or images;
- traverse vehicle/group navigation;
- inherit a VAG continuation row's position;
- infer OEM replacement/supersession;
- normalize ambiguous date formats;
- write a production database or PartScope files.

## Offline extraction command

The CLI converts one previously saved HTML page into normalized JSON and performs no network access:

```bash
python -m tools.catcar_poc.cli --adapter ford --input page.html --output catalog.json --source-url "https://www.catcar.info/example/page" --context context.json
```

`--adapter` accepts `toyota`, `nissan`, `ford`, or `vag`. `--context` is optional explicit catalog metadata. For Toyota, already extracted AJAX records can be supplied with `--oem-records`. The command does not download pages, follow navigation, or fetch Toyota AJAX tokens itself.

## Tests

GitHub Actions runs parser, adapter, regression, and JSON Schema tests on Python 3.12. Synthetic tests cover edge cases. A separate offline real-artifact regression replays the previously captured Toyota, Nissan, Ford, and VAG HTML pages without contacting CatCar, validates each normalized document against the shared schema, and uploads the JSON report as a short-lived workflow artifact. This confirms the tested layouts only; it is not proof of full brand coverage.

Toyota AJAX responses with the source message `No applicable data!` are retained as OEM records with `source_status: no_applicable_data`, rather than silently disappearing. Blank OEM period/applicability cells remain null.

Before a production importer is considered, the adapters still need fixture-based validation against additional real page variants and an explicit permission review.
