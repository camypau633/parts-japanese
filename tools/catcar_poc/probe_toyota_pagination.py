"""Browser-level, single-page Toyota/Lexus pagination probe for GitHub Actions."""
import argparse
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

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
NEXT_LABEL = re.compile(r"^(next|следующая|след|›|»|>)$", re.IGNORECASE)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", default="out/toyota-pagination-probe")
    parser.add_argument("--timeout", type=int, default=45000)
    args = parser.parse_args()
    parts = urlsplit(args.url)
    host = (parts.hostname or "").lower()
    if host not in ("catcar.info", "www.catcar.info") or not parts.path.startswith("/toyota/"):
        raise SystemExit("URL must be a CatCar Toyota catalog URL")

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    requests, responses = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        page.set_default_timeout(args.timeout)
        page.on("request", lambda req: requests.append({
            "url": req.url, "method": req.method, "resource_type": req.resource_type,
            "is_navigation": req.is_navigation_request()
        }) if (urlsplit(req.url).hostname or "").endswith("catcar.info") else None)
        page.on("response", lambda res: responses.append({
            "url": res.url, "status": res.status, "resource_type": res.request.resource_type
        }) if (urlsplit(res.url).hostname or "").endswith("catcar.info") else None)

        navigation_error = None
        try:
            response = await page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)
            await page.wait_for_timeout(5000)
        except Exception as exc:
            response = None
            navigation_error = str(exc)[:500]

        initial_url = page.url
        initial_html = await page.content()
        (out / "page-initial.html").write_text(initial_html, encoding="utf-8")
        dom = await page.evaluate("""() => ({
          title: document.title,
          scripts: Array.from(document.scripts).map(s => ({src:s.src || '', inline:(s.src ? '' : s.textContent || '').slice(0,200000)})),
          controls: Array.from(document.querySelectorAll('a,button,[role=button],[onclick],[class*=page],[id*=page]'))
            .filter(e => { const r=e.getBoundingClientRect(); return r.width>0 && r.height>0; })
            .map(e => ({tag:e.tagName, text:(e.innerText || e.textContent || '').trim().replace(/\\s+/g,' ').slice(0,120),
              href:e.getAttribute('href'), onclick:e.getAttribute('onclick'),
              aria:e.getAttribute('aria-label'), title:e.getAttribute('title'),
              cls:typeof e.className==='string'?e.className:'', id:e.id,
              html:e.outerHTML.slice(0,700)}))
        })""")
        (out / "inline-scripts.json").write_text(
            json.dumps(dom["scripts"], ensure_ascii=False, indent=2), encoding="utf-8"
        )

        candidates = []
        for index, item in enumerate(dom["controls"]):
            label = " ".join((item.get("text") or "").split())
            aria = item.get("aria") or ""
            title = item.get("title") or ""
            class_id = (item.get("cls") or "") + " " + (item.get("id") or "")
            exact_next = bool(NEXT_LABEL.fullmatch(label or aria or title))
            page_two_control = label == "2" and re.search(r"page|pagination", class_id, re.I)
            if exact_next or page_two_control:
                candidates.append({"index": index, **item, "reason": "explicit_next" if exact_next else "page_2_control"})

        clicked = None
        click_error = None
        if candidates:
            selected = candidates[0]
            locator = page.locator(
                '[data-partscope-probe-index="%s"]' % selected["index"]
            )
            try:
                await locator.click(timeout=5000)
                clicked = selected
                await page.wait_for_timeout(5000)
            except Exception as exc:
                click_error = str(exc)[:500]

        final_html = await page.content()
        (out / "page-after-click.html").write_text(final_html, encoding="utf-8")
        report = {
            "status": "page_loaded" if response else "navigation_failed",
            "seed_url": args.url,
            "initial_url": initial_url,
            "final_url": page.url,
            "http_status": response.status if response else None,
            "navigation_error": navigation_error,
            "page_title": dom.get("title"),
            "visible_control_count": len(dom["controls"]),
            "pagination_candidates": candidates,
            "clicked_control": clicked,
            "click_error": click_error,
            "requests": requests,
            "responses": responses,
            "ajax_or_fetch_requests": [r for r in requests if r["resource_type"] in ("xhr", "fetch")],
            "interpretation": (
                "pagination_control_clicked_network_captured" if clicked and not click_error else
                "no_unambiguous_visible_pagination_control" if not candidates else
                "pagination_candidate_click_failed"
            ),
            "caution": "Only one explicit next/page-2 control is clicked; no page parameter is guessed."
        }
        (out / "probe-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
