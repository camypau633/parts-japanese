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

## One model page

Workflow: [41594034763](https://github.com/camypau633/parts-japanese/actions/runs/41594034763)

Selected link: 2011 Honda Civic, 3-door entry.

- HTTP 200; HTML size 11,192 bytes.
- Page title: `2011 CIVIC - Catcar.info`.
- Breadcrumb shows region `Европа`.
- The page only contains headings for transmission and configuration and an unfilled region placeholder.
- No detail rows, OEM numbers, diagrams or hotspot coordinates were present in the returned HTML.
- This is an intermediate configuration-selection page, not a usable parts-group page.

## Decision

Do not create a Honda adapter from this page. The page structure and next configuration-selection request must be understood first. Next bounded step: inspect the site's own Honda page JavaScript and the configuration-selection flow, then choose one real configuration and one parts group if the site exposes it.

The current work remains limited to Japanese vehicle makes. This Honda sample is from the Europe region in CatCar's catalog; that region label is recorded explicitly and is not silently treated as a Japanese domestic-market catalog.

## Follow-up: region index and site script

Workflow: [41594235645](https://github.com/camypau633/parts-japanese/actions/runs/41594235645)

- `/honda/?l=` returned the same Honda landing index (HTTP 200, 21,252 bytes); it did not expose a separate region list.
- The public `/js/script.js?v=2.0` file returned HTTP 200 (9,681 bytes).
- The inspected script contains generic modal AJAX and the `getArticles()` handler. When its state is 70, it navigates to the supplied `script_href/?l=...`; otherwise it requests `&st=81` for a part-row expansion.
- The script does not contain Honda-specific transmission/trim or region-selection logic. Those controls must be populated elsewhere or the selected catalog entry is incomplete.
- No additional Honda catalog requests were made after this discovery.

**Current Honda conclusion remains unchanged:** the sampled 2011 Civic page is not a parts-group page. We need another bounded model/configuration sample or an identified server-rendered selection endpoint before writing a Honda adapter.

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
- Honda is not yet enabled in PartScope export. The image dimensions and all hotspot bounds must pass an independent check first.
