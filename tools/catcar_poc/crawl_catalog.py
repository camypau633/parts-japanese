"""Bounded CatCar Honda catalog crawler.

The crawler discovers navigation links itself, respects a minimum delay between
requests, and normalizes only pages accepted by HondaAdapter. It never publishes
records to PartScope. Unrecognized pages are recorded for adapter work.
"""
import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections import deque
from html.parser import HTMLParser
from pathlib import Path

import jsonschema
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit
import base64

from .adapters import HondaAdapter
from .normalize import normalize_page


USER_AGENT = "PartScope-Japanese-Catalog-Importer/0.1 (+catalog research)"
MAX_PAGE_BYTES = 4 * 1024 * 1024


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self._anchor = None
        self.title_parts = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = {key.lower(): (value or "") for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "a" and attrs.get("href"):
            self._anchor = {"href": attrs["href"], "text": ""}
            self.links.append(self._anchor)

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self._anchor is not None:
            self._anchor["text"] += data

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "a":
            self._anchor = None


def canonical_url(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path,
                       parts.query, ""))


def allowed_catalog_url(url, make):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    prefix = "/" + make.lower().strip("/") + "/"
    return (
        parts.scheme in ("http", "https")
        and (host == "catcar.info" or host.endswith(".catcar.info"))
        and parts.path.lower().startswith(prefix)
    )


def decoded_filter(url):
    encoded = parse_qs(urlsplit(url).query).get("l", [""])[0]
    if not encoded:
        return {}
    encoded += "=" * (-len(encoded) % 4)
    try:
        decoded = base64.b64decode(encoded).decode("utf-8", "replace")
    except (ValueError, TypeError):
        return {}
    result = {}
    for segment in decoded.split("||"):
        if "==" in segment:
            key, value = segment.split("==", 1)
            result[key.strip()] = value.strip()
    return result


def discover_links(html, page_url, make):
    parser = LinkCollector()
    parser.feed(html)
    found = []
    seen = set()
    for item in parser.links:
        target = canonical_url(urljoin(page_url, item["href"]))
        if not allowed_catalog_url(target, make) or target in seen:
            continue
        seen.add(target)
        found.append({
            "url": target,
            "label": " ".join(item["text"].split())[:240],
        })
    return " ".join(" ".join(parser.title_parts).split()), found


def fetch_page(url, timeout):
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(MAX_PAGE_BYTES + 1)
        if len(body) > MAX_PAGE_BYTES:
            raise ValueError("page_exceeds_4_mib_limit")
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type.lower():
            raise ValueError("unexpected_content_type:" + content_type)
        return response.status, response.geturl(), body.decode("utf-8", "replace")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def crawl(start_url, output_dir, max_pages=100, delay=10.0, timeout=30,
          make="honda", resume_state=None):
    if delay < 10:
        raise ValueError("delay must be at least 10 seconds")
    if not allowed_catalog_url(start_url, make):
        raise ValueError("start_url is outside the selected CatCar make path")

    output_dir = Path(output_dir)
    detail_dir = output_dir / "normalized"
    review_dir = output_dir / "review"
    detail_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)

    if resume_state:
        state = json.loads(Path(resume_state).read_text(encoding="utf-8"))
        if state.get("make", "").lower() != make.lower():
            raise ValueError("resume state belongs to a different make")
        if canonical_url(state.get("start_url", "")) != canonical_url(start_url):
            raise ValueError("resume state belongs to a different start URL")
        queue = deque(state.get("queue") or [])
        visited = set(state.get("visited") or [])
        details = int(state.get("detail_pages", 0))
        previous_errors = int(state.get("errors", 0))
    else:
        queue = deque([{"url": canonical_url(start_url), "label": "start"}])
        visited = set()
        details = 0
        previous_errors = 0
    queued = {item["url"] for item in queue} | visited
    errors = []
    page_records = []
    pages_this_run = 0
    adapter = HondaAdapter()
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "catcar-extraction-v0.1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    last_request_at = None

    while queue and pages_this_run < max_pages:
        item = queue.popleft()
        url = item["url"]
        if url in visited:
            continue
        if last_request_at is not None:
            wait = delay - (time.monotonic() - last_request_at)
            if wait > 0:
                time.sleep(wait)
        last_request_at = time.monotonic()
        visited.add(url)
        pages_this_run += 1

        record = {
            "url": url,
            "discovered_as": item.get("label", ""),
            "status": "unknown",
        }
        try:
            status, final_url, html = fetch_page(url, timeout)
            final_url = canonical_url(final_url)
            if not allowed_catalog_url(final_url, make):
                raise ValueError("redirect_left_selected_make_path")
            title, links = discover_links(html, final_url, make)
            record.update({
                "http_status": status,
                "final_url": final_url,
                "title": title,
                "discovered_links": len(links),
            })
            for link in links:
                if link["url"] not in queued and link["url"] not in visited:
                    queue.append(link)
                    queued.add(link["url"])

            try:
                parsed = adapter.parse(html)
            except ValueError as exc:
                record["status"] = "navigation_or_unrecognized"
                record["adapter_message"] = str(exc)
                if not links:
                    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
                    (review_dir / (digest + ".html")).write_text(
                        html, encoding="utf-8"
                    )
            else:
                context = {
                    "brand": "Honda",
                    "catalog_filter_raw": decoded_filter(final_url),
                    "source_page_label": item.get("label", ""),
                    "source_page_title": title,
                }
                document = normalize_page(parsed, context, final_url)
                jsonschema.validate(instance=document, schema=schema)
                if parsed.get("page_status") == "incomplete":
                    record["status"] = "incomplete_detail"
                    record["warnings"] = parsed.get("page_warnings", [])
                    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
                    (review_dir / (digest + ".html")).write_text(
                        html, encoding="utf-8"
                    )
                elif not parsed.get("parts"):
                    record["status"] = "unrecognized_table"
                else:
                    record["status"] = "detail_page"
                    details += 1
                    digest = hashlib.sha256(final_url.encode("utf-8")).hexdigest()[:16]
                    write_json(detail_dir / (digest + ".json"), document)
                    record["part_rows"] = len(document["parts"])
                    record["diagram_count"] = len(document["diagrams"])
                    record["hotspot_count"] = len(document["hotspots"])
        except jsonschema.ValidationError as exc:
            record["status"] = "schema_validation_error"
            record["error"] = str(exc.message)[:500]
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            if "html" in locals():
                (review_dir / (digest + ".html")).write_text(html, encoding="utf-8")
            errors.append({"url": url, "error": record["error"]})
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            record["status"] = "fetch_error"
            record["error"] = str(exc)[:500]
            errors.append({"url": url, "error": str(exc)[:500]})

        page_records.append(record)
        write_json(output_dir / "crawl-state.json", {
            "make": make.title(),
            "start_url": start_url,
            "max_pages": max_pages,
            "minimum_delay_seconds": delay,
            "pages_visited": len(visited),
            "queue_remaining": len(queue),
            "detail_pages": details,
            "errors": previous_errors + len(errors),
            "queue": list(queue),
            "visited": sorted(visited),
        })
        with (output_dir / "pages.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    report = {
        "crawler": "catcar_honda_bounded_v1",
        "make": make.title(),
        "start_url": start_url,
        "pages_visited": len(visited),
        "detail_pages_normalized": details,
        "navigation_or_unrecognized_pages": sum(
            item["status"] == "navigation_or_unrecognized" for item in page_records
        ),
        "incomplete_detail_pages": sum(
            item["status"] == "incomplete_detail" for item in page_records
        ),
        "fetch_errors": previous_errors + len(errors),
        "queue_remaining": len(queue),
        "complete": not queue,
        "errors": errors,
    }
    write_json(output_dir / "crawl-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bounded CatCar Honda catalog crawler")
    parser.add_argument("--start-url", default="https://www.catcar.info/honda/")
    parser.add_argument("--output", type=Path, default=Path("out/catcar-honda"))
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--resume-state", type=Path, help="Previously downloaded crawl-state.json")
    args = parser.parse_args(argv)
    if args.max_pages < 1 or args.max_pages > 2000:
        parser.error("--max-pages must be between 1 and 2000")
    crawl(args.start_url, args.output, args.max_pages, args.delay, args.timeout,\n          resume_state=args.resume_state)


if __name__ == "__main__":
    main()
