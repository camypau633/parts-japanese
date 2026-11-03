# PartScope CatCar Japanese preview audit — 2026-11-03

## Source run

- Repository: camypau633/parts-japanese
- Workflow run: [41592807044](https://github.com/camypau633/parts-japanese/actions/runs/41592807044)
- Commit: 3ee5b19cf3d89a9c2cb8260a19d2cec3a7ba0004
- Artifact: catcar-real-artifact-regression
- Scope: Japanese makes only — Toyota and Nissan.

## Combined export

The regression combined eight Toyota Camry group documents, the Toyota oil-filter fixture, and the Nissan Pixo fixture.

- 264 PartScope records: 189 Toyota and 75 Nissan.
- 260 unique SKU keys.
- 403 factory catalogue rows with source provenance.
- 264/264 records have explicit vehicle-year context.
- 189/264 records have a confirmed engine code. All 75 Nissan records intentionally leave engine blank because the captured Nissan URL and inspected catalog context do not state it.
- 10/10 diagram URLs were reachable as PNG images.
- All 10 diagrams returned PNG dimensions through bounded byte-range requests; no full image downloads were used.
- 407 hotspot entries passed export validation: 204 Toyota and 203 Nissan.
- The Nissan diagram contains 39 source coordinate zones; 27 position identifiers match table rows, while 110, 117, and 311 remain unresolved and are not converted into invented part records.

## Data limitations

- Analogues exported: 0.
- Physical dimensions exported: 0.
- Technical drawings exported: 0.
- Missing Nissan engine data is not inferred from the model name.
- The 407 hotspot count is the number of exported hotspot entries attached to SKU records, not the number of unique source rectangles. Multiple OEM variants can legitimately refer to the same catalog position.

## Decision

**Japanese schema and bounded diagram export: pass for this sample. Production readiness: not approved.**

This remains a preview dataset. It must be published only under public/data-preview/catcar/; PartScope production public/data/ and search behavior must remain unchanged. This project does not process non-Japanese makes; other markets belong in separate repositories.

No mass extraction is authorized by this validation.
