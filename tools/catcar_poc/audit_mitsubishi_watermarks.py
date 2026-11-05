"""Visual watermark screening for three real Mitsubishi CatCar diagrams."""
import hashlib
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

SAMPLES = [
    ("rocker-cover", "http://ci.catcar.info/mitsubishi_2017_05/euro/111/111_110500135T.png"),
    ("cylinder-head", "http://ci.catcar.info/mitsubishi_2017_05/euro/111/111_120500036T.png"),
    ("piston-crankshaft", "http://ci.catcar.info/mitsubishi_2017_05/euro/111/111_210F00078T.png"),
]
MAX_IMAGE_BYTES = 8 * 1024 * 1024
USER_AGENT = "PartScope-CatCar-Mitsubishi-Watermark-Audit/1.0"


def ocr(path):
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", "11"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    return " ".join(result.stdout.split())


def main():
    output = Path("out/mitsubishi-watermark")
    output.mkdir(parents=True, exist_ok=True)
    results = []
    thumbs = []
    for index, (label, url) in enumerate(SAMPLES, 1):
        if index > 1:
            time.sleep(10)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=40) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read(MAX_IMAGE_BYTES + 1)
        if len(body) > MAX_IMAGE_BYTES:
            results.append({"label": label, "url": url, "status": "size_limit_exceeded"})
            continue
        path = output / (label + ".png")
        path.write_bytes(body)
        image = Image.open(path).convert("RGB")
        width, height = image.size
        full_text = ocr(path)
        crops = {}
        for name, bounds in {
            "top_left": (0, 0, width // 3, height // 3),
            "top_right": (width * 2 // 3, 0, width, height // 3),
            "bottom_left": (0, height * 2 // 3, width // 3, height),
            "bottom_right": (width * 2 // 3, height * 2 // 3, width, height),
            "center": (width // 3, height // 3, width * 2 // 3, height * 2 // 3),
        }.items():
            crop_path = output / (label + "-" + name + ".png")
            image.crop(bounds).save(crop_path)
            crops[name] = ocr(crop_path)
            crop_path.unlink(missing_ok=True)
        joined = " ".join([full_text] + list(crops.values())).lower()
        indicators = []
        for pattern, name in [
            (r"cat\\s*car|catcar\\.info", "catcar_text"),
            (r"copyright|all rights reserved", "copyright_text"),
            (r"www\\.[a-z0-9.-]+", "website_text"),
            (r"watermark|sample|demo", "watermark_or_sample_text"),
        ]:
            if re.search(pattern, joined, re.I):
                indicators.append(name)
        results.append({
            "label": label, "url": url, "status": "downloaded_and_ocr_checked",
            "content_type": content_type, "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "dimensions": {"width": width, "height": height},
            "full_image_ocr": full_text, "corner_and_center_ocr": crops,
            "text_indicators": indicators,
            "ocr_interpretation": "text_watermark_candidate" if indicators else "no_watermark_text_detected",
            "visual_review_required": True, "saved_image": path.name,
        })
        thumb = image.copy()
        thumb.thumbnail((720, 540))
        canvas = Image.new("RGB", (740, 590), "white")
        canvas.paste(thumb, ((740 - thumb.width) // 2, 12))
        ImageDraw.Draw(canvas).text((12, 565), label + " | " + path.name, fill="black")
        thumbs.append(canvas)
    if thumbs:
        sheet = Image.new("RGB", (740, 590 * len(thumbs)), "#dddddd")
        for i, thumb in enumerate(thumbs):
            sheet.paste(thumb, (0, 590 * i))
        sheet.save(output / "contact-sheet.jpg", quality=90)
    report = {
        "audit": "bounded_mitsubishi_catcar_watermark_screening",
        "sample_count": len(SAMPLES), "crawl_delay_seconds": 10,
        "max_image_bytes": MAX_IMAGE_BYTES, "images": results,
        "conclusion": "OCR is only a screening signal; manually inspect saved PNGs/contact sheet for logos and translucent marks.",
    }
    (output / "watermark-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
