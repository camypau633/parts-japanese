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

## Bounded Toyota Camry group/AJAX sample

The `normalize_toyota_oem_sample.py` command consumes a saved bounded probe artifact. The artifact must contain the JSON summary, each raw group HTML page, and each sampled AJAX HTML response:

```bash
python -m tools.catcar_poc.normalize_toyota_oem_sample --sample out/oem_variation_sample.json --schema schemas/catcar-extraction-v0.1.schema.json --output out/normalized
```

It performs no network requests. It verifies that every sampled part row exists in the saved group HTML, checks that parsed OEM rows exactly match the saved AJAX HTML, and validates each group document against the shared schema. It retains all part rows from each saved group, including rows whose AJAX response was not sampled; those rows remain marked `requires_ajax` and are not exported as OEM numbers.

Each OEM record retains its source row, group ID, AJAX URL, and record order. Empty responses are accepted only when the saved AJAX HTML explicitly contains CatCar's `No applicable data!` message. The source record ID remains null when CatCar does not provide one; a local row order is not misrepresented as a CatCar ID.

The normalizer is intentionally limited to the groups and AJAX responses present in the artifact. It does not claim complete Camry catalog coverage, and it does not infer OEM replacements or analogues.
