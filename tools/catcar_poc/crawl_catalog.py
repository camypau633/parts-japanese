"""Bounded CatCar crawler for the supported Japanese vehicle makes.

The crawler discovers navigation links, respects a minimum request delay, and
normalizes pages through the selected make adapter. It never publishes records
to PartScope. Unrecognized pages are retained for adapter review.
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
from urllib.parse import parse_qs, quote, urljoin, urlsplit, urlunsplit
import base64

from .adapters import DiscoveryOnlyAdapter, HondaAdapter, MazdaAdapter, NissanAdapter, SubaruAdapter, SuzukiAdapter, ToyotaAdapter, detail_page_validation
from .catalog_registry import CATCAR_JAPANESE_CATALOGS, catalog_config
from .normalize import normalize_page
from .parser import parse_html, cell_texts


USER_AGENT = "PartScope-Japanese-Catalog-Importer/0.1 (+catalog research)"
MAX_PAGE_BYTES = 4 * 1024 * 1024
ADAPTER_IMPLEMENTATIONS = {
    "honda": HondaAdapter,
    "mazda": MazdaAdapter,
    "nissan": NissanAdapter,
    "toyota": ToyotaAdapter,
    "subaru": SubaruAdapter,
    "suzuki": SuzukiAdapter,
}
# The registry is the single source of truth for catalog roots. A missing
# implementation deliberately falls back to discovery-only mode.
ADAPTERS = {
    make: ADAPTER_IMPLEMENTATIONS.get(config["detail_adapter"], DiscoveryOnlyAdapter)
    for make, config in CATCAR_JAPANESE_CATALOGS.items()
}


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


def navigation_stage(url):
    """Return CatCar's explicit stage number for depth-first selector traversal."""
    stage = decoded_filter(url).get("st")
    if stage is None:
        stage = parse_qs(urlsplit(url).query).get("st", [""])[0]
    try:
        return int(stage)
    except (TypeError, ValueError):
        return -1


MARKET_LABELS = {
    "euro": "Europe",
    "europe": "Europe",
    "eu": "Europe",
    "japan": "Japan",
    "jpn": "Japan",
    "jdm": "Japan",
    "asia": "Asia",
    "asian": "Asia",
    "asia-pacific": "Asia-Pacific",
    "asiapacific": "Asia-Pacific",
    "africa": "Africa",
    "canada": "Canada",
    "ca": "Canada",
    "caribbean": "Caribbean",
    "latin-america": "Latin America",
    "latinamerica": "Latin America",
    "middle-east": "Middle East",
    "middleeast": "Middle East",
    "pacific": "Pacific",
    "russia": "Russia",
    "usa": "United States",
    "us": "United States",
    "america": "United States",
    "united-states": "United States",
    "канада": "Canada",
    "сша": "United States",
    "япония": "Japan",
    "европа": "Europe",
    "европа (левый руль)": "Europe (LHD)",
    "европа (правый руль)": "Europe (RHD)",
    "europe (lhd)": "Europe (LHD)",
    "europe (rhd)": "Europe (RHD)",
    "lhd": "Europe (LHD)",
    "rhd": "Europe (RHD)",
    "general": "Middle East",
    "gen": "Middle East",
    "el": "Europe (LHD)",
    "er": "Europe (RHD)",
    "gl": "Asia (LHD)",
    "gr": "Asia (RHD)",
    "jp": "Japan",
    "us": "United States",
    "cainf": "Canada",
    "elinf": "Europe (LHD)",
    "erinf": "Europe (RHD)",
    "usinf": "United States",
    "европа леворульные": "Europe (LHD)",
    "европа праворульные": "Europe (RHD)",
    "азия леворульные": "Asia (LHD)",
    "азия праворульные": "Asia (RHD)",
    "europe lhd": "Europe (LHD)",
    "europe rhd": "Europe (RHD)",
    "asia lhd": "Asia (LHD)",
    "asia rhd": "Asia (RHD)",
    "северная америка": "North America",
    "north america": "North America",
    "ближний восток": "Middle East",
    "азия": "Asia",
    "африка": "Africa",
    "россия": "Russia",
    "латинская америка": "Latin America",
    "карибы": "Caribbean",
    "тихий океан": "Pacific",
}
# Suzuki exposes numeric marketId values in its own region selector. These
# mappings are based on the labels linked from the CatCar Suzuki root page.
SUZUKI_MARKET_ID_LABELS = {
    "1": "Africa",
    "2": "Asia",
    "3": "Canada",
    "4": "Caribbean",
    "5": "Europe",
    "6": "Latin America",
    "7": "Middle East",
    "8": "Pacific",
    "9": "Russia",
    "10": "United States",
}


def market_context(adapter_result, source_url, page_title=None):
    """Extract only explicit market markers; never infer a market from model names."""
    decoded = decoded_filter(source_url)
    try:
        selector_labels = json.loads(decoded.get("sts", "{}") or "{}")
    except (TypeError, ValueError):
        selector_labels = {}
    selector_market = (
        str(selector_labels.get("20", "")).strip().lower()
        if isinstance(selector_labels, dict) else ""
    )
    filter_codes = [
        str(value).strip().lower()
        for key, value in decoded.items()
        if key.lower() in ("market", "region", "country", "sales_region", "catalog_region")
    ]
    market_candidates = ([selector_market] if selector_market else []) + filter_codes
    market_id = str(decoded.get("marketId", "")).strip()
    if market_id in SUZUKI_MARKET_ID_LABELS:
        return {"market_region": SUZUKI_MARKET_ID_LABELS[market_id],
                "market_code_raw": "marketId=" + market_id}

    path_candidates = []
    urls = [source_url]
    urls.extend(image.get("src", "") for image in adapter_result.get("images", [])
                if image.get("src"))
    for candidate_url in urls:
        segments = [segment.lower() for segment in urlsplit(candidate_url).path.split("/")
                    if segment]
        if len(segments) >= 2:
            path_candidates.append(segments[1])

    for candidate in market_candidates + path_candidates:
        if candidate in MARKET_LABELS:
            raw_code = filter_codes[0] if filter_codes else candidate
            return {"market_region": MARKET_LABELS[candidate],
                    "market_code_raw": raw_code}

    title_key = " ".join((page_title or "").strip().lower().split())
    suffix = " - catcar.info"
    if title_key.endswith(suffix):
        title_key = title_key[:-len(suffix)]
    if title_key in MARKET_LABELS:
        raw_code = filter_codes[0] if filter_codes else title_key
        return {"market_region": MARKET_LABELS[title_key],
                "market_code_raw": raw_code}

    raw_code = filter_codes[0] if filter_codes else (path_candidates[0] if path_candidates else None)
    return {"market_region": None, "market_code_raw": raw_code}

def toyota_variant_context(filter_values, resolved_brand=None):
    """Preserve Toyota/Lexus model and variant selectors exactly as CatCar exposes them."""
    try:
        selector = json.loads(filter_values.get("sts", "{}") or "{}")
    except (TypeError, ValueError):
        selector = {}
    if not isinstance(selector, dict):
        selector = {}

    values = {
        "catalog_id": "catalog",
        "modification_name": "modifname",
        "engine_code": "engine",
        "model_code": "modelno",
        "production_period_code_raw": "ProdPeriod",
        "source_group_id": "group_id",
        "series_name_raw": None,
        "group_label_raw": None,
        "model_label_raw": None,
        "catalog_region_label_raw": None,
        "catalog_market_label_raw": None,
    }
    result = {}
    for target, source in values.items():
        raw = filter_values.get(source) if source else None
        if target == "series_name_raw":
            raw = selector.get("60")
        elif target == "group_label_raw":
            raw = selector.get("70")
        elif target == "model_label_raw":
            raw = selector.get("30")
        elif target == "catalog_region_label_raw":
            raw = selector.get("10")
        elif target == "catalog_market_label_raw":
            raw = selector.get("20")
        if raw is not None and str(raw).strip():
            result[target] = str(raw).strip()

    model_label = result.get("model_label_raw")
    if model_label:
        model_name = model_label
        catalog_id = result.get("catalog_id")
        if catalog_id and model_name.endswith(" " + catalog_id):
            model_name = model_name[:-(len(catalog_id) + 1)].strip()
        if resolved_brand and model_name.casefold().startswith(resolved_brand.casefold() + " "):
            model_name = model_name[len(resolved_brand):].strip()
        result["model_name"] = model_name
    return result


def explicit_brand_context(make, filter_values):
    """Resolve shared-root brands only from an explicit CatCar brand/model label."""
    candidates = catalog_config(make)["brands"]
    if len(candidates) == 1:
        return {"brand": candidates[0], "brand_candidates": candidates}

    matches = []
    evidence = []
    explicit_keys = ("brand", "brand_name", "make", "manufacturer", "marque")
    for key in explicit_keys:
        value = str(filter_values.get(key, "") or "").strip()
        if not value:
            continue
        folded = value.casefold()
        for brand in candidates:
            prefix = brand.casefold()
            if folded == prefix or folded.startswith(prefix + " "):
                matches.append(brand)
                evidence.append((key, value))

    # CatCar's model selector is carried as JSON in the explicit "sts" filter.
    # Only a model label beginning with a complete brand name is authoritative;
    # combined labels such as "TOYOTA/LEXUS" remain unresolved.
    try:
        selector = json.loads(filter_values.get("sts", "{}") or "{}")
    except (TypeError, ValueError):
        selector = {}
    if isinstance(selector, dict):
        for key, raw_value in selector.items():
            value = str(raw_value or "").strip()
            folded = value.casefold()
            for brand in candidates:
                prefix = brand.casefold()
                if folded == prefix or folded.startswith(prefix + " "):
                    matches.append(brand)
                    evidence.append(("sts." + str(key), value))

    unique = sorted(set(matches))
    if len(unique) == 1:
        field, value = evidence[0]
        return {
            "brand": unique[0],
            "brand_candidates": candidates,
            "brand_source_field": field,
            "brand_source_value": value,
        }
    return {"brand": None, "brand_candidates": candidates}

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


def build_toyota_ajax_url(token):
    """Build the exact GET URL used by CatCar's observed getArticles() function."""
    # getArticles() concatenates the already URL-encoded token directly
    # into the query string. CatCar tokens commonly end in %3D; quoting them
    # again would turn %3D into %253D and change the lookup key.
    if not token or not re.fullmatch(r"(?:[A-Za-z0-9_+/=-]|%[0-9A-Fa-f]{2})+", token):
        raise ValueError("invalid_toyota_ajax_token")
    return "https://www.catcar.info/toyota/?l={}&st=81".format(token)


def fetch_toyota_ajax_page(url, timeout):
    """Fetch one Toyota row expansion; CatCar returns an HTML table fragment."""
    if not allowed_catalog_url(url, "toyota"):
        raise ValueError("toyota_ajax_url_outside_catalog_path")
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    })
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read(MAX_PAGE_BYTES + 1)
                if len(body) > MAX_PAGE_BYTES:
                    raise ValueError("toyota_ajax_response_exceeds_4_mib_limit")
                content_type = response.headers.get("Content-Type", "")
                if "html" not in content_type.lower():
                    raise ValueError("unexpected_toyota_ajax_content_type:" + content_type)
                return response.status, response.geturl(), body.decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == 2:
                raise
        time.sleep(2 * (attempt + 1))
    raise last_error


def resolve_toyota_ajax_rows(parsed, group_url, output_dir, timeout,
                             request_delay=1.0):
    """Resolve each Toyota getArticles row and retain the exact OEM source response."""
    ajax_rows = parsed.get("ajax_rows") or []
    if not ajax_rows:
        return [], []

    raw_dir = Path(output_dir) / "ajax_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    oem_records = []
    errors = []
    group_id = decoded_filter(group_url).get("group_id")
    requests_made = 0
    for index, part in enumerate(ajax_rows):
        token = part.get("ajax_token", "")
        try:
            ajax_url = build_toyota_ajax_url(token)
            # Group IDs such as 1103 repeat across different Toyota models,
            # markets and modifications. Cache identity must include the full
            # source URL, not only the local group ID.
            digest = hashlib.sha256(
                (canonical_url(group_url) + "|" + str(part.get("source_row_id") or "")).encode("utf-8")
            ).hexdigest()[:16]
            raw_path = raw_dir / (digest + ".html")
            if raw_path.is_file():
                body = raw_path.read_text(encoding="utf-8", errors="replace")
                final_url = ajax_url
            else:
                if requests_made:
                    time.sleep(request_delay)
                status, final_url, body = fetch_toyota_ajax_page(ajax_url, timeout)
                requests_made += 1
                if status != 200:
                    raise ValueError("toyota_ajax_http_status:%s" % status)
                raw_path.write_text(body, encoding="utf-8")
            records = ToyotaAdapter.parse_ajax_records(
                body, source_row_id=part.get("source_row_id")
            )
            if not records:
                if raw_path.exists():
                    raw_path.rename(raw_path.with_suffix(".unclassified.html"))
                raise ValueError("toyota_ajax_empty_unclassified")
            status_value = records[0].get("source_status", "available")
            part["source_status"] = (
                "no_applicable_data" if status_value == "no_applicable_data"
                else "requires_ajax"
            )
            part.setdefault("additional_source_fields", {}).update({
                "ajax_resolution_status": status_value,
                "ajax_url": final_url,
                "ajax_response_file": str(raw_path.relative_to(Path(output_dir))),
                "ajax_record_count": 0 if status_value == "no_applicable_data" else len(records),
            })
            for order, record in enumerate(records):
                record.update({
                    "source_record_order": order if status_value == "available" else None,
                    "source_group_id": group_id,
                    "source_url": final_url,
                })
                oem_records.append(record)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            part["source_status"] = "requires_ajax"
            part.setdefault("additional_source_fields", {}).update({
                "ajax_resolution_status": "error",
                "ajax_error": str(exc)[:300],
            })
            errors.append({
                "source_row_id": part.get("source_row_id"),
                "error": str(exc)[:300],
            })
    return oem_records, errors


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def catalog_navigation_reason(make, url, html, links):
    """Recognize CatCar market/year/model selectors before detail parsing."""
    make = make.lower()
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    parsed = parse_html(html)
    has_diagram = any(image.get("image_kind") == "diagram" for image in parsed.images)
    if has_diagram:
        return None

    if parts.path.rstrip("/") == "/" + make and not query.get("l") and links:
        return "catalog_root_selector"

    filters = [decoded_filter(link.get("url", "")) for link in links]
    # Model rows advance to stage 30; identifier names differ between makes.
    if any(values.get("st") == "30" for values in filters):
        return "model_selector"

    # Honda first selects a production year (stage 20) before listing models.
    if make == "honda" and any(values.get("year") for values in filters):
        return "honda_year_selector"

    if make == "nissan":
        header_sets = (
            {"модель", "дата производства", "серия"},
            {"model", "production date", "series"},
        )
        for row in parsed.rows:
            cells = {" ".join(value.strip().lower().split())
                     for value in cell_texts(row)}
            if any(required.issubset(cells) for required in header_sets):
                return "nissan_model_selector"

    # Mazda's market pages expose model rows at stage 60, not stage 30.
    # Identify the selector by its observed table headings so it is never
    # passed to the Mazda parts-table adapter as if it were a detail page.
    if make == "mazda":
        header_sets = (
            {"год", "модель", "дата начала производства", "кузов", "каталог"},
            {"year", "model", "production start date", "body", "catalog"},
            {"year", "model", "production date", "car line", "catalog"},
            {"код", "номер", "название"},
            {"code", "number", "name"},
        )
        for row in parsed.rows:
            cells = {" ".join(value.strip().lower().split())
                     for value in cell_texts(row)}
            if any(required.issubset(cells) for required in header_sets):
                return "mazda_model_selector"
    return None

def crawl(start_url, output_dir, max_pages=100, delay=10.0, timeout=30,
          make="honda", resume_state=None):
    make = make.lower()
    if make not in ADAPTERS:
        raise ValueError("make must be one of: " + ", ".join(sorted(ADAPTERS)))
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
        failed_urls = list(state.get("failed_urls") or [])
        queued_urls = {item["url"] for item in queue}
        for failed_url in failed_urls:
            if failed_url not in queued_urls:
                queue.append({"url": failed_url, "label": "retry_after_previous_error"})
        visited = set(state.get("visited") or []) - set(failed_urls)
        details = int(state.get("detail_pages", 0))
        previous_errors = int(state.get("errors", 0))
    else:
        queue = deque([{"url": canonical_url(start_url), "label": "start"}])
        visited = set()
        failed_urls = []
        details = 0
        previous_errors = 0
    # Prefer deeper CatCar selector stages over hundreds of sibling model links.
    # Stable sorting preserves source order within the same stage.
    queue = deque(sorted(queue, key=lambda item: navigation_stage(item["url"]), reverse=True))
    queued = {item["url"] for item in queue} | visited
    errors = []
    page_log = output_dir / "pages.jsonl"
    page_records = []
    if page_log.exists():
        for line in page_log.read_text(encoding="utf-8").splitlines():
            try:
                page_records.append(json.loads(line))
            except ValueError:
                continue
    pages_this_run = 0
    adapter = ADAPTERS[make]()
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
        html = None
        try:
            status, final_url, html = fetch_page(url, timeout)
            final_url = canonical_url(final_url)
            failed_urls = [failed_url for failed_url in failed_urls if failed_url != url]
            if not allowed_catalog_url(final_url, make):
                raise ValueError("redirect_left_selected_make_path")
            title, links = discover_links(html, final_url, make)
            page_market = market_context(
                {"images": parse_html(html).images}, final_url, page_title=title
            )
            record.update({
                "http_status": status,
                "final_url": final_url,
                "title": title,
                "discovered_links": len(links),
                "market_region": page_market["market_region"],
                "market_code_raw": page_market["market_code_raw"],
            })
            for link in links:
                if link["url"] not in queued and link["url"] not in visited:
                    queue.append(link)
                    queued.add(link["url"])
            if links:
                queue = deque(sorted(
                    queue,
                    key=lambda queued_item: navigation_stage(queued_item["url"]),
                    reverse=True,
                ))

            try:
                navigation_reason = catalog_navigation_reason(make, final_url, html, links)
                if navigation_reason:
                    raise ValueError("catalog_navigation_page: " + navigation_reason)
                parsed = adapter.parse(html)
                oem_records = []
                ajax_errors = []
                if make == "toyota" and parsed.get("ajax_rows"):
                    oem_records, ajax_errors = resolve_toyota_ajax_rows(
                        parsed, final_url, output_dir, timeout
                    )
                    if ajax_errors:
                        failed_urls.append(url)
                        errors.append({"url": url, "error": "toyota_ajax_request_failed"})
                    validation = detail_page_validation(parse_html(html), parsed.get("parts", []))
                    warnings = list(validation.get("page_warnings", []))
                    if ajax_errors:
                        warnings.append("toyota_ajax_request_failed")
                    parsed["page_status"] = (
                        "complete" if validation["page_status"] == "complete" and not ajax_errors
                        else "incomplete"
                    )
                    parsed["page_warnings"] = warnings
            except ValueError as exc:
                record["status"] = "navigation_or_unrecognized"
                record["adapter_message"] = str(exc)
                digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
                (review_dir / (digest + ".html")).write_text(
                    html, encoding="utf-8"
                )
            else:
                filter_values = decoded_filter(final_url)
                brand_context = explicit_brand_context(make, filter_values)
                context = {
                    **brand_context,
                    **(toyota_variant_context(filter_values, brand_context.get("brand")) if make == "toyota" else {}),
                    "manufacturer_country": "Japan",
                    **page_market,
                    "catalog_filter_raw": filter_values,
                    "source_page_label": item.get("label", ""),
                    "source_page_title": title,
                }
                document = normalize_page(parsed, context, final_url, oem_records=oem_records)
                jsonschema.validate(instance=document, schema=schema)
                if parsed.get("page_status") == "incomplete":
                    record["status"] = "incomplete_detail"
                    record["warnings"] = parsed.get("page_warnings", [])
                    record["part_rows"] = len(document["parts"])
                    record["diagram_count"] = len(document["diagrams"])
                    record["hotspot_count"] = len(document["hotspots"])
                    record["ajax_rows_requiring_lookup"] = sum(
                        part.get("additional_source_fields", {}).get("ajax_resolution_status") in (None, "error")
                        for part in document["parts"]
                    )
                    record["ajax_rows_resolved"] = sum(
                        part.get("additional_source_fields", {}).get("ajax_resolution_status") == "available"
                        for part in document["parts"]
                    )
                    record["ajax_rows_no_applicable_data"] = sum(
                        part.get("source_status") == "no_applicable_data"
                        for part in document["parts"]
                    )
                    if ajax_errors:
                        record["ajax_errors"] = ajax_errors
                    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
                    (review_dir / (digest + ".html")).write_text(
                        html, encoding="utf-8"
                    )
                    write_json(review_dir / (digest + ".json"), document)
                elif not parsed.get("parts"):
                    record["status"] = "unrecognized_table"
                    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
                    (review_dir / (digest + ".html")).write_text(html, encoding="utf-8")
                else:
                    record["status"] = "detail_page"
                    details += 1
                    digest = hashlib.sha256(final_url.encode("utf-8")).hexdigest()[:16]
                    write_json(detail_dir / (digest + ".json"), document)
                    record["part_rows"] = len(document["parts"])
                    record["diagram_count"] = len(document["diagrams"])
                    record["hotspot_count"] = len(document["hotspots"])
                    record["ajax_rows_requiring_lookup"] = sum(
                        part.get("additional_source_fields", {}).get("ajax_resolution_status") in (None, "error")
                        for part in document["parts"]
                    )
                    record["ajax_rows_resolved"] = sum(
                        part.get("additional_source_fields", {}).get("ajax_resolution_status") == "available"
                        for part in document["parts"]
                    )
                    record["ajax_rows_no_applicable_data"] = sum(
                        part.get("source_status") == "no_applicable_data"
                        for part in document["parts"]
                    )
                    if ajax_errors:
                        record["ajax_errors"] = ajax_errors
        except jsonschema.ValidationError as exc:
            failed_urls.append(url)
            record["status"] = "schema_validation_error"
            record["error"] = str(exc.message)[:500]
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            if html is not None:
                (review_dir / (digest + ".html")).write_text(html, encoding="utf-8")
            errors.append({"url": url, "error": record["error"]})
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            failed_urls.append(url)
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
            "failed_urls": sorted(set(failed_urls)),
        })
        with (output_dir / "pages.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    # A failed page can appear more than once after a resume/retry. Report
    # the latest outcome per canonical URL so market coverage and status
    # counters represent pages, not request attempts.
    latest_by_url = {}
    for item in page_records:
        latest_by_url[item.get("url") or item.get("final_url")] = item
    unique_page_records = list(latest_by_url.values())

    market_coverage = {}
    for item in unique_page_records:
        region = item.get("market_region") or "Unspecified"
        market_coverage[region] = market_coverage.get(region, 0) + 1

    report = {
        "crawler": "catcar_japanese_bounded_v1",
        "market_coverage_pages": dict(sorted(market_coverage.items())),
        "make": make.title(),
        "start_url": start_url,
        "pages_visited": len(unique_page_records),
        "detail_pages_normalized": details,
        "navigation_or_unrecognized_pages": sum(
            item["status"] == "navigation_or_unrecognized" for item in unique_page_records
        ),
        "incomplete_detail_pages": sum(
            item["status"] == "incomplete_detail" for item in unique_page_records
        ),
        "fetch_errors": sum(
            item["status"] in ("fetch_error", "schema_validation_error")
            for item in unique_page_records
        ),
        "queue_remaining": len(queue),
        "retry_urls_pending": len(set(failed_urls)),
        "complete": not queue and not failed_urls,
        "errors": errors,
    }
    write_json(output_dir / "crawl-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bounded CatCar Japanese catalog crawler")
    parser.add_argument("--make", choices=sorted(ADAPTERS), default="honda")
    parser.add_argument("--start-url")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--resume-state", type=Path, help="Previously downloaded crawl-state.json")
    args = parser.parse_args(argv)
    if args.max_pages < 1 or args.max_pages > 2000:
        parser.error("--max-pages must be between 1 and 2000")
    start_url = args.start_url or catalog_config(args.make)["url"]
    output = args.output or Path("out/catcar-{}".format(args.make))
    crawl(
        start_url,
        output,
        args.max_pages,
        args.delay,
        args.timeout,
        make=args.make,
        resume_state=args.resume_state,
    )


if __name__ == "__main__":
    main()
