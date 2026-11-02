# CatCar POC — Camry Stage A validation

Date: 2026-11-02  
Repository: `camypau633/parts-japanese`  
Latest end-to-end workflow: [41469740318](https://github.com/camypau633/parts-japanese/actions/runs/41469740318)  
Normalizer-only workflow: [41466769287](https://github.com/camypau633/parts-japanese/actions/runs/41466769287)  
Code commit used by latest end-to-end run: `655db39e0bdfff6e3d5d6bac5a14976b57bd959e`

## Scope

A bounded sample of 8 groups from Toyota Camry catalog 284170, modification ACV30-AEPNK, engine 2AZFE. The probe saved each of the 8 group HTML pages, all 123 sampled AJAX response pages, and the JSON extraction summary. It did not crawl the remaining catalog.

## Raw source and normalized coverage

- 8 group HTML pages parsed.
- 123 source part rows found in those group pages.
- All 123 of 123 part rows had their AJAX responses sampled; no rows in these eight groups remain unsampled.
- 322 OEM table records parsed from the saved AJAX responses and cross-checked against their raw HTML.
- 8 additional part rows returned CatCar's literal `No applicable data!` response. They are preserved as explicit no-applicable-data statuses, not fabricated OEM numbers.
- The normalized document set therefore contains 330 OEM/status entries: 322 source table rows plus 8 explicit no-applicable-data markers.
- 183 distinct OEM numbers were present in the 322 table rows.
- 8 diagram images and 137 source hotspots were parsed.
- All 8 diagram URLs returned HTTP 200 with `image/png`; bounded range reads returned PNG dimensions without downloading full image files.
- All 137 source hotspots matched a part-row identifier; all 123 part rows had at least one matching hotspot in these 8 groups.
- All 8 normalized group documents passed the shared JSON Schema.
- Toyota group rows now retain their actual second-cell part descriptions (for example, `GASKET KIT, ENGINE OVERHAUL`) and the original row cells.

## PartScope preview export

The same workflow passed the 8 normalized group documents into the existing PartScope exporter, writing only to a temporary GitHub Actions artifact. It did not publish to `camypau633/partscope` or modify its production data.

- 8 normalized documents read.
- 187 PartScope catalogue records exported for 183 unique SKU keys.
- 322 factory catalogue rows validated.
- All 187 catalogue records retained Toyota, Camry, 2AZFE and the explicitly encoded profile period 09/2001–01/2006.
- All 187 records had a CatCar diagram URL.
- 14 two-character JSON shards were generated in the isolated preview artifact.
- OEM provenance in factory rows includes the AJAX source URL, group ID and record order.
- 202 verified interactive hotspots were exported across all 187 catalogue records.
- The hotspot coordinates use the centres of CatCar's source rectangles in natural image pixels. The bounded geometry probe verified PNG dimensions, image bounds, and the CatCar responsive-coordinate script before enabling export.
- Four SKU keys appear in more than one catalog group; the exporter preserves them as separate PartScope candidates with their own diagrams and positions instead of merging away catalog context.
- Analogues exported: 0.
- Physical dimensions exported: 0.

## PartScope UI compatibility

The corresponding UI changes were committed to `camypau633/partscope` and the GitHub Pages deployment completed successfully: [build and deploy run 41469868745](https://github.com/camypau633/partscope/actions/runs/41469868745).

- Diagram hotspot popovers display the saved period and applicability text.
- Multiple records for one SKU are labelled as separate catalogue records, not separate manufacturers.
- Sharing a diagram preserves the selected catalogue record ID.
- Only application code was deployed. The Camry preview shards remain in the Actions artifact; production catalogue data was not changed.

## Verified multi-OEM examples

| Part row | Records | Distinct OEMs |
|---|---:|---:|
| 09110 | 5 | 3 |
| 04111 | 15 | 8 |
| 11101 | 21 | 11 |
| 11400 | 4 | 2 |
| 11302 | 3 | 2 |

For example, part row `04111` has multiple OEM values across successive periods, and in some periods two different OEMs are listed simultaneously. The source does not establish a supersession relationship, so all records remain separate.

## Missing-data cases

- `9151180830` and `91511B0614`: OEM is present, but period and applicability cells are genuinely empty in the source HTML.
- `12321A` and `12322`: CatCar returns the literal response `No applicable data!`, not a table with missing fields.

These cases remain distinct:
1. OEM record with complete fields;
2. OEM record with empty period/applicability;
3. explicit no-applicable-data response;
4. request or parsing error.

## Source-use gate

This technical validation does not establish permission to redistribute CatCar catalogue data. No authoritative reuse/licensing terms for `catcar.info` were confirmed during this pass, and the site's `robots.txt` endpoint could not be independently retrieved. Keep the current bounded sample as a research artifact; do not expand the crawl to the remaining groups or publish the data in the public PartScope production catalogue until access and redistribution rights are confirmed.

## Limitations and next work

- This is a bounded Camry sample of the first 8 catalog groups, not full coverage of the entire Camry catalog.
- The 187 preview catalogue records are not ready for production publication.
- Temporal scan found 167 overlapping-period pairs and 219 adjacent-period OEM changes. These are observations only, not proof of replacement or interchangeability.
- 43 OEM table rows have both period and applicability cells empty. These are missing source values, not malformed dates; the original blanks are preserved.
- No analogues or physical dimensions have been inferred.
- Physical dimensions are not present in this sample; no diameter, height, thread or other measurements are fabricated.
- No mass extraction was performed.
- The workflow is still a research/preview pipeline; production publication remains disabled.
