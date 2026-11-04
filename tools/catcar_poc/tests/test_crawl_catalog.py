import base64
import json
import tempfile
import urllib.error
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.catcar_poc.crawl_catalog import (
    ADAPTERS, allowed_catalog_url, decoded_filter,
    discover_links, market_context, crawl
)
from tools.catcar_poc.catalog_registry import CATCAR_JAPANESE_CATALOGS, catalog_config
from tools.catcar_poc.adapters import DiscoveryOnlyAdapter


class CrawlCatalogTests(unittest.TestCase):
    def test_registry_covers_all_eight_catcar_japanese_catalog_roots(self):
        expected = {
            "toyota", "nissan", "honda", "suzuki",
            "mazda", "mitsubishi", "isuzu", "subaru",
        }
        self.assertEqual(set(CATCAR_JAPANESE_CATALOGS), expected)
        self.assertEqual(set(ADAPTERS), expected)
        self.assertEqual(catalog_config("toyota")["brands"], ["Toyota", "Lexus"])
        self.assertEqual(catalog_config("nissan")["brands"], ["Nissan", "Infiniti"])
        self.assertIs(ADAPTERS["suzuki"], DiscoveryOnlyAdapter)
        self.assertIs(ADAPTERS["mazda"], DiscoveryOnlyAdapter)

    def test_discovery_only_adapter_does_not_fabricate_part_records(self):
        with self.assertRaisesRegex(ValueError, "detail_adapter_not_implemented"):
            DiscoveryOnlyAdapter().parse("<html><body>unknown layout</body></html>")

    def test_suzuki_numeric_market_ids_are_decoded_from_verified_catalog_filters(self):
        def url_for(filter_text):
            encoded = base64.b64encode(filter_text.encode("utf-8")).decode("ascii")
            return "https://www.catcar.info/suzuki/?l=" + encoded

        europe = market_context(
            {}, url_for("marketId==5||st==20")
        )
        asia = market_context(
            {}, url_for("marketId==2||st==20")
        )
        self.assertEqual(europe["market_region"], "Europe")
        self.assertEqual(europe["market_code_raw"], "marketId=5")
        self.assertEqual(asia["market_region"], "Asia")
        self.assertNotEqual(asia["market_region"], "Japan")

    def test_asian_market_is_preserved_separately_from_japan_for_all_make_paths(self):
        asia = {
            "images": [{
                "src": "https://ci.catcar.info/mazda/asia/ABC123/IMGE/diagram.png"
            }]
        }
        japan = {
            "images": [{
                "src": "https://ci.catcar.info/mazda/japan/ABC123/IMGE/diagram.png"
            }]
        }
        self.assertEqual(
            market_context(asia, "https://www.catcar.info/mazda/")[ "market_region" ],
            "Asia",
        )
        self.assertEqual(
            market_context(japan, "https://www.catcar.info/mazda/")[ "market_region" ],
            "Japan",
        )
        self.assertNotEqual(
            market_context(asia, "https://www.catcar.info/mazda/")[ "market_region" ],
            market_context(japan, "https://www.catcar.info/mazda/")[ "market_region" ],
        )

    def test_discovery_only_catalog_retains_page_without_fabricating_records(self):
        html = "<html><head><title>Suzuki catalog</title></head><body><a href='/suzuki/?l=next'>Next</a></body></html>"
        url = "https://www.catcar.info/suzuki/"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out"
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_page",
                return_value=(200, url, html),
            ):
                report = crawl(
                    url, output, max_pages=1, delay=10, make="suzuki"
                )
            self.assertTrue(report["complete"])
            self.assertEqual(report["detail_pages_normalized"], 0)
            records = [
                json.loads(line)
                for line in (output / "pages.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(records[0]["status"], "navigation_or_unrecognized")
            self.assertIn("detail_adapter_not_implemented", records[0]["adapter_message"])
            self.assertEqual(len(list((output / "review").glob("*.html"))), 1)
            self.assertEqual(list((output / "normalized").glob("*.json")), [])

    def test_scope_rejects_other_makes_and_hosts(self):
        self.assertTrue(allowed_catalog_url("https://www.catcar.info/honda/?l=x", "honda"))
        self.assertFalse(allowed_catalog_url("https://www.catcar.info/toyota/", "honda"))
        self.assertFalse(allowed_catalog_url("https://example.com/honda/", "honda"))

    def test_discovery_keeps_only_selected_make(self):
        html = """
        <html><head><title>Honda catalog</title></head><body>
        <a href="/honda/?l=abc">Honda model</a>
        <a href="/toyota/?l=def">Toyota model</a>
        <a href="https://example.com/honda/">External</a>
        </body></html>
        """
        title, links = discover_links(html, "https://www.catcar.info/honda/", "honda")
        self.assertEqual(title, "Honda catalog")
        self.assertEqual(len(links), 1)
        self.assertIn("/honda/?l=abc", links[0]["url"])

    def test_decoded_filter_preserves_explicit_fields(self):
        url = "https://www.catcar.info/honda/?l=bW9kbmFtZT09QUNDT1JE"
        self.assertEqual(decoded_filter(url), {"modname": "ACCORD"})

    def test_market_region_is_separate_from_japanese_manufacturer_origin(self):
        european = {
            "images": [{"src": "https://ci.catcar.info/honda/euro/18TA0801/IMGE/E__0100.png"}]
        }
        japan = {
            "images": [{"src": "https://ci.catcar.info/honda/japan/18TA0801/IMGE/E__0100.png"}]
        }
        self.assertEqual(
            market_context(european, "https://www.catcar.info/honda/")["market_region"],
            "Europe",
        )
        self.assertEqual(
            market_context(japan, "https://www.catcar.info/honda/")["market_region"],
            "Japan",
        )

    def test_crawl_normalizes_a_realistic_honda_detail_page_without_network(self):
        html = """
        <table>
          <tr><th>Код</th><th>Артикул</th><th>Описание</th><th>Дополнительная информация</th><th>Опционные коды</th></tr>
          <tr><td>1</td><td>16400-RL2-G01</td><td>THROTTLE BODY</td><td></td><td></td></tr>
        </table>
        <img class="resize" src="http://ci.catcar.info/honda/euro/18TA0801/IMGE/E__0100.png">
        <div class="coord" srcNum="1" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        url = "https://www.catcar.info/honda/?l=sample"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out"
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_page",
                return_value=(200, url, html),
            ):
                report = crawl(url, output, max_pages=1, delay=10)
            self.assertTrue(report["complete"])
            self.assertEqual(report["detail_pages_normalized"], 1)
            files = list((output / "normalized").glob("*.json"))
            self.assertEqual(len(files), 1)
            document = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(document["parts"][0]["part_number_raw"], "16400-RL2-G01")
            self.assertEqual(document["catalog_context"]["brand"], "Honda")
            self.assertEqual(document["catalog_context"]["manufacturer_country"], "Japan")
            self.assertEqual(document["catalog_context"]["market_region"], "Europe")

    def test_resume_restores_queue_and_does_not_refetch_visited_page(self):
        html = """
        <table>
          <tr><th>Код</th><th>Артикул</th><th>Описание</th></tr>
          <tr><td>1</td><td>16400-RL2-G01</td><td>THROTTLE BODY</td></tr>
        </table>
        <img class="resize" src="http://ci.catcar.info/honda/euro/18TA0801/IMGE/E__0100.png">
        """
        root = "https://www.catcar.info/honda/"
        child = "https://www.catcar.info/honda/?l=child"
        root_html = html.replace(
            "</table>",
            '</table><a href="/honda/?l=child">Next</a>',
        )
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out"
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_page",
                return_value=(200, root, root_html),
            ):
                first = crawl(root, output, max_pages=1, delay=10)
            self.assertFalse(first["complete"])
            state = output / "crawl-state.json"
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_page",
                return_value=(200, child, html),
            ) as fetch:
                second = crawl(
                    root, output, max_pages=1, delay=10, resume_state=state
                )
            fetch.assert_called_once()
            self.assertEqual(fetch.call_args.args[0], child)
            self.assertTrue(second["complete"])
            self.assertEqual(second["pages_visited"], 2)

    def test_failed_page_is_retried_after_resume(self):
        html = """
        <table>
          <tr><th>Код</th><th>Артикул</th><th>Описание</th></tr>
          <tr><td>1</td><td>16400-RL2-G01</td><td>THROTTLE BODY</td></tr>
        </table>
        <img class="resize" src="http://ci.catcar.info/honda/euro/18TA0801/IMGE/E__0100.png">
        """
        url = "https://www.catcar.info/honda/"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out"
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_page",
                side_effect=urllib.error.URLError("temporary network error"),
            ):
                first = crawl(url, output, max_pages=1, delay=10)
            self.assertFalse(first["complete"])
            self.assertEqual(first["retry_urls_pending"], 1)
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_page",
                return_value=(200, url, html),
            ) as fetch:
                second = crawl(
                    url,
                    output,
                    max_pages=1,
                    delay=10,
                    resume_state=output / "crawl-state.json",
                )
            fetch.assert_called_once()
            self.assertTrue(second["complete"])
            self.assertEqual(second["detail_pages_normalized"], 1)
            self.assertEqual(second["fetch_errors"], 1)


if __name__ == "__main__":
    unittest.main()
