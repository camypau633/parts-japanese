# CatCar POC — OEM temporal relationship validation

Date: 2026-11-02  
Repository: `camypau633/parts-japanese`  
Workflow: [41449404600](https://github.com/camypau633/parts-japanese/actions/runs/41449404600)  
Commit: `6a9ff87767fcf94c901ab477745f5f114341be95`

## Scope

The bounded Toyota Camry sample covers 8 groups, 34 part rows and 148 source catalog records. The period parser reads CatCar's `MM/YYYY-MM/YYYY` values and preserves the original period string.

## Results

- 128 pairwise overlaps between records with different OEM numbers, across 14 part rows.
- Of those overlap pairs, 113 have identical applicability text and 15 have different applicability text.
- 172 pairwise adjacent-period comparisons with different OEM numbers. This is a pair count, not 172 confirmed replacement links: records can have multiple alternatives in the same period, so pairwise comparisons can multiply.
- 2 source records have an OEM but no period or applicability: part rows `9151180830` and `91511B0614`.
- No explicit OEM supersession/replacement field was present in the inspected AJAX table.

## Examples

### Different OEMs in the same period and same applicability

Part row `04111` includes:
- `04111-28260`, 09/2003–06/2004, `2AZFE..ACV3#`
- `04111-28261`, 09/2003–06/2004, `2AZFE..ACV3#`

Both are listed for the same period and applicability. The source does not explain whether these represent parallel variants, alternatives, or a replacement relation. Do not collapse them or infer supersession.

Part row `09110` includes:
- `09111-06020`, 09/2001–01/2002
- `09111-0W080`, 09/2001–01/2002

Both carry applicability `ACV3#`; the source gives no additional discriminator.

### Same period, different applicability

Part row `09141` lists `99914-10810` and `99914-11214` for the same periods, but with different applicability descriptions:
- `ACV3# ８ Ｘ １０`
- `ACV3# １２ Ｘ １４`

This is direct evidence that applicability text must be preserved exactly; it distinguishes options that would be lost if records were merged by date alone.

### Chronological OEM changes

Part row `11302`:
- `11310-28070`, 09/2001–06/2004
- `11310-28070`, 06/2004–08/2005
- `11310-28071`, 09/2005–01/2006

This shows a later OEM in the catalog timeline, but the table does not explicitly state that the later OEM supersedes the earlier one.

## Importer rules established

1. Preserve every source row as a separate catalog record.
2. Preserve OEM, period and applicability exactly as returned, including blank fields and full-width characters.
3. Do not deduplicate records solely by OEM, period, or part row.
4. Do not convert adjacent OEM changes into replacement links without a separate authoritative source field.
5. Store inferred relationships separately from source facts and mark them as unverified.
6. Model multiple records for one part row as a one-to-many relationship.

## Conclusion

Stage A now demonstrates multiple OEMs, parallel records in identical periods, differing applicability variants, chronological OEM changes, open periods and incomplete source rows. CatCar's inspected table supports a complete record list, but not a reliable OEM supersession graph by itself.

This remains a bounded Toyota Camry POC. No mass extraction was performed.
