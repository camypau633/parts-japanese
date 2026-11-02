"""Bounded CatCar PNG/header and coordinate-system inspection.

Reads at most 64 KiB from each PNG and bounded snippets of one CatCar JS/CSS
asset. It never stores or downloads full diagram images.
"""
import argparse
import json
import posixpath
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


MAX_IMAGE_HEADER_BYTES = 65536
MAX_SCRIPT_BYTES = 262144
BASE = "https://www.catcar.info"


def normalize_image_url(source_url, image_url):
    resolved = urljoin(source_url, image_url)
    parsed = urlsplit(resolved)
    host = (parsed.hostname or "").lower()
    if host == "catcar.info" or host.endswith(".catcar.info"):
        parsed = parsed._replace(scheme="https")
    path = quote(posixpath.normpath(parsed.path), safe="/%:@")
    normalized = urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
    host = (urlsplit(normalized).hostname or "").lower()
    if urlsplit(normalized).scheme not in ("http", "https") or not (
        host == "catcar.info" or host.endswith(".catcar.info")
    ):
        raise ValueError("Non-CatCar image URL rejected")
    return normalized


def fetch_limited(url, max_bytes, timeout, byte_range=None):
    headers = {"User-Agent": "PartScope-CatCar-Geometry-Check/1.0"}
    if byte_range:
        headers["Range"] = "bytes=%d-%d" % byte_range
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(max_bytes)
            return {
                "status": response.status,
                "content_type": response.headers.get("Content-Type", ""),
                "content_range": response.headers.get("Content-Range", ""),
                "content_length": response.headers.get("Content-Length", ""),
                "body": body,
                "error": None,
            }
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        return {
            "status": error.code if isinstance(error, HTTPError) else None,
            "content_type": "",
            "content_range": "",
            "content_length": "",
            "body": b"",
            "error": str(error),
        }


def png_dimensions(data):
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        return None
    return width, height


def _integer(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def hotspot_extent(hotspots):
    boxes = []
    invalid = 0
    for hotspot in hotspots:
        top = _integer(hotspot.get("top_raw"))
        left = _integer(hotspot.get("left_raw"))
        width = _integer(hotspot.get("width_raw"))
        height = _integer(hotspot.get("height_raw"))
        if None in (top, left, width, height) or width <= 0 or height <= 0:
            invalid += 1
            continue
        boxes.append({
            "top": top,
            "left": left,
            "right": left + width,
            "bottom": top + height,
        })
    if not boxes:
        return {
            "valid_box_count": 0,
            "invalid_box_count": invalid,
            "max_right": None,
            "max_bottom": None,
        }
    return {
        "valid_box_count": len(boxes),
        "invalid_box_count": invalid,
        "max_right": max(item["right"] for item in boxes),
        "max_bottom": max(item["bottom"] for item in boxes),
    }


def _source_asset(url, max_bytes, timeout, patterns):
    result = fetch_limited(url, max_bytes, timeout)
    body = result.pop("body")
    source = body.decode("utf-8", "replace")
    snippets = []
    for pattern in patterns:
        match = re.search(pattern, source, re.I)
        if match:
            start = max(0, match.start() - 220)
            end = min(len(source), match.end() + 420)
            snippets.append(source[start:end])
    result["bytes_read"] = len(body)
    result["truncated_at_limit"] = len(body) >= max_bytes
    result["relevant_snippets"] = snippets[:8]
    return result


def inspect_documents(paths, max_urls=20, timeout=12):
    documents = []
    seen_urls = set()
    for path in paths:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        source_url = str((document.get("source") or {}).get("url") or "").strip()
        context = document.get("catalog_context") or {}
        for diagram in document.get("diagrams") or []:
            url = normalize_image_url(source_url, str(diagram.get("source_image_url") or ""))
            seen_urls.add(url)
            if len(seen_urls) > max_urls:
                raise ValueError("Diagram URL count exceeds configured limit")
            hotspots = [
                item for item in (document.get("hotspots") or [])
                if item.get("diagram_id") == diagram.get("diagram_id")
            ]
            documents.append((context.get("source_group_id"), url, hotspots))

    results = []
    for group_id, url, hotspots in documents:
        response = fetch_limited(
            url, MAX_IMAGE_HEADER_BYTES, timeout, byte_range=(0, MAX_IMAGE_HEADER_BYTES - 1)
        )
        dimensions = png_dimensions(response["body"])
        extent = hotspot_extent(hotspots)
        bounds_ok = None
        if dimensions and extent["valid_box_count"] and not extent["invalid_box_count"]:
            width, height = dimensions
            bounds_ok = extent["max_right"] <= width and extent["max_bottom"] <= height
        results.append({
            "source_group_id": group_id,
            "image_url": url,
            "http_status": response["status"],
            "content_type": response["content_type"],
            "content_range": response["content_range"],
            "image_header_bytes_read": len(response["body"]),
            "image_dimensions": {"width": dimensions[0], "height": dimensions[1]} if dimensions else None,
            "hotspot_count": len(hotspots),
            "hotspot_extent": extent,
            "all_hotspot_boxes_inside_image_bounds": bounds_ok,
            "error": response["error"],
        })

    script = _source_asset(
        BASE + "/js/jquery.resizeImageCoords.js",
        MAX_SCRIPT_BYTES,
        timeout,
        [r"srcTop", r"srcLeft", r"srcWidth", r"srcHeight", r"resize"],
    )
    css = _source_asset(
        BASE + "/css/main.css",
        MAX_SCRIPT_BYTES,
        timeout,
        [r"img_wrapper", r"\.resize", r"\.coord"],
    )
    return {
        "inspection": "bounded_catcar_diagram_geometry",
        "network_requests_max": len(results) + 2,
        "unique_diagram_urls": len(seen_urls),
        "full_images_downloaded": 0,
        "max_image_bytes_read_per_url": MAX_IMAGE_HEADER_BYTES,
        "images": results,
        "coordinate_script": script,
        "main_css": css,
        "interpretation_note": (
            "Bounds checks alone do not prove coordinate scaling. Review the captured "
            "resize script and CSS before exporting hotspot coordinates."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-urls", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=12)
    args = parser.parse_args(argv)

    report = inspect_documents(args.input, args.max_urls, args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
