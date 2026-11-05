"""Capture one real Toyota getArticles AJAX transition from CatCar."""
import argparse, asyncio, json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

SEED = "https://www.catcar.info/toyota/?l=bWFya2V0PT1ldXJvfHxzdD09NzB8fHN0cz09eyIxMCI6IlJlZ2lvbiIsIjIwIjoiRXVyb3BlIiwiMzAiOiJMRVhVUyBOWDMwMEhcLzIwMFQyMDAgNTI3NTEwIiwiNjAiOiJBR1oxMEwtQVdUTFRXIiwiNzAiOiIxMS0wMyBFTkdJTkUgT1ZFUkhBVUwgR0FTS0VUIEtJVCJ9fHxjYXRhbG9nPT01Mjc1MTB8fHJlYz09QTF8fG1vZGlmbmFtZT09QUdaMTBMLUFXVExUV3x8ZW5naW5lPT04QVJGVFN8fG1vZGVsbm89PTAwN3x8UHJvZlBlcmlvZD09MjAxNDEyOTk5OTk5fHxtb2RfaW5mbzA9PVdHfHxtb2RfaW5mbzE9PUFUTXx8bW9kX2luZm8yPT02RkN8fG1vZF9pbmZvMz09TEhEfHxtb2RfaW5mbzQ9PUx8fG1vZF9pbmZvNT09VEJPfHxncm91cF9pZD09MTEwM3x8cGFnZTcwPT0w&lang=en"

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="out/toyota-ajax-probe")
    ap.add_argument("--timeout", type=int, default=45000)
    args = ap.parse_args()
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    requests, responses = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        page.set_default_timeout(args.timeout)
        page.on("request", lambda r: requests.append({"url":r.url,"method":r.method,"type":r.resource_type,"post_data":r.post_data}) if "catcar.info" in r.url else None)
        page.on("response", lambda r: responses.append({"url":r.url,"status":r.status,"type":r.request.resource_type,"body":(r.text().catch if False else None)}) if "catcar.info" in r.url else None)
        nav = await page.goto(SEED, wait_until="domcontentloaded", timeout=args.timeout)
        await page.wait_for_timeout(2500)
        controls = await page.locator('[onclick*="getArticles"]').evaluate_all(
            "(els) => els.map((e,i) => ({i,text:(e.innerText||e.textContent||'').trim(),onclick:e.getAttribute('onclick')}))"
        )
        if not controls:
            raise RuntimeError("No visible getArticles controls on seed page")
        (out/"controls.json").write_text(json.dumps(controls,ensure_ascii=False,indent=2))
        # Capture response bodies for same-origin XHR/fetch requests.
        async def capture_response(resp):
            if resp.request.resource_type in ("xhr","fetch") and "catcar.info" in resp.url:
                try:
                    body = await resp.text()
                    responses.append({"url":resp.url,"status":resp.status,"type":resp.request.resource_type,"body":body[:500000]})
                except Exception as e:
                    responses.append({"url":resp.url,"status":resp.status,"type":resp.request.resource_type,"body_error":str(e)})
        page.on("response", capture_response)
        await page.locator('[onclick*="getArticles"]').first.evaluate("(e)=>e.click()")
        await page.wait_for_timeout(4000)
        html = await page.content()
        (out/"page-after-click.html").write_text(html,encoding="utf-8")
        scripts = await page.evaluate("""async () => {
          const u='/js/script.js?v=2.0';
          return await fetch(u).then(r=>r.text()).catch(e=>'FETCH_ERROR '+e);
        }""")
        (out/"catcar-script.js").write_text(scripts,encoding="utf-8")
        report = {"http_status":nav.status if nav else None,"seed_url":page.url,"clicked":controls[0],
                  "request_log":requests,"xhr_fetch_responses":responses,
                  "interpretation":"captured_getArticles_transition" if responses else "no_xhr_fetch_response_observed"}
        (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2))
        await browser.close()

if __name__=="__main__": asyncio.run(main())
