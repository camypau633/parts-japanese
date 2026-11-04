# CatCar extraction adapters — POC

This package contains shared parsers, brand/layout adapters, draft JSON normalization, a PartScope exporter, and a bounded/resumable crawler for all eight Japanese CatCar catalog roots. It is an early importer implementation, not yet a complete production importer for all ten marques.

## Current project scope

The active project is limited to Japanese vehicle makes, but includes all regional versions available in CatCar: Japan/JDM, Asia, Europe, USA, Canada, Russia, the Middle East, Latin America, and other export markets. Vehicle manufacturer origin and catalog market are separate fields. The bounded/resumable crawler can select all eight CatCar catalog roots (Toyota/Lexus, Nissan/Infiniti, Honda, Suzuki, Mazda, Mitsubishi, Isuzu, Subaru) and uses a minimum 10-second delay. It discovers HTML links, normalizes recognized detail pages through the selected adapter, checkpoints its queue, and records unrecognized pages for review. It preserves an explicit market label when CatCar exposes a recognized market code (for example, `euro` in a diagram path or Suzuki's verified numeric `marketId` values); unknown raw codes are retained and missing market information is not guessed. Suzuki's `marketId` mapping is documented in `docs/catcar-japanese-catalog-structure-survey-2026-11-05.md`; the Asia region is never relabeled as Japan. Detail adapters currently exist for Honda, Nissan, Toyota, Suzuki, and Subaru. Suzuki's first header-driven adapter targets the inspected parts table (code, part number, name, additional information, quantity); its synthetic regression fixture is based on the live Asia/APV/GC415T table, but it still needs retained raw HTML and validation across other Suzuki models and markets. Subaru's first header-driven adapter targets the inspected parts-list columns (position, part number, options, applicable models, production date, note/destination code, comment); it has a synthetic regression fixture based on the inspected CatCar table, but still needs a retained raw HTML fixture and validation across other Subaru groups and markets. Mazda, Mitsubishi, and Isuzu remain in discovery-only mode: pages and navigation are retained for layout research, but no part records are fabricated. Toyota and Nissan catalog roots each represent two marques; until an explicit source field distinguishes them, the normalized `brand` is null and `brand_candidates` retains both possibilities. This is not yet a complete catalog crawl. Toyota rows requiring a `getArticles` lookup remain marked `requires_ajax`; the crawler does not yet fetch those OEM responses.

Ford and VAG adapters remain legacy experimental code from earlier probes. They are excluded from the current Japanese-only regression, importer, and preview publication. Do not run or extend them in this repository; other vehicle markets belong in separate repositories.

## Runtime

- Executed in GitHub Actions on Python 3.12.
- Parser and adapters use the Python standard library.
- Development tests use `jsonschema` to validate normalized output.
- No local Windows/Python setup is required.

## Japanese adapters

- `ToyotaAdapter`: extracts Toyota source-row identifiers and `getArticles` AJAX tokens; parses OEM, production-period, and applicability cells from an AJAX response. Blank AJAX cells remain blank and do not shift adjacent values.
- `NissanAdapter`: reads the tested static table column order and matches `srcNum` hotspots to the first table column.
- `SuzukiAdapter`: parses the inspected Asia/APV/GC415T parts-table header and preserves part name, additional information and quantity. Current regression coverage is a synthetic fixture; a real raw HTML capture and broader model/market checks are still required.
- `SubaruAdapter`: parses the inspected Subaru parts-list header and preserves applicable-model, production-date, destination-code and comment columns. Current regression coverage is a synthetic fixture; a real raw HTML capture and broader market/group checks are still required.
- HondaAdapter is now implemented for the observed Honda code/part-number/description table. It starts parsing after the explicit header row, preserves duplicate position rows, and retains the additional-information and option-code columns. The 2011 Accord E-1 sample validates six part rows and nine coordinate regions. Honda preview conversion is enabled for the validated Accord E-1 sample after its 1920×959 image and all nine hotspot bounds were checked. This is one model/configuration/group only; it is not yet broad Honda coverage and has not been published into the PartScope preview dataset.

## Output behavior

`normalize_page()` converts adapter results into the draft shared JSON structure defined by `schemas/catcar-extraction-v0.1.schema.json`. It preserves one-to-many hotspot-to-row mappings and accepts Toyota OEM variation records linked to their source row.

Raw strings, all original static-table cells, table order, and original hotspot geometry are retained. The normalized catalog context records the Japanese manufacturer country separately from `market_region` and `market_code_raw`. The crawler also records market metadata on navigation and discovery-only pages, and `crawl-report.json` includes `market_coverage_pages` so regional discovery can be audited before a detail adapter exists. These are page counts, not a claim of complete model coverage. Image parsing distinguishes confirmed diagram images (`img.resize`) from logos, loaders, and other images; only confirmed diagram images enter the normalized `diagrams` collection.

The current importer does not yet:
- complete a full mass crawl or download the complete catalogs;
- fetch Toyota `getArticles` AJAX responses during crawling;
- infer OEM replacement/supersession;
- normalize ambiguous date formats;
- write to the production PartScope database.

## Offline extraction command

The CLI converts one previously saved HTML page into normalized JSON and performs no network access:

```bash
python -m tools.catcar_poc.cli --adapter toyota --input page.html --output catalog.json --source-url "https://www.catcar.info/example/page" --context context.json
```

For the current Japanese project, the crawler accepts all eight catalog roots: `toyota`, `nissan`, `honda`, `suzuki`, `mazda`, `mitsubishi`, `isuzu`, and `subaru`. The last five currently collect review artifacts only. Legacy `ford` and `vag` CLI choices remain only for historical fixture reproduction and are not part of the active project scope. For Toyota, already extracted AJAX records can be supplied with `--oem-records`.

## Tests and real fixtures

GitHub Actions runs parser, adapter, regression, crawler unit, and JSON Schema tests on Python 3.12. Crawler tests mock network access and cover normalization, market metadata, and checkpoint resume. Synthetic tests cover parser edge cases. The active real-artifact regression replays the captured Toyota and Nissan fixtures only. Honda's first captured detail-group fixture is now covered by the offline adapter unit test. The real-artifact exporter regression still replays Toyota and Nissan fixtures. Honda is covered by a captured-layout parser test and a dedicated exporter test using the measured Accord E-1 diagram geometry.

Toyota AJAX responses with the source message `No applicable data!` are retained as OEM records with `source_status: no_applicable_data`, rather than silently disappearing. Blank OEM period/applicability cells remain null.

Before production use, the crawler must be exercised over all eight Japanese catalog roots; detail adapters must be implemented for Mazda, Mitsubishi, and Isuzu; Suzuki and Subaru's first adapters must be validated against retained real HTML from multiple groups and markets; Toyota `getArticles` AJAX collection must be implemented; market labels must be checked against real CatCar regional catalog paths; incomplete-page handling and resume behavior must be verified on real runs; and source permissions/terms must be reviewed.

## Bounded Toyota Camry group/AJAX sample

The `normalize_toyota_oem_sample.py` command consumes a saved bounded probe artifact. The artifact must contain the JSON summary, each raw group HTML page, and each sampled AJAX HTML response:

```bash
python -m tools.catcar_poc.normalize_toyota_oem_sample --sample out/oem_variation_sample.json --schema schemas/catcar-extraction-v0.1.schema.json --output out/normalized
```

It performs no network requests. It verifies that every sampled part row exists in the saved group HTML, checks that parsed OEM rows exactly match the saved AJAX HTML, and validates each group document against the shared schema. It retains all part rows from each group, including rows whose AJAX response was not sampled; those rows remain marked `requires_ajax` and are not exported as OEM numbers.

Each OEM record retains its source row, group ID, AJAX URL, and record order. Empty responses are accepted only when the saved AJAX HTML explicitly contains CatCar's `No applicable data!` message. The source record ID remains null when CatCar does not provide one; a local row order is not misrepresented as a CatCar ID.

The normalizer is intentionally limited to the groups and AJAX responses present in the artifact. It does not claim complete catalog coverage and does not infer OEM replacements or analogues.
