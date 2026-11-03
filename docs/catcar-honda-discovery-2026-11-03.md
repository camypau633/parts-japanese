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
