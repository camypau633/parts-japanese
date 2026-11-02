# CatCar Ford third-brand validation

Date: 2026-11-02

## Scope

A bounded inspection of one Ford catalog branch:

- Brand: Ford
- Model: Fiesta DX, 1995–2002
- Catalog: 424
- Group: A Body And Related Parts
- Selected subgroup: A04 Body And Related Parts — Dash Panel / Apron / Heater / Windscreen
- Leaf section: A04041 Heater

This is a single representative leaf page, not a full Ford catalog crawl.

## Verified extraction

The leaf page returned HTTP 200 and 233,829 bytes of HTML.

The table contains 26 rows including the header, i.e. 25 part rows. The visible columns are:

- Code
- Part number
- Name
- Production date

The diagram is available at:

`http://ci.catcar.info/ford_2017_01/euro/424/g001206802.png`

The image download returned HTTP 200 and 57,627 bytes.

## Diagram-to-table relationship

- 20 coordinate hotspot elements were found in the HTML.
- 14 unique hotspot identifiers were found.
- 14 unique part-row codes were found in the table.
- All 14 unique identifiers match.
- Unmatched hotspot identifiers: 0.
- Table codes without a hotspot: 0.

The HTML stores hotspot geometry in `srcTop`, `srcLeft`, `srcWidth`, and `srcHeight`; the hotspot's `name` identifies the table's `Code`.

The page also loads CatCar's shared `script.js?v=2.0` and `jquery.resizeImageCoords.js` assets. This probe establishes the HTML-level relationship and coordinates; it does not yet independently verify every interactive browser event.

## Architecture implications

The third brand confirms the need for separate source adapters and a common normalized output:

- Toyota Camry: table rows are revealed through AJAX tokens; OEM variation and applicability are returned as separate records.
- Nissan Pixo: catalog rows are present in static HTML; hotspot `srcNum` values link to part-row identifiers.
- Ford Fiesta: hierarchical group navigation leads to a static leaf table; hotspot `name` values link to the table's `Code` column.

Do not assume that a displayed part number is always an OEM supersession record. Preserve the source's own field names and raw values, and normalize them with brand/layout-specific adapters.

## Limits

This probe validates one Ford leaf page only. It does not establish universal Ford coverage, all Ford catalog layouts, or permission for mass collection. Terms of use must be reviewed before any bulk collection.
