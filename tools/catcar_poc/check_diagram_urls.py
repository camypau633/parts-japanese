"""Bounded CatCar diagram URL probe; never downloads full image files."""
import argparse
import json
import posixpath
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


def collect_urls(paths, max_urls):
    urls = set()
    for path in paths:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        source_url = str((document.get("source") or {}).get("url") or "").strip()
        for diagram in document.get("diagrams") or []:
            image_url = str(diagram.get("source_image_url") or "").strip()
            if not image_url:
                continue
            url = urljoin(source_url, image_url)
            parsed = urlsplit(url)
            if parsed.hostname and (parsed.hostname == "catcar.info" or parsed.hostname.endswith(".catcar.info")):
                parsed = parsed._replace(scheme="https")
            parsed = parsed._replace(path=quote(posixpath.normpath(parsed.path), safe="/%:@"))
            urls.add(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment)))
    ordered = sorted(urls)
    if len(ordered) > max_urls:
        raise ValueError("Found %d unique diagram URLs; limit is %d" % (len(ordered), max_urls))
    for url in ordered:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.scheme not in ("http", "https") or not (host == "catcar.info" or host.endswith(".catcar.info")):
            raise ValueError("Non-CatCar diagram URL rejected: %s" % url)
    return ordered


def probe(url, timeout):
    request = Request(url, method="HEAD", headers={"User-Agent": "PartScope-CatCar-URL-Check/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return {"url": url, "method": "HEAD", "status": response.status,
                    "reachable": 200 <= response.status < 400, "content_type": response.headers.get("Content-Type")}
    except HTTPError as error:
        if error.code not in (405, 501):
            return {"url": url, "method": "HEAD", "status": error.code,
                    "reachable": False, "error": str(error)}
    except (URLError, TimeoutError, OSError) as error:
        return {"url": url, "method": "HEAD", "status": None,
                "reachable": False, "error": str(error)}

    # Some image hosts do not implement HEAD. Request one byte and close immediately.
    request = Request(url, headers={
        "User-Agent": "PartScope-CatCar-URL-Check/1.0",
        "Range": "bytes=0-0",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read(1)
            return {"url": url, "method": "GET-range", "status": response.status,
                    "reachable": 200 <= response.status < 400,
                    "content_type": response.headers.get("Content-Type")}
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        status = error.code if isinstance(error, HTTPError) else None
        return {"url": url, "method": "GET-range", "status": status,
                "reachable": False, "error": str(error)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-urls", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args(argv)

    urls = collect_urls(args.input, args.max_urls)
    results = [probe(url, args.timeout) for url in urls]
    report = {
        "check": "bounded_catcar_diagram_url_probe",
        "network_requests_max": len(urls) * 2,
        "unique_urls": len(urls),
        "reachable_count": sum(item["reachable"] for item in results),
        "unreachable_count": sum(not item["reachable"] for item in results),
        "results": results,
        "note": "Only HEAD or a one-byte range request is attempted; full images are never downloaded.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
