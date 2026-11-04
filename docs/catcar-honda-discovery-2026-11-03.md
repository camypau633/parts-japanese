# Honda CatCar discovery — 2026-11-03

## Scope

Bounded discovery of one Japanese vehicle make (Honda). No other manufacturers are included in this current project.

## Honda landing page

Workflow: [41593919774](https://github.com/camypau633/parts-japanese/actions/runs/41593919774)

- `https://www.catcar.info/honda/` returned HTTP 200.
- Page title: `HONDA - Catcar.info`.
- HTML size: 21,252 bytes.
- 55 catalog links were found.
- Visible year links cover 1982–2012.
- Model links include Accord, Accord Tourer, Ballade, City, Civic, CR-V, CR-Z, Crosstour, Insight, Jazz, Odyssey and Pilot.

## One model page — Civic initial dead end

Workflow: [41594034763](https://github.com/camypau633/parts-japanese/actions/runs/41594034763)

Selected link: 2011 Honda Civic, 3-door entry.

- HTTP 200; HTML size 11,192 bytes.
- Page title: `2011 CIVIC - Catcar.info`.
- Breadcrumb shows region `Европа`.
- The page only contains headings for transmission and configuration and an unfilled region placeholder.
- No detail rows, OEM numbers, diagrams or hotspot coordinates were present in the returned HTML.
- This is an intermediate configuration-selection page, not a usable parts-group page.

## Initial decision after Civic probe

The Civic page alone was insufficient to create an adapter. This conclusion was superseded by the separate Accord 2011 probe below, which exposed a populated configuration list and a real parts hierarchy.

The current work remains limited to Japanese vehicle makes. This Honda sample is from the Europe region in CatCar's catalog; that region label is recorded explicitly and is not silently treated as a Japanese domestic-market catalog.

## Follow-up: region index and site script

Workflow: [41594235645](https://github.com/camypau633/parts-japanese/actions/runs/41594235645)

- `/honda/?l=` returned the same Honda landing index (HTTP 200, 21,252 bytes); it did not expose a separate region list.
- The public `/js/script.js?v=2.0` file returned HTTP 200 (9,681 bytes).
- The inspected script contains generic modal AJAX and the `getArticles()` handler. When its state is 70, it navigates to the supplied `script_href/?l=...`; otherwise it requests `&st=81` for a part-row expansion.
- The script does not contain Honda-specific transmission/trim or region-selection logic. Those controls must be populated elsewhere or the selected catalog entry is incomplete.
- At this stage no additional Honda catalog requests were made; the later bounded Accord probes are documented below.

**Civic-specific conclusion:** that selected Civic page remains an intermediate page with no parts group. The Accord path below demonstrates a separate working Honda catalog route.

## Second model sample: 2011 Accord, 4-door

Workflow: [41594697255](https://github.com/camypau633/parts-japanese/actions/runs/41594697255)

- HTTP 200; HTML size 62,113 bytes.
- The page contains 99 table rows.
- It exposes three regional sections: Austria (KW), Arab countries (KY), and United Kingdom (KE).
- It lists several transmission/grade combinations, including 5AT/5MT and 2.0, 2.2, 2.4 and 3.5 grades.
- Unlike the Civic sample, this page contains real configuration links with encoded region, transmission, grade and modification IDs.
- A specific next-level configuration has been selected for inspection: Austria (KW), 5AT, 2.0 EX. Its URL encodes modification IDs 4094 and 4095.

The Accord page demonstrates that Honda's configuration selection can be represented as explicit catalog links. It is still a Europe-region sample of the Japanese Honda make, not a Japanese domestic-market sample.

## Selected configuration page

Workflow: [41594801969](https://github.com/camypau633/parts-japanese/actions/runs/41594801969)

Selected configuration: 2011 Accord, 4-door, Austria (KW), 5AT, 2.0 EX.

- HTTP 200; HTML size 19,664 bytes.
- Page title and breadcrumbs confirm the selected configuration.
- The page exposes five equipment-option rows (AB3, ABS, LH, SR, STL).
- It provides five top-level parts groups:
  1. Двигатель
  2. Трансмиссия
  3. Электрика, впускная/выпускная система, охлаждение и отопление
  4. Рулевое управление, тормоза и подвеска
  5. Внешняя/внутренняя отделка
- The group links carry the selected vehicle, region, transmission, grade and modification IDs in the encoded query.
- The configuration landing page itself has no part table, diagram or hotspot; those are expected at the next group level.

This is the first Honda path that reaches an actual catalog structure. The next bounded probe follows only the Engine group.

## Engine group listing

Workflow: [41594884552](https://github.com/camypau633/parts-japanese/actions/runs/41594884552)

- The selected Honda Accord Engine group returned HTTP 200 (31,070 bytes).
- It contains 32 table rows: five equipment-option rows, one header row, and 26 engine subgroups.
- Subgroups include throttle body, intake manifold, fuel injector, converter, ignition coil, alternator, wiring harness, cylinder head, camshaft, oil pump, cylinder block/oil pan, water pump, crankshaft/piston and gasket kit.
- Each subgroup has its own encoded `st=60` link and a `bcode` identifier.
- This group-list page itself has no part-level table or exploded diagram; the next level is an individual subgroup page.

This confirms a deeper Honda hierarchy: model → region/transmission/grade → main group → subgroup → part table/diagram.

## First Honda part-table adapter

- Added `HondaAdapter` (`honda_static`) to the offline adapter library and CLI.
- It locates the explicit `Код / Артикул / Описание` header rather than assuming the first table row is a part.
- It preserves source row order, OEM text, description, additional-information text and option codes.
- It retains duplicate rows at the same diagram position; the two position-1 OEM rows remain separate because their option-code sets differ.
- Unit test covers the observed Accord E-1 layout, six parts, one diagram image, nine hotspot rectangles and repeated positions 4 and 5.
- Unit tests passed: [41595193453](https://github.com/camypau633/parts-japanese/actions/runs/41595193453).
- Honda preview conversion is enabled for this single captured Accord E-1 group. A unit test verifies five cleaned SKU keys, six factory rows, preserved option-code variants, nine hotspot rectangles and the 2011 model-year context. This does not mean broad Honda coverage or production publication.

## Honda E-1 diagram: watermark and geometry

Workflow: [41595234384](https://github.com/camypau633/parts-japanese/actions/runs/41595234384)

- Diagram: `E__0100.png`, HTTP 200, PNG, 23,213 bytes.
- Native dimensions: 1920 × 959 pixels.
- All 9 hotspot rectangles are within the image bounds.
- Repeated positions are intentional: position 4 has four rectangles and position 5 has two.
- The full-resolution image was visually inspected. No CatCar logo, watermark text, diagonal overlay or translucent repeating mark was observed.
- OCR found only diagram labels and cross-references such as E-3 and E-15-10; these are native drawing annotations, not watermarks.
- The visible drawing labels match the hotspot positions 1–5.

**Honda E-1 sample: geometry pass, visible watermark not found.** This result applies to this one Honda diagram only.

## Honda preview conversion test

- Added Honda to the Japanese preview-conversion allowlist.
- The exporter now preserves Honda's additional source fields, including option-code differences, so the two position-1 table rows are not collapsed.
- Model year 2011 is carried into the compatibility year field; no engine code is guessed from the 2.0L grade.
- Verified geometry status 200 is accepted when the complete PNG was downloaded and inspected; all nine boxes are confirmed within 1920×959.
- Dedicated test passed: [41595507927](https://github.com/camypau633/parts-japanese/actions/runs/41595507927).
- Existing Toyota/Nissan real-artifact regression passed after exporter changes: [41595507960](https://github.com/camypau633/parts-japanese/actions/runs/41595507960).

The Honda sample can now be converted to PartScope preview records offline. It has not yet been published into the PartScope preview directory or production catalogue.


## Second main group: steering, brakes and suspension

Workflow: [41819963305](https://github.com/camypau633/parts-japanese/actions/runs/41819963305)

Selected group: 2011 Accord, 4-door, Austria (KW), 5AT, 2.0 EX — “РУЛЕВОЕ УПРАВЛЕНИЕ, ТОРМОЗНАЯ СИСТЕМА, ПОДВЕСКА”.

- HTTP 200; HTML size 36,240 bytes.
- The page contains 26 table rows: five equipment-option rows, one header row and 20 subgroup links.
- Subgroups cover tires/wheels, rear and front brakes, front driveshaft, brake pedal/master cylinder, ABS/VSA, brake lines, parking brake, front knuckle, front and rear lower arms, front and rear shock absorbers, steering wheel/column, power-steering gearbox and lines, and selector lever.
- Each subgroup link carries the same selected Accord configuration context plus a distinct subgroup code (`bcode`).
- Like the Engine group listing, this is a hierarchy page, not a part-level table: it has no exploded diagram or hotspot geometry yet.
- The inspected page returned only generic checkbox icons; no actual diagram image was embedded at this level.

This confirms that the second main Honda group uses the same high-level navigation pattern as Engine: main group → named subgroup → part table/diagram. It does **not** yet prove that every subgroup's part-table layout is identical to E-1, so the adapter remains validated only against the E-1 part page.

The next useful probe is one bounded subgroup page from this list (for example B-28 Front Shock Absorber), to check whether its part table and diagram geometry follow the E-1 pattern.


## B-28 subgroup: front shock absorber

Workflow: [41820216716](https://github.com/camypau633/parts-japanese/actions/runs/41820216716)

Selected subgroup: 2011 Accord, 4-door, Austria (KW), 5AT, 2.0 EX — B-28 `FRONT SHOCK ABSORBER`.

- HTTP 200; HTML size 58,183 bytes.
- The page contains 37 table rows: five equipment-option rows, one explicit part-table header, and 31 part rows including distinct option and supplier variants.
- The OEM table includes spring, right/left front shock absorber assemblies and units, mounting bases, dust covers, bump stops, collars and fasteners.
- The same OEM can occur in multiple rows because option codes differ. These rows must remain distinct; position numbers alone are not unique row identifiers.
- There are 19 distinct diagram positions and 20 hotspot rectangles. Position 7 has two separate rectangles.
- All hotspot coordinates are available as `srcTop`, `srcLeft`, `srcWidth` and `srcHeight`; the image is `http://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2800.png`.
- The B-28 HTML includes the actual diagram URL and hotspot geometry, confirming the same core table/diagram structure as E-1. The part-row count and duplicate-option behavior are more complex, so regression coverage should be expanded before broad Honda enablement.

## B-28 diagram: watermark and geometry audit

Workflow: [41820435155](https://github.com/camypau633/parts-japanese/actions/runs/41820435155)

- Diagram: `B__2800.png`, HTTP 200, PNG, 17,331 bytes.
- Native dimensions: 1920 × 959 pixels.
- All 20 hotspot rectangles are inside the image bounds; 19 distinct position labels are present.
- Position 7 has two separate rectangles, and both are retained.
- The full-resolution image was visually inspected. No CatCar logo, watermark text, diagonal overlay or translucent repeating mark was observed.
- OCR screening found only native diagram position labels and the drawing identifier `TA08B2800`; no CatCar, copyright or website indicators were found.

**B-28 sample: geometry pass, visible watermark not found.** This conclusion applies only to this image, not to all Honda/CatCar diagrams.

This is the second verified Honda part-table subgroup (after Engine E-1). Both are from the Austria (KW) catalog configuration; this does not establish JDM coverage or all Honda models/years.

## B-28 parser and PartScope export regression

- Added a B-28 adapter regression using representative rows from the captured source layout. It verifies duplicate spring OEM rows with different option-code sets, alternate supplier/part variants sharing a diagram position, repeated position 7, and the diagram reference.
- Added a PartScope export regression for B-28. It verifies that the two spring rows remain separate factory-part rows, model year 2011 is retained, engine code remains blank rather than guessed, and both position-7 hotspot rectangles survive export.
- Both test suites passed in [CatCar adapter unit tests run 115](https://github.com/camypau633/parts-japanese/actions/runs/41820744245).
- The existing bounded Toyota/Nissan real-artifact regression also passed after these changes: [run 40](https://github.com/camypau633/parts-japanese/actions/runs/41820744247). This checks that the Honda additions did not break those existing source paths; it is not a full Honda production-import run.

Honda conversion remains an offline preview capability only. No Honda records or images have been published to PartScope preview or production.


## Third part-table subgroup: B-22 front brake

Workflow: [41821028881](https://github.com/camypau633/parts-japanese/actions/runs/41821028881)

Selected subgroup: 2011 Accord, 4-door, Austria (KW), 5AT, 2.0 EX — B-22 `FRONT BRAKE`.

- HTTP 200; HTML size 51,218 bytes.
- The page contains 31 table rows: five equipment-option rows, one header and 25 part rows.
- The 25 part rows contain 24 unique OEM numbers.
- Position 5 contains two rows for the same hub-bearing OEM `44300-TA0-A61`, with different option-code sets.
- Position 18 contains four distinct wheel-bolt OEMs from different suppliers: `90113-S84-901`, `90113-SD4-901`, `90113-SD4-902` and `90113-SJK-901`. All four rows must remain distinct even though they share the same diagram position.
- The diagram is `http://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2200.png`.
- There are 23 hotspot rectangles for 21 distinct position labels. Positions 12 and 13 each have two rectangles.
- The adapter and exporter regression tests now cover this pattern: repeated OEM with option differences, four different OEMs at one position, and repeated hotspot rectangles.

## B-22 diagram: watermark and geometry audit

Workflow: [41821329190](https://github.com/camypau633/parts-japanese/actions/runs/41821329190)

- Diagram: `B__2200.png`, HTTP 200, PNG, 43,490 bytes.
- Native dimensions: 1920 × 959 pixels.
- All 23 hotspot rectangles are inside image bounds; 21 distinct position labels are present.
- Positions 12 and 13 each have two separate rectangles, both preserved.
- The full-resolution image was visually inspected. No CatCar logo, watermark text, diagonal overlay or translucent repeating mark was observed.
- OCR screening found native labels and cross-references to B-21, B-21-1 and B-21-2, plus drawing identifier `TA08B2200`; no CatCar, copyright or website indicators were found.

**B-22 sample: geometry pass, visible watermark not found.** This applies only to this one image. This is an Austria (KW) catalog sample, not JDM data.

- The B-22 adapter and PartScope export regressions passed in [CatCar adapter unit tests run 116](https://github.com/camypau633/parts-japanese/actions/runs/41821425683).
- The captured 51,218-byte B-22 HTML was also passed through the actual `HondaAdapter` in [B-22 probe run](https://github.com/camypau633/parts-japanese/actions/runs/41821659669): 25 part rows, 24 unique OEMs, both option variants at position 5, all four distinct position-18 wheel-bolt OEMs, 23 hotspots and one diagram image were verified.
- Existing Toyota/Nissan real-artifact regression passed again after the Honda changes: [run 42](https://github.com/camypau633/parts-japanese/actions/runs/41821425837).


## B-27 front knuckle: incomplete catalog response

Probe: [41821783325](https://github.com/camypau633/parts-japanese/actions/runs/41821783325)

- HTTP 200; HTML size 16,429 bytes.
- The returned page contains the five equipment-option rows and a part-table header only; there are no part rows.
- No hotspot coordinates were returned.
- The only diagram candidate contains the literal template path `/honda/euro/{npl}/IMGE/B__2700.png`, not a resolved image URL.
- This response is classified as an incomplete/intermediate catalog page and is not eligible for normalization or export. HTTP 200 alone is not sufficient evidence that a subgroup contains usable parts.


## Fourth part-table subgroup: B-19-10 rear brake

Workflow: [41822139081](https://github.com/camypau633/parts-japanese/actions/runs/41822139081)

Selected subgroup: 2011 Accord, 4-door, Austria (KW), 5AT, 2.0 EX — B-19-10 `REAR BRAKE`.

- HTTP 200; HTML size 65,034 bytes.
- The page contains 42 table rows: five equipment-option rows, one header and 36 part rows.
- The 36 part rows contain 26 unique OEM numbers.
- Ten OEMs appear twice with different option-code sets (including the right/left rear caliper assemblies and several internal brake components).
- Position 19 contains three different wheel-bolt OEMs; position 21 contains two different O-ring OEMs.
- There are 26 hotspot rectangles for 23 distinct position labels. Position 17 has three separate rectangles and position 10 has two.
- The captured HTML passed the actual `HondaAdapter` regression step in the workflow: all 36 part rows, 26 unique OEMs, ten option-variant pairs, the three position-19 OEMs, the two position-21 OEMs, 26 hotspots and one diagram image were verified.

## B-19-10 diagram: watermark and geometry audit

Workflow: [41822240524](https://github.com/camypau633/parts-japanese/actions/runs/41822240524)

- Diagram: `B__1910.png`, HTTP 200, PNG, 38,652 bytes.
- Native dimensions: 1920 × 960 pixels.
- All 26 hotspot rectangles are inside the image bounds; 23 distinct position labels are present.
- Position 17 has three separate rectangles; position 10 has two.
- The full-resolution image was visually inspected. No CatCar logo, watermark text, diagonal overlay or translucent repeating mark was observed.
- OCR screening found native drawing labels and identifier `TA08B1910E`; no CatCar, copyright or website indicators were found.

**B-19-10 sample: geometry pass, visible watermark not found.** This result applies only to this one image. This sample is also Austria (KW), not JDM.


## Fifth part-table subgroup: B-29 rear lower arm

Probe: [41826563235](https://github.com/camypau633/parts-japanese/actions/runs/41826563235)  
Real adapter validation: [41826682904](https://github.com/camypau633/parts-japanese/actions/runs/41826682904)

Selected subgroup: 2011 Accord, 4-door, Austria (KW), 5AT, 2.0 EX — B-29 `REAR LOWER ARM`.

- HTTP 200; HTML size 77,717 bytes.
- The page contains 50 table rows: five equipment-option rows, one header and 44 part rows.
- The 44 part rows contain 38 unique OEM numbers.
- Six position labels contain two rows each with different option-code sets: 7, 8, 15, 19, 23 and 31. All option variants are preserved.
- There are 41 hotspot rectangles for 38 distinct position labels. Position 25 has three separate rectangles; position 26 has two.
- The actual captured HTML passed through `HondaAdapter`: all 44 part rows, 38 unique OEMs, six option-variant pairs, 41 hotspots and one diagram image were verified.

**B-29 diagram watermark and geometry audit is running.** Diagram URL: `http://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2900.png`. This sample is also Austria (KW), not JDM.
