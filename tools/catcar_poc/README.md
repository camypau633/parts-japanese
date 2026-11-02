# CatCar extraction adapters — POC

The package in this folder is a first implementation of the shared parsing and draft normalization layer. It is intentionally **not** a crawler, downloader, or production importer.

## Runtime

- Python 3.8+
- Standard library only
- No browser automation or external dependencies

## Current adapters

- `ToyotaAdapter`: extracts CatCar Toyota part-row names and `getArticles` AJAX tokens; parses OEM, production-period, and applicability cells from an AJAX response.
- `NissanAdapter`: reads a static table using the tested Nissan column order and matches `srcNum` hotspots to the first table column.
- `FordAdapter`: reads the Ford leaf table and matches hotspot `name` values to the `Code` column.
- `VagAdapter`: reads the combined VAG table, preserves blank-position continuation rows, and matches hotspot `name` values to the first position column.

## Output behavior

Each adapter returns raw parsed rows, image references, hotspot records, part-row records, and a hotspot reconciliation summary. `normalize_page()` converts this result into the draft shared JSON shape. It preserves one-to-many mappings when one diagram position identifies multiple source part rows.

The parser preserves raw strings and original row order. It does not:

- fetch pages or images;
- traverse vehicle/group navigation;
- inherit a VAG continuation row's position;
- infer OEM replacement/supersession;
- normalize ambiguous date formats;
- write a production database or PartScope files.

## Tests

Run locally:

```bash
python -m unittest discover -s tools/catcar_poc/tests -v
```

GitHub Actions runs the same tests on Python 3.8.

Tests use small synthetic HTML fragments that represent the verified structures. They are regression tests for parser behavior, not proof of full brand coverage. Before a production importer is considered, the adapters still need fixture-based validation against additional real page variants and a permission review.
