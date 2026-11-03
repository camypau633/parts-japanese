# CatCar extraction adapters — POC

This package contains the shared parser, brand/layout adapters, and draft JSON normalization layer. It is not a crawler, downloader, or production importer.

## Current project scope

The active project is limited to Japanese vehicle makes only. Toyota and Nissan have bounded real-page fixtures. Honda is currently in catalog-layout discovery; no Honda adapter is enabled until a real detail-group page is captured and validated.

Ford and VAG adapters remain legacy experimental code from earlier probes. They are excluded from the current Japanese-only regression, importer, and preview publication. Do not run or extend them in this repository; other vehicle markets belong in separate repositories.

## Runtime

- Executed in GitHub Actions on Python 3.12.
- Parser and adapters use the Python standard library.
- Development tests use `jsonschema` to validate normalized output.
- No local Windows/Python setup is required.

## Japanese adapters

- `ToyotaAdapter`: extracts Toyota source-row identifiers and `getArticles` AJAX tokens; parses OEM, production-period, and applicability cells from an AJAX response. Blank AJAX cells remain blank and do not shift adjacent values.
- `NissanAdapter`: reads the tested static table column order and matches `srcNum` hotspots to the first table column.
- HondaAdapter is now implemented for the observed Honda code/part-number/description table. It starts parsing after the explicit header row, preserves duplicate position rows, and retains the additional-information and option-code columns. The 2011 Accord E-1 sample validates six part rows and nine coordinate regions. Honda export remains disabled until the diagram's dimensions and hotspot bounds are independently verified.

## Output behavior

`normalize_page()` converts adapter results into the draft shared JSON structure defined by `schemas/catcar-extraction-v0.1.schema.json`. It preserves one-to-many hotspot-to-row mappings and accepts Toyota OEM variation records linked to their source row.

Raw strings, all original static-table cells, table order, and original hotspot geometry are retained. Image parsing distinguishes confirmed diagram images (`img.resize`) from logos, loaders, and other images; only confirmed diagram images enter the normalized `diagrams` collection.

The current Japanese workflows do not:
- perform mass crawling or download complete catalogs;
- infer OEM replacement/supersession;
- normalize ambiguous date formats;
- write to the production PartScope database.

## Offline extraction command

The CLI converts one previously saved HTML page into normalized JSON and performs no network access:

```bash
python -m tools.catcar_poc.cli --adapter toyota --input page.html --output catalog.json --source-url "https://www.catcar.info/example/page" --context context.json
```

For the current Japanese project, use `toyota`, `nissan`, or `honda`. Legacy `ford` and `vag` CLI choices remain only for historical fixture reproduction and are not part of the active project scope. For Toyota, already extracted AJAX records can be supplied with `--oem-records`.

## Tests and real fixtures

GitHub Actions runs parser, adapter, regression, and JSON Schema tests on Python 3.12. Synthetic tests cover edge cases. The active real-artifact regression replays the captured Toyota and Nissan fixtures only. Honda's first captured detail-group fixture is now covered by the offline adapter unit test. The real-artifact exporter regression still covers Toyota and Nissan only; Honda must pass image geometry and export validation before being enabled for preview publication.

Toyota AJAX responses with the source message `No applicable data!` are retained as OEM records with `source_status: no_applicable_data`, rather than silently disappearing. Blank OEM period/applicability cells remain null.

Before a production importer is considered, adapters still need fixture-based validation against additional Japanese page variants and an explicit permission review.

## Bounded Toyota Camry group/AJAX sample

The `normalize_toyota_oem_sample.py` command consumes a saved bounded probe artifact. The artifact must contain the JSON summary, each raw group HTML page, and each sampled AJAX HTML response:

```bash
python -m tools.catcar_poc.normalize_toyota_oem_sample --sample out/oem_variation_sample.json --schema schemas/catcar-extraction-v0.1.schema.json --output out/normalized
```

It performs no network requests. It verifies that every sampled part row exists in the saved group HTML, checks that parsed OEM rows exactly match the saved AJAX HTML, and validates each group document against the shared schema. It retains all part rows from each group, including rows whose AJAX response was not sampled; those rows remain marked `requires_ajax` and are not exported as OEM numbers.

Each OEM record retains its source row, group ID, AJAX URL, and record order. Empty responses are accepted only when the saved AJAX HTML explicitly contains CatCar's `No applicable data!` message. The source record ID remains null when CatCar does not provide one; a local row order is not misrepresented as a CatCar ID.

The normalizer is intentionally limited to the groups and AJAX responses present in the artifact. It does not claim complete catalog coverage and does not infer OEM replacements or analogues.
