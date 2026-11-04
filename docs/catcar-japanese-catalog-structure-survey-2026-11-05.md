# CatCar Japanese catalog structure survey

Date: 2026-11-05

This is a structural survey of the public CatCar navigation, not a claim that the
catalog contents have been fully extracted. All observations are retained as
source-page labels and URLs by the bounded crawler.

## Catalog roots

The CatCar Japanese section lists ten marques behind eight catalog roots:

- Toyota / Lexus: `/toyota/`
- Nissan / Infiniti: `/nissan/`
- Honda: `/honda/`
- Suzuki: `/suzuki/`
- Mazda: `/mazda/`
- Mitsubishi: `/mitsubishi/`
- Isuzu: `/isuzu/`
- Subaru: `/subaru/`

Daihatsu is not listed as an available Japanese catalog.

## Newly inspected catalog structures

### Suzuki

The root page presents regional navigation followed by model lists. The visible
region labels include All regions, Asia, Africa, Europe, Canada, Latin America,
Russia, United States, Middle East, Caribbean and Pacific. Selecting a region
changes the model list. Selecting a model leads to equipment/grade choices and
then catalog groups.

A live Asia branch was followed through APV → GC415T → Engine →
1 - ENGINE GASKET SET. Its parts table exposes the columns `Code`,
`Part number`, `Name`, `Additional information` and `Qty`; the inspected
sample contains real Suzuki part numbers such as `11402-61880` and
`11141-61J00`. A first header-driven Suzuki adapter now parses these fields,
preserving the selected market from the page filter. The adapter still needs
raw HTML regression captures and checks on other models and markets.

Suzuki stores the selected region in the base64-encoded `l` filter using a
numeric `marketId`. The following identifiers were observed directly on the
region links from the Suzuki root page:

| marketId | CatCar region label |
|---:|---|
| 1 | Africa |
| 2 | Asia |
| 3 | Canada |
| 4 | Caribbean |
| 5 | Europe |
| 6 | Latin America |
| 7 | Middle East |
| 8 | Pacific |
| 9 | Russia |
| 10 | United States |

There is no separate Japan link in the visible Suzuki region selector. Do not
convert Asia or All regions into Japan. Keep the raw market identifier and
region label separate; Japan/JDM presence must be verified from actual vehicle
records before assigning it.

### Mazda

The root offers Middle East, Europe, United States and Japan. The selected
market is explicit in the decoded filter (for example, `market==japan`). The
Japanese index contains model entries and a separate model/generation table
with production start, body/model code and catalog code. A selected generation
then opens a list of major groups (engine, transmission, body, chassis, etc.).

### Mitsubishi

The root offers Europe, Middle East, North America and Japan. The decoded
filter exposes `market==japan` for the Japan branch. The Japanese index is a
model table with model name, chassis/model code, production date range and DP
catalog identifier. Selecting a model leads to chassis/model variants and then
the catalog groups.

### Isuzu

The root is organized first by vehicle families rather than by region:
BUSES, COMPO, PICKUP, SUV and TRUCKS. Selecting a family leads to model codes;
a selected model can lead to modification records, which include identifiers,
RHD/LHD, emission/version notes and production-year spans. These distinctions
must be preserved as source configuration, not flattened into one model.

### Subaru

The public root presents separate market branches for Europe (LHD), Europe
(RHD), Japan and the United States. Selecting Japan opens a model index with
model name, production date range and series code. The inspected Japan index
includes, among others, Legacy B10-B15, Impreza G10-G14, Forester S10-S13,
WRX/LEVORG V10 and BRZ Z10. Several entries have open-ended production ranges
(for example, Legacy B15 from 07/2014 and Impreza G14 from 08/2016), so the
catalog must not be treated as ending at those dates. The next level is a
model/series page, followed by main groups and detail-group tables. The inspected
Legacy B15 C-series Engine group exposed Japanese selector fields and a parts
list with columns `№`, `Part number`, `Options`, `Applicable Models`,
`Production date`, `Note/Destination Code` and `Comment`. A first
header-driven Subaru adapter now preserves these fields. It still needs a
retained raw HTML fixture and validation across additional groups and markets.

The initial web inspection timeout was transient: the root and Japan branch
were subsequently opened successfully.

## Implementation consequences

- The common crawler can traverse these navigation levels because each level
  links to another URL under the same make path.
- The decoded CatCar filter must be preserved in every extracted document.
- Suzuki numeric region IDs are mapped only to the labels observed above.
- Mazda and Mitsubishi use explicit textual market labels.
- Isuzu requires family/model/modification hierarchy preservation.
- Subaru market navigation and a parts-list table layout are now verified. A first header-driven adapter is implemented for the observed columns, but it still needs a retained raw HTML fixture and validation across multiple groups and markets.
- None of these observations authorizes a detail-table parser. Detail parsers
  must be based on retained real HTML samples and regression fixtures.
