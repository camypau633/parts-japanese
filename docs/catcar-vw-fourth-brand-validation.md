# CatCar Volkswagen fourth-brand validation

Date: 2026-11-02

## Scope

One bounded leaf page from the combined Audi / Volkswagen / Skoda / Seat catalog family:

- Make: Volkswagen
- Model: Campmob. (Typ2/Transp./LT), Europe
- Catalog year: 2018
- Group: Body
- Illustration: 86735

This is one leaf-page probe, not a full VAG catalog crawl.

## Verified extraction

- HTTP status: 200
- HTML size: 59,651 bytes
- Table rows: 39 including header (38 body rows)
- Table headers: position, part number, Description, Remark, ST, Model data (with additional empty/layout cells)
- 26 coordinate elements in HTML
- 22 unique hotspot identifiers
- Diagram image fetched successfully: HTTP 200, 59,651 bytes, image/png
- Image URL: `http://ci.catcar.info/vag_2017_12/452/452867350.png`

## Hotspot-to-table comparison

The diagram hotspot identifiers match 22 of the table's unique position codes.

- Matched hotspot identifiers: 22
- Hotspot identifiers without a table position: 0
- Table position codes without a hotspot: `(40)`

The unmatched table marker `(40)` must remain unresolved until its meaning is confirmed from the raw row markup and page behavior. Do not fabricate a hotspot for it.

The HTML exposes `srcTop`, `srcLeft`, `srcWidth`, `srcHeight`, and `srcNum` on coordinate elements. The coordinate `name` values correspond to the table's position column on this page.

## Important table structure

The table contains continuation/variant rows where the position cell is empty but a part number is present. For example, a base part number can be followed by variant part numbers with color or production-period suffixes. These rows must not be dropped.

The current probe confirms the visible row values but does not yet prove the precise parent-child semantics for every blank-position continuation row. Preserve row order and raw cells; implement inheritance of the preceding position only after confirming the underlying row markup or script behavior.

## Architecture implications

This is a fourth distinct catalog family/layout pattern:

- Toyota: AJAX row reveal and separate OEM/applicability variation records.
- Nissan: static HTML table; diagram positions match `srcNum`.
- Ford: hierarchical group navigation and static leaf table; diagram positions match `name` against `Code`.
- Volkswagen / VAG: combined make catalog, static table with variant continuation rows; diagram positions match `name` against the table position column.

The common output model remains viable, but the VAG adapter must preserve table row order and distinguish positioned rows from continuation rows.

## Limits

This validates one Volkswagen page only. It does not prove all VAG makes, markets, years, or page layouts. It does not authorize bulk collection. Terms of use must be reviewed before automated bulk collection.
