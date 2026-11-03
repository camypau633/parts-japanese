# CatCar diagram watermark audit — 2026-11-03

## Scope

A bounded pixel-level review of four actual PNG diagrams already referenced by the PartScope preview dataset. This is not a full-catalog certification.

Workflow: [41593915734](https://github.com/camypau633/parts-japanese/actions/runs/41593915734)

## Sample

| Image | Make | Dimensions | Bytes |
|---|---|---:|---:|
| 118157.png | Toyota | 760 × 1112 | 16,489 |
| page_120_A_002.png | Nissan | 1024 × 555 | 14,082 |
| 090164.png | Toyota | 760 × 1112 | 11,136 |
| 113339.png | Toyota | 760 × 1112 | 9,905 |

The audit downloaded no more than four full images, capped each at 8 MiB, and waited at least 10 seconds between image requests in accordance with the published CatCar robots.txt crawl delay.

## Automated screening

Tesseract OCR was run on each full image and on five regions (four corners and center). No text patterns indicating CatCar, catcar.info, copyright overlays, or generic watermark/sample labels were detected.

OCR is not sufficient to rule out image-only logos or faint translucent marks.

## Visual inspection

All four PNGs and the generated contact sheet were visually inspected.

- No visible CatCar logo or CatCar text watermark was observed over the diagrams.
- No obvious translucent repeating overlay or diagonal watermark was observed.
- Diagram labels, OEM/position numbers, Japanese explanatory text and drawing borders are native diagram content, not watermarks.
- One Toyota drawing depicts a branded support/tool; its small Toyota marking is printed on the depicted object and is not a watermark overlay.
- The fourth image contains several empty framed panels; these are part of the supplied image and are not a watermark.

## Conclusion

**No visible CatCar watermark was found in the four inspected images.**

This conclusion applies only to the four sampled images. It does not prove that all CatCar diagrams are watermark-free, nor does it establish permission to reuse or redistribute the images. Copyright, database rights, contractual terms and reuse permissions remain separate questions. Keep mass collection and redistribution disabled until permission is clarified.
