# CatCar POC — cross-brand validation: Nissan Pixo

Date: 2026-11-02  
Repository: `camypau633/parts-japanese`  
Workflow: [41449985400](https://github.com/camypau633/parts-japanese/actions/runs/41449985400)  
Commit: `e636caa5714d04d1b986d76dd4d92ac7c3232d94`

## Scope

A single Nissan/Infiniti catalog page was tested to determine whether the Toyota extraction findings transfer to another make and a different CatCar catalog layout.

Vehicle/catalog page:
- Make/catalog: Nissan/Infiniti
- Model: PIXO (UA0)
- Region: Europe, left-hand drive
- Section: ENGINE MECHANICAL
- Group: PISTON, CRANKSHAFT & FLYWHEEL
- Catalog image: `http://ci.catcar.info/nissan_2017_09/el/043/page_120_A_002.png`

This is a bounded one-page probe, not a full Nissan catalog extraction.

## Page and table results

- HTTP 200; HTML response: 115,365 bytes.
- 78 table rows including the header (77 data rows).
- 27 unique part-row identifiers.
- 5 image elements on the page; one exploded diagram image was identified.
- The Nissan page exposes OEM, description, production period, alternative number and quantity-per-vehicle directly in HTML table cells. Unlike the Toyota sample, this page does not use the same per-row AJAX reveal pattern.

Sample source rows:
- `12000-4A00A`, PISTON SET-W/PISTON RING, 03/2009–01/2012, quantity 03.
- `12000-4A00B`, same part-row identifier `12010S`, 01/2012–, quantity 03.
- `12033-4A00A`, RING SET-PISTON PIN, 03/2009–.
- `12033-4A00C`, same row identifier `12033M`, 02/2010–.

## Diagram and hotspot validation

- Diagram image downloaded successfully: HTTP 200, 14,082 bytes.
- 39 coordinate zones in HTML.
- 30 unique `srcNum` values.
- 27 unique values match the 27 part-row identifiers in the table.
- 3 unmatched values: `110`, `117`, `311`. Preserve these as unresolved diagram callouts; do not silently discard them or invent part records.
- CatCar's JavaScript confirms that clicking a `.coord` zone reads `srcNum` and searches for a table row with the matching `name`; the separate resize script recalculates hotspot positions from `srcTop/srcLeft/srcWidth/srcHeight`.

This confirms the diagram-to-table link on this Nissan page for all 27 catalog part-row identifiers represented by the table.

## Cross-brand conclusions

1. The basic data concepts transfer: part-row identifier, OEM, production period, description and diagram coordinates.
2. The page layout and extraction mechanism differ from Toyota: Nissan provides a static HTML table rather than the Toyota AJAX row reveal used in the Camry probe.
3. Diagram zones use `srcNum` to refer to table row identifiers; hotspot geometry is stored in source HTML and adjusted responsively by CatCar JavaScript.
4. The importer must use brand/catalog adapters or page-layout detection. A single Toyota-specific parser is not universal.
5. Preserve all source fields, including alternate numbers, per-vehicle quantity, repeated part-row identifiers and unmatched diagram callouts.

## Limitations

- Only one Nissan model page and one diagram group were tested.
- This does not prove that every Nissan catalog section or every CatCar brand uses this layout.
- No mass extraction was performed.
- CatCar terms/conditions for automated collection still require review before any broad extraction.

## Conclusion

The extraction concept is not Toyota-only: a second make and a different catalog layout expose equivalent core data and working diagram hotspots. However, CatCar uses multiple page structures and extraction methods. The correct architecture is a shared normalized output with separate source/layout adapters, not one universal HTML parser.
