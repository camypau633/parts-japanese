# CatCar POC — Camry Stage A validation

Date: 2026-11-02  
Repository: `camypau633/parts-japanese`  
Latest end-to-end workflow: [41467023268](https://github.com/camypau633/parts-japanese/actions/runs/41467023268)  
Normalizer-only workflow: [41466769287](https://github.com/camypau633/parts-japanese/actions/runs/41466769287)  
Code commit used by latest end-to-end run: `6056c78091029efbc568efd7a0fd4139c8fe28bf`

## Scope

A bounded sample of 8 groups from Toyota Camry catalog 284170, modification ACV30-AEPNK, engine 2AZFE. The probe saved each of the 8 group HTML pages, all 34 sampled AJAX response pages, and the JSON extraction summary. It did not crawl the remaining catalog.

## Raw source and normalized coverage

- 8 group HTML pages parsed.
- 123 source part rows found in those group pages.
- 34 of 123 part rows had their AJAX responses sampled; 89 rows remain explicitly marked `requires_ajax` and are not treated as known OEM records.
- 148 OEM table records parsed from the 34 saved AJAX responses and cross-checked against their raw HTML.
- 2 additional part rows (`12321A`, `12322`) returned CatCar's literal `No applicable data!` response. They are preserved as explicit no-applicable-data statuses, not fabricated OEM numbers.
- The normalized document set therefore contains 150 OEM/status entries: 148 source table rows plus 2 explicit no-applicable-data markers.
- 76 distinct OEM numbers were present in the 148 table rows.
- 8 diagram images and 137 source hotspots were parsed.
- All 137 hotspots matched a part-row identifier; all 123 part rows had at least one matching hotspot in these 8 groups.
- All 8 normalized group documents passed the shared JSON Schema.

## PartScope preview export

The same workflow passed the 8 normalized group documents into the existing PartScope exporter, writing only to a temporary GitHub Actions artifact. It did not publish to `camypau633/partscope` or modify its production data.

- 8 normalized documents read.
- 76 unique PartScope SKU records exported.
- 148 factory catalogue rows validated.
- All 76 records retained Toyota, Camry, 2AZFE and the explicitly encoded profile period 09/2001–01/2006.
- All 76 records had a CatCar diagram URL.
- 9 two-character JSON shards were generated in the isolated preview artifact.
- OEM provenance in factory rows includes the AJAX source URL, group ID and record order.
- Analogues exported: 0.
- Physical dimensions exported: 0.
- Hotspots exported: 0. Although the source coordinates and row matches were parsed, they are not yet calibrated against the actual image coordinate system, so the exporter correctly omits them.

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

## Limitations and next work

- This is a bounded Camry sample, not full coverage of the 123 part rows: 89 AJAX rows remain unsampled.
- The 76 preview SKU records are not ready for production publication.
- No analogues or physical dimensions have been inferred.
- Hotspot coordinates need image-dimension and coordinate-system calibration before export to PartScope.
- No mass extraction was performed.
- The workflow is still a research/preview pipeline; production publication remains disabled.
