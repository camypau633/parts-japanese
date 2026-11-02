# PartScope Japanese catalogue exporter

The offline converter turns normalized CatCar JSON documents into the static shard format consumed by `camypau633/partscope`.

## Run

```bash
python -m tools.catcar_poc.export_partscope \
  --input normalized/toyota.json \
  --input normalized/nissan.json \
  --output out/partscope-data
```

Repeat `--input` for each normalized document. The output directory must be empty; this prevents stale shards from being mixed into a new export. Python 3.8+ and the standard library are sufficient.

## Mapping

- The cleaned OEM number is the shard key and top-level record key.
- Nissan static table rows become `factory_parts` entries.
- Toyota OEM AJAX rows are joined to their catalogue rows by `source_row_id`; OEM variations are retained as separate factory records.
- Vehicle context becomes `compatibility`.
- The first confirmed catalogue illustration URL is carried into `diagram.diagramUrl`.
- Factory catalogue rows are never copied to `analogs`.
- Analogue and physical-dimension arrays remain empty until a separate validated source exists.
- Hotspots are omitted from the app-facing output until source coordinates are calibrated against the actual image coordinate system. Raw geometry remains in the normalized source document.

## Guardrails

- Only Toyota and Nissan are enabled for production export. Ford and Volkswagen research fixtures are rejected.
- The converter is offline and makes no HTTP requests.
- It does not crawl pages or download image assets.
- Shards are keyed by the first two characters of the cleaned SKU and capped at 2 MiB by default.
- `export-report.json` records counts, explicit omissions, and a fail-closed integrity report: SKU/shard-key agreement, OEM row-to-SKU agreement, Toyota/Nissan-only brands, CatCar provenance/hosts, compatibility make consistency, and diagram URL format.
- Export stops before writing shards if an integrity check fails. The report also measures how many records have explicit compatibility years, engine codes, and diagram URLs; missing source fields remain missing rather than being inferred.
- The real-artifact workflow also probes the unique CatCar diagram URLs with a strict cap (20 URLs), using `HEAD` and at most a one-byte range request. It never downloads full images; reachability results are stored in `diagram-url-check.json`.

## Real-fixture regression

GitHub Actions runs the normalized real Toyota Camry and Nissan Pixo fixtures through this exporter after the parser/schema regression. The latest successful run exported **77 SKU records across 7 shards** (Toyota and Nissan only). The largest shard was about 113 KiB, below the 2 MiB project budget.

This confirms the conversion path on the captured examples. It is not a full production catalogue import, does not establish full make/model coverage, and does not publish the generated shards into the PartScope app repository.
