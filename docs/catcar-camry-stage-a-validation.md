# CatCar POC — Camry Stage A validation

Date: 2026-11-02  
Repository: `camypau633/parts-japanese`  
Workflow: [41448892073](https://github.com/camypau633/parts-japanese/actions/runs/41448892073)  
Commit: `802f408a3ac63000c8c2b900d76c7b3d073405b2`

## Scope

Bounded sample of 8 groups and 34 part rows from Toyota Camry catalog 284170, modification ACV30-AEPNK, engine 2AZFE. This is a validation sample, not a bulk extraction.

## Results

- 34 AJAX responses saved as raw HTML.
- 148 catalog records parsed.
- Parsed records matched the raw HTML table exactly: 34/34 part responses.
- Multiple OEMs and multiple production periods were preserved.
- Open-ended periods such as `06/2004-` were preserved.
- Empty table cells were preserved rather than shifting columns.

## Verified multi-OEM examples

| Part row | Records | Distinct OEMs |
|---|---:|---:|
| 09110 | 5 | 3 |
| 04111 | 15 | 8 |
| 11101 | 21 | 11 |
| 11400 | 4 | 2 |
| 11302 | 3 | 2 |

## Missing-data cases

- `9151180830` and `91511B0614`: OEM is present, but period and applicability cells are genuinely empty in the source HTML.
- `12321A` and `12322`: CatCar returns the literal response `No applicable data!`, not a table with missing fields.

These cases must remain distinguishable in the eventual data model:
1. record with complete fields;
2. record with OEM but empty period/applicability;
3. no applicable data response;
4. request or parsing error.

## Limitations

- This validates Stage A only for a bounded Toyota Camry sample.
- It does not prove universal behavior across manufacturers or catalog families.
- No mass extraction was performed.
