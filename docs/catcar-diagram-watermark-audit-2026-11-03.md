# CatCar diagram watermark audit — 2026-11-03

## Scope

A bounded pixel-level review of all 10 unique PNG diagrams currently referenced by the PartScope CatCar preview dataset. This is not a full-catalog certification.

Workflow: [41594201226](https://github.com/camypau633/parts-japanese/actions/runs/41594201226)

## Sample

| Image | Make | Dimensions | Bytes |
|---|---|---:|---:|
| 118157.png | Toyota | 760 × 1112 | 16,489 |
| page_120_A_002.png | Nissan | 1024 × 555 | 14,082 |
| 090164.png | Toyota | 760 × 1112 | 11,136 |
| 113339.png | Toyota | 760 × 1112 | 9,905 |
| 112181B.png | Toyota | 760 × 1112 | 25,911 |
| 113084D.png | Toyota | 760 × 1112 | 16,312 |
| 113647H.png | Toyota | 1592 × 1099 | 45,788 |
| 112186A.png | Toyota | 760 × 1112 | 16,594 |
| 113338.png | Toyota | 760 × 1112 | 9,163 |
| 150397.png | Toyota | 760 × 1112 | 4,727 |

The audit downloaded all 10 unique images, capped each at 8 MiB, and waited at least 10 seconds between image requests in accordance with the published CatCar robots.txt crawl delay.

## Automated screening

Tesseract OCR was run on each full image and on five regions (four corners and center). No CatCar, catcar.info, or explicit copyright/watermark/sample overlay was found.

The first OCR rule flagged one image because it misread a native diagram reference note containing a PNC/figure reference as a copyright pattern. Full-resolution visual inspection confirmed that this is ordinary printed diagram text, not a watermark. The overly broad OCR pattern has been removed from the audit script to avoid this false positive.

OCR alone is not sufficient to rule out image-only logos or faint translucent marks.

## Visual inspection

All 10 full-resolution PNGs and the generated contact sheet were visually inspected.

- No visible CatCar logo or CatCar text watermark was observed over any of the 10 diagrams.
- No obvious translucent repeating overlay or diagonal watermark was observed.
- Diagram labels, OEM/position numbers, Japanese explanatory text, cross-references and drawing borders are native diagram content, not watermarks.
- One Toyota drawing depicts a branded support/tool; its small Toyota marking is printed on the depicted object and is not a watermark overlay.
- Some images contain empty framed panels; these are part of the source image and are not watermarks.

## Conclusion

**No visible CatCar watermark was found in all 10 diagrams currently present in the PartScope preview dataset.**

This conclusion is limited to those 10 images. It does not prove that all CatCar diagrams are watermark-free, nor does it establish permission to reuse or redistribute the images. Copyright, database rights, contractual terms and reuse permissions remain separate questions. Keep mass collection and redistribution disabled until permission is clarified.
