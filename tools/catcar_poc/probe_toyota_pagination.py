"""Bounded live probe for Toyota/Lexus detail-page pagination.

The probe fetches one known CatCar Toyota-root detail page, inspects its HTML and
same-site JavaScript for pagination controls, and optionally follows one
explicitly advertised next-page URL. It does not guess page parameters or crawl
the catalog. Raw evidence is retained as a GitHub Actions artifact.
"""
import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

DEFAULT_URL = (
    "https://www.catcar.info/toyota/?l="
    "bWFya2V0PT1ldXJvfHxzdD09NzB8fHN0cz09eyIxMCI6IlJlZ2lvbiIsIjIwIjoiRXVyb3BlIiwi"
    "MzAiOiJMRVhVUyBOWDMwMEhcLzIwMFQyMDAgNTI3NTEwIiwiNjAiOiJBR1oxMEwtQVdUTFRXIiwi"
    "NzAiOiIxMS0wMyBFTkdJTkUgT1ZFUkhBVUwgR0FTS0VUIEtJVCJ9fHxjYXRhbG9nPT01Mjc1MTB8"
    "fHJlYz09QTF8fG1vZGlmbmFtZT09QUdaMTBMLUFXVExUV3x8ZW5naW5lPT04QVJGVFN8fG1vZGVs"
    "bm89PTAwN3x8UHJvZlBlcmlvZD09MjAxNDEyOTk5OTk5fHxtb2RfaW5mbzA9PVdHfHxtb2RfaW5m"
    "bzE9PUFUTXx8bW9kX2luZm8yPT02RkN8fG1vZF9pbmZvMz09TEhEfHxtb2RfaW5mbzQ9PUx8fG1v"
    "ZF9pbmZvNT09VEJPfHxncm91cF9pZD09MTEwM3x8cGFnZTcwPT0w&lang=en"
)
USER_AGENT = "PartScope-Toyota-Pagination-Probe/0.1"
MAX_BYTES = 2 * 1024 * 1024
MAX_SCRIPTS = 5
PATTERNS = re.compile(
    r"pagination|\bnext\b|page(?:[0-9]+)?|getArticles|changePage|loadPage|"
    r"ajax|st\s*[:=]\s*81",
    re.IGNORECASE,
)


class EvidenceParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self.scripts = []
        self.forms = []
        self._anchor = None
        self._script = None
        self._form = None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "a":
            self._anchor = {"href": a.get("href", ""), "text": "", "onclick": a.get("onclick", "")}
            self.anchors.append(self._anchor)
        elif tag == "script":
            self._script = {"src": a.get("src", ""), "text": ""}
            self.scripts.append(self._script)
        elif tag == "form":
            self._form = {"action": a.get("action", ""), "method": a.get("method", "get"), "controls": []}
            self.forms.append(self._form)
        elif self._form is not None and tag in ("input", "select", "button"):
            self._form["controls"].append({
                "tag": tag, "name": a.get("name", ""), "value": a.get("value", ""),
                "type": a.get("type", ""), "onclick": a.get("onclick", "")
            })

    def handle_data(self, data):
        if self._anchor is not None:
            self._anchor["text"] += data
        if self._script is not None and not self._script["src"]:
            self._script["text"] += data

    def handle_endtag(self, tag):
        if tag == "a":
            self._anchor = None
        elif tag == "script":
            self._script = None
        elif tag == "form":
            self._form = None


def fetch(url, timeout):
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("response_exceeds_2MiB")
        return response.status, response.geturl(), response.headers.get("Content-Type", ""), body


def same_catcar_host(url):
    host = (urlsplit(url).hostname or "").lower()
    return host == "catcar.info" or host.endswith(".catcar.info")


def compact_evidence(text, limit=12):
    found = []
    for match in PATTERNS.finditer(text):
        start, end = max(0, match.start() - 180), min(len(text), match.end() + 260)
        snippet = re.sub(r"\s+", " ", text[start:end]).strip()
        if snippet not in found:
            found.append(snippet[:500])
        if len(found) >= limit:
            break
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", default="out/toyota-pagination-probe")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--delay", type=float, default=10.0)
    args = parser.parse_args()
    if args.delay < 10:
        raise SystemExit("delay must be at least 10 seconds")
    parts = urlsplit(args.url)
    if not same_catcar_host(args.url) or not parts.path.startswith("/toyota/"):
        raise SystemExit("URL must be a CatCar Toyota catalog URL")

    out = Path(args.output)
    (out / "scripts").mkdir(parents=True, exist_ok=True)
    status, final_url, content_type, body = fetch(args.url, args.timeout)
    if status != 200 or "html" not in content_type.lower():
        raise SystemExit("unexpected page response: %s %s" % (status, content_type))
    html = body.decode("utf-8", "replace")
    (out / "page.html").write_text(html, encoding="utf-8")

    evidence = EvidenceParser()
    evidence.feed(html)
    inline_js = "\n".join(item["text"] for item in evidence.scripts if item["text"])
    (out / "inline-scripts.js").write_text(inline_js, encoding="utf-8")

    script_results = []
    external = []
    for item in evidence.scripts:
        if not item["src"]:
            continue
        script_url = urljoin(final_url, item["src"])
        if same_catcar_host(script_url) and script_url not in external:
            external.append(script_url)

    for index, script_url in enumerate(external[:MAX_SCRIPTS]):
        if index:
            time.sleep(args.delay)
        try:
            js_status, js_final, js_type, js_body = fetch(script_url, args.timeout)
            js_text = js_body.decode("utf-8", "replace")
            filename = "%02d-%s.js" % (
                index + 1, hashlib.sha256(script_url.encode()).hexdigest()[:10]
            )
            (out / "scripts" / filename).write_text(js_text, encoding="utf-8")
            script_results.append({
                "url": script_url, "final_url": js_final, "status": js_status,
                "content_type": js_type, "file": "scripts/" + filename,
                "pagination_evidence": compact_evidence(js_text),
            })
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            script_results.append({"url": script_url, "error": str(exc)[:300]})

    seed_query = parse_qs(parts.query, keep_blank_values=True)
    anchor_results = []
    explicit_next = []
    for item in evidence.anchors:
        href = item["href"].strip()
        if not href or href.startswith(("javascript:", "#")):
            continue
        target = urljoin(final_url, href)
        if not same_catcar_host(target) or not urlsplit(target).path.startswith("/toyota/"):
            continue
        target_query = parse_qs(urlsplit(target).query, keep_blank_values=True)
        changed = {
            key: {"from": seed_query.get(key), "to": target_query.get(key)}
            for key in set(seed_query) | set(target_query)
            if seed_query.get(key) != target_query.get(key)
        }
        label = re.sub(r"\s+", " ", item["text"]).strip()
        row = {"label": label[:160], "url": target, "query_changes": changed,
               "onclick": item["onclick"][:300]}
        anchor_results.append(row)
        if re.search(r"next|след|^[2-9]$", label, re.IGNORECASE) or (
            changed and any(re.search(r"page|st", key, re.IGNORECASE) for key in changed)
        ):
            explicit_next.append(row)

    report = {
        "status": "page_fetched",
        "seed_url": args.url,
        "final_url": final_url,
        "http_status": status,
        "content_type": content_type,
        "page_bytes": len(body),
        "inline_script_count": sum(bool(x["text"]) for x in evidence.scripts),
        "external_script_count": len(external),
        "external_scripts_inspected": script_results,
        "forms": evidence.forms,
        "same_catalog_anchor_count": len(anchor_results),
        "candidate_pagination_links": explicit_next,
        "inline_pagination_evidence": compact_evidence(inline_js),
        "page_query_keys": sorted(seed_query),
        "interpretation": (
            "explicit_next_link_found" if explicit_next else
            "pagination_not_exposed_as_plain_anchor; inspect retained JS/HTML evidence"
        ),
        "followed_next_page": False,
        "notes": [
            "No page parameter is guessed or modified.",
            "Only same-site JavaScript assets are fetched, with at least the configured delay.",
            "A candidate link is reported, not followed, to avoid unverified repeated requests."
        ],
    }
    (out / "probe-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
