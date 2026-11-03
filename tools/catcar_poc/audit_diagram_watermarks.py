"""Bounded visual watermark audit for a small CatCar diagram sample.

Downloads at most four full PNGs, waits at least ten seconds between CatCar
image requests, runs OCR over full images and corner crops, and creates a
contact sheet for manual visual review. This does not claim that OCR can
detect image-only logos or all translucent watermarks.
"""
import hashlib
import json
import re
import subprocess
import time
import urllib.request
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlsplit

import urllib.error
from PIL import Image, ImageDraw


BASE = "https://raw.githubusercontent.com/camypau633/partscope/main/public/data-preview/catcar/"
MAX_IMAGES = 10
MAX_IMAGE_BYTES = 8 * 1024 * 1024
USER_AGENT = "PartScope-CatCar-Watermark-Audit/1.0"


def fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def collect_diagrams():
    manifest = json.loads(fetch(BASE + "manifest.json").decode("utf-8"))
    found = OrderedDict()
    for shard in manifest.get("shards", []):
        name = shard.get("file", "")
        if not re.fullmatch(r"[A-Za-z0-9]{2}\.json", name):
            continue
        payload = json.loads(fetch(BASE + name).decode("utf-8"))
        for records in payload.values():
            for record in records if isinstance(records, list) else [records]:
                diagram = record.get("diagram") or {}
                url = diagram.get("diagramUrl")
                if not url:
                    continue
                host = (urlsplit(url).hostname or "").lower()
                if host not in ("ci.catcar.info", "www.catcar.info", "catcar.info"):
                    continue
                brand = record.get("brand", "unknown")
                found.setdefault(url, {"url": url, "brands": set()})["brands"].add(brand)
    return manifest, list(found.values())


def run_ocr(path, psm):
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", str(psm)],
        check=False, capture_output=True, text=True, timeout=30
    )
    return " ".join(result.stdout.split()), result.returncode


def inspect_image(item, index, output):
    url = item["url"]
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=35) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read(MAX_IMAGE_BYTES + 1)
    if len(body) > MAX_IMAGE_BYTES:
        return {
            "url": url, "brands": sorted(item["brands"]), "status": "size_limit_exceeded",
            "max_bytes": MAX_IMAGE_BYTES, "content_type": content_type,
            "full_visual_review": "not_available"
        }
    path = output / ("diagram-%02d.png" % index)
    path.write_bytes(body)
    image = Image.open(path).convert("RGB")
    width, height = image.size
    full_text, full_rc = run_ocr(path, 11)
    corner_text = {}
    crop_specs = {
        "top_left": (0, 0, width // 3, height // 3),
        "top_right": (width * 2 // 3, 0, width, height // 3),
        "bottom_left": (0, height * 2 // 3, width // 3, height),
        "bottom_right": (width * 2 // 3, height * 2 // 3, width, height),
        "center": (width // 3, height // 3, width * 2 // 3, height * 2 // 3),
    }
    for name, bounds in crop_specs.items():
        crop = image.crop(bounds)
        crop_path = output / ("crop-%02d-%s.png" % (index, name))
        crop.save(crop_path)
        text, rc = run_ocr(crop_path, 11)
        corner_text[name] = {"text": text, "ocr_exit_code": rc}
        crop_path.unlink(missing_ok=True)

    joined = " ".join([full_text] + [x["text"] for x in corner_text.values()]).lower()
    indicators = []
    for pattern, label in [
        (r"cat\s*car|catcar\.info", "catcar_text"),
        (r"copyright|\bc\s*\d{4}|all rights reserved", "copyright_text"),
        (r"www\.[a-z0-9.-]+", "website_text"),
        (r"watermark|sample|demo", "watermark_or_sample_text"),
    ]:
        if re.search(pattern, joined, re.I):
            indicators.append(label)

    return {
        "url": url,
        "brands": sorted(item["brands"]),
        "status": "downloaded_and_ocr_checked",
        "content_type": content_type,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "dimensions": {"width": width, "height": height},
        "full_image_ocr": full_text,
        "corner_and_center_ocr": corner_text,
        "text_indicators": indicators,
        "ocr_interpretation": (
            "text_watermark_candidate" if indicators else "no_watermark_text_detected"
        ),
        "full_visual_review": "required_for_image_only_or_translucent_marks",
        "saved_image": path.name,
        "ocr_exit_code": full_rc,
    }


def main():
    output = Path("out/watermark")
    output.mkdir(parents=True, exist_ok=True)
    manifest, candidates = collect_diagrams()
    # Prefer a balanced Japanese-manufacturer sample from the currently
    # available preview; Nissan and Toyota are the only brands in this sample.
    selected = []
    for preferred in ("Toyota", "Nissan"):
        match = next((x for x in candidates if preferred in x["brands"] and x not in selected), None)
        if match:
            selected.append(match)
    for item in candidates:
        if len(selected) >= MAX_IMAGES:
            break
        if item not in selected:
            selected.append(item)
    selected = selected[:MAX_IMAGES]

    results = []
    for index, item in enumerate(selected, 1):
        if index > 1:
            time.sleep(10)  # robots.txt Crawl-delay: 10
        try:
            results.append(inspect_image(item, index, output))
        except Exception as error:
            results.append({
                "url": item["url"], "brands": sorted(item["brands"]),
                "status": "error", "error": repr(error),
                "full_visual_review": "not_available"
            })

    thumbs = []
    for result in results:
        filename = result.get("saved_image")
        if not filename:
            continue
        image = Image.open(output / filename).convert("RGB")
        image.thumbnail((640, 480))
        canvas = Image.new("RGB", (660, 520), "white")
        canvas.paste(image, ((660 - image.width) // 2, 25))
        draw = ImageDraw.Draw(canvas)
        draw.text((12, 495), "%s | %s" % (", ".join(result["brands"]), filename), fill="black")
        thumbs.append(canvas)
    if thumbs:
        sheet = Image.new("RGB", (660 * 2, 520 * ((len(thumbs) + 1) // 2)), "#dddddd")
        for i, thumb in enumerate(thumbs):
            sheet.paste(thumb, ((i % 2) * 660, (i // 2) * 520))
        sheet.save(output / "contact-sheet.jpg", quality=88)

    report = {
        "audit": "bounded_catcar_diagram_watermark_audit",
        "manifest_status": manifest.get("status"),
        "candidate_diagrams": len(candidates),
        "images_selected": len(selected),
        "max_image_bytes": MAX_IMAGE_BYTES,
        "crawl_delay_seconds": 10,
        "images": results,
        "conclusion": (
            "OCR is a screening signal only. A human must inspect the saved PNGs "
            "or contact sheet before concluding that no visual watermark is present."
        ),
    }
    (output / "watermark-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
