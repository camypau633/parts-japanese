import base64
import json
import tempfile
import urllib.error
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.catcar_poc.crawl_catalog import (
    ADAPTERS, allowed_catalog_url, decoded_filter,
    discover_links, market_context, explicit_brand_context, toyota_variant_context, crawl,
    build_toyota_ajax_url, resolve_toyota_ajax_rows, catalog_navigation_reason,
)
from tools.catcar_poc.catalog_registry import CATCAR_JAPANESE_CATALOGS, catalog_config
from tools.catcar_poc.adapters import DiscoveryOnlyAdapter, MazdaAdapter, SubaruAdapter, SuzukiAdapter


class CrawlCatalogTests(unittest.TestCase):
    def test_shared_toyota_lexus_root_uses_only_explicit_model_brand_labels(self):
        lexus = explicit_brand_context(
            "toyota", {"sts": '{"30":"LEXUS NX300H/200T200"}'}
        )
        unresolved_toyota = explicit_brand_context(
            "toyota", {"sts": '{"30":"CAMRY 284170"}'}
        )
        ambiguous = explicit_brand_context(
            "toyota", {"brand": "TOYOTA/LEXUS"}
        )
        self.assertEqual(lexus["brand"], "Lexus")
        self.assertEqual(lexus["brand_source_field"], "sts.30")
        self.assertEqual(lexus["brand_candidates"], ["Toyota", "Lexus"])
        self.assertIsNone(unresolved_toyota["brand"])
        self.assertEqual(unresolved_toyota["brand_candidates"], ["Toyota", "Lexus"])
        self.assertIsNone(ambiguous["brand"])

    def test_toyota_variant_context_preserves_lexus_model_market_engine_and_modification(self):
        context = toyota_variant_context({
            "catalog": "527510",
            "modifname": "AGZ10L-AWTLTW",
            "engine": "8ARFTS",
            "modelno": "007",
            "ProdPeriod": "201412999999",
            "group_id": "1103",
            "sts": json.dumps({
                "10": "Region",
                "20": "Europe",
                "30": "LEXUS NX300H/200T200 527510",
                "60": "AGZ10L-AWTLTW",
                "70": "11-03 ENGINE OVERHAUL GASKET KIT",
            }),
        }, resolved_brand="Lexus")
        self.assertEqual(context["catalog_id"], "527510")
        self.assertEqual(context["model_label_raw"], "LEXUS NX300H/200T200 527510")
        self.assertEqual(context["model_name"], "NX300H/200T200")
        self.assertEqual(context["modification_name"], "AGZ10L-AWTLTW")
        self.assertEqual(context["engine_code"], "8ARFTS")
        self.assertEqual(context["model_code"], "007")
        self.assertEqual(context["production_period_code_raw"], "201412999999")
        self.assertEqual(context["source_group_id"], "1103")
        self.assertEqual(context["series_name_raw"], "AGZ10L-AWTLTW")
        self.assertEqual(context["group_label_raw"], "11-03 ENGINE OVERHAUL GASKET KIT")
        self.assertEqual(context["catalog_market_label_raw"], "Europe")

    def test_toyota_variant_model_label_is_preserved_without_guessing_brand(self):
        context = toyota_variant_context({
            "catalog": "284170",
            "sts": '{"30":"CAMRY 284170"}',
        }, resolved_brand=None)
        self.assertEqual(context["model_name"], "CAMRY")
        self.assertEqual(context["model_label_raw"], "CAMRY 284170")
        self.assertNotIn("brand", context)

    def test_shared_nissan_infiniti_root_resolves_explicit_infiniti_model_label(self):
        context = explicit_brand_context(
            "nissan", {"sts": '{"30":"INFINITI QX50"}'}
        )
        self.assertEqual(context["brand"], "Infiniti")
        self.assertEqual(context["brand_source_field"], "sts.30")
        self.assertEqual(context["brand_candidates"], ["Nissan", "Infiniti"])

    def test_registry_covers_all_eight_catcar_japanese_catalog_roots(self):
        expected = {
            "toyota", "nissan", "honda", "suzuki",
            "mazda", "mitsubishi", "isuzu", "subaru",
        }
        self.assertEqual(set(CATCAR_JAPANESE_CATALOGS), expected)
        self.assertEqual(set(ADAPTERS), expected)
        self.assertEqual(catalog_config("toyota")["brands"], ["Toyota", "Lexus"])
        self.assertEqual(catalog_config("nissan")["brands"], ["Nissan", "Infiniti"])
        self.assertIs(ADAPTERS["suzuki"], SuzukiAdapter)
        self.assertIs(ADAPTERS["mazda"], MazdaAdapter)
        self.assertIs(ADAPTERS["subaru"], SubaruAdapter)

    def test_nissan_model_selector_is_not_misparsed_as_part_numbers(self):
        encoded = base64.b64encode(
            b"region==ca||st==20||sts=={}||mod_id==51||start==1994-02-01"
        ).decode("ascii")
        html = """
        <h1>Модель</h1>
        <table><tr><th>Модель</th><th>Дата производства</th><th>Серия</th></tr>
        <tr><td><a href="/nissan/?l=MODEL">240SX</a></td>
        <td>02/1994-06/1998</td><td>S14</td></tr></table>
        """
        links = [{"url": "https://www.catcar.info/nissan/?l=" + encoded,
                  "label": "240SX"}]
        reason = catalog_navigation_reason(
            "nissan", "https://www.catcar.info/nissan/?l=REGION", html, links
        )
        self.assertEqual(reason, "nissan_model_selector")

    def test_catalog_root_without_filter_is_classified_as_selector(self):
        html = "<html><body><a href='/toyota/?l=MARKET'>Europe</a></body></html>"
        links = [{"url": "https://www.catcar.info/toyota/?l=MARKET",
                  "label": "Europe"}]
        self.assertEqual(
            catalog_navigation_reason("toyota", "https://www.catcar.info/toyota/",
                                      html, links),
            "catalog_root_selector",
        )

    def test_discovery_only_adapter_does_not_fabricate_part_records(self):
        with self.assertRaisesRegex(ValueError, "detail_adapter_not_implemented"):
            DiscoveryOnlyAdapter().parse("<html><body>unknown layout</body></html>")

    def test_nissan_region_code_ca_is_resolved_as_canada(self):
        encoded = base64.b64encode(
            b"region==ca||st==20"
        ).decode("ascii")
        context = market_context(
            {}, "https://www.catcar.info/nissan/?l=" + encoded
        )
        self.assertEqual(context["market_region"], "Canada")
        self.assertEqual(context["market_code_raw"], "ca")

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
        html = "<html><head><title>Isuzu catalog</title></head><body><a href='/isuzu/?l=next'>Next</a></body></html>"
        url = "https://www.catcar.info/isuzu/?l=selected"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out"
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_page",
                return_value=(200, url, html),
            ):
                report = crawl(
                    url, output, max_pages=1, delay=10, make="isuzu"
                )
            self.assertFalse(report["complete"])
            self.assertEqual(report["queue_remaining"], 1)
            self.assertEqual(report["detail_pages_normalized"], 0)
            records = [
                json.loads(line)
                for line in (output / "pages.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(records[0]["status"], "navigation_or_unrecognized")
            self.assertIn("detail_adapter_not_implemented", records[0]["adapter_message"])
            self.assertEqual(len(list((output / "review").glob("*.html"))), 1)
            self.assertEqual(list((output / "normalized").glob("*.json")), [])

    def test_discovery_only_pages_report_asian_market_coverage(self):
        html = """
        <html><head><title>Suzuki Asia</title></head><body>
        <img class="resize" src="https://ci.catcar.info/suzuki/asia/ABC123/IMGE/diagram.png">
        </body></html>
        """
        url = "https://www.catcar.info/suzuki/"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out"
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_page",
                return_value=(200, url, html),
            ):
                report = crawl(url, output, max_pages=1, delay=10, make="suzuki")
            self.assertEqual(report["market_coverage_pages"]["Asia"], 1)
            records = [
                json.loads(line)
                for line in (output / "pages.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(records[0]["market_region"], "Asia")
            self.assertEqual(records[0]["status"], "navigation_or_unrecognized")

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

    def test_mazda_and_subaru_explicit_japan_filters_are_not_confused_with_asia(self):
        def url_for(make, filter_text):
            encoded = base64.b64encode(filter_text.encode("utf-8")).decode("ascii")
            return "https://www.catcar.info/{}/?l={}".format(make, encoded)

        mazda_japan = market_context({}, url_for("mazda", "market==japan||st==60"))
        subaru_japan = market_context({}, url_for("subaru", "region==japan||st==20"))
        suzuki_asia = market_context({}, url_for("suzuki", "marketId==2||st==20"))

        self.assertEqual(mazda_japan["market_region"], "Japan")
        self.assertEqual(subaru_japan["market_region"], "Japan")
        self.assertEqual(suzuki_asia["market_region"], "Asia")
        self.assertNotEqual(suzuki_asia["market_region"], mazda_japan["market_region"])

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

    def test_toyota_ajax_url_preserves_catcar_pre_encoded_token(self):
        token = "bWFya2V0PT1qYXBhbnx8c3Q9PTgw%3D"
        self.assertEqual(
            build_toyota_ajax_url(token),
            "https://www.catcar.info/toyota/?l=bWFya2V0PT1qYXBhbnx8c3Q9PTgw%3D&st=81",
        )
        with self.assertRaises(ValueError):
            build_toyota_ajax_url("token&other=parameter")

    def test_toyota_ajax_rows_are_resolved_and_linked_to_source_group(self):
        html = """
        <table><tr name="15600A" onclick="getArticles(this, 'TOKEN-15600A', 80, '/toyota/');">
          <td>15600A</td><td>UNION(FOR OIL FILTER)</td>
        </tr></table>
        <img class="resize" src="https://ci.catcar.info/toyota/japan/diagram.png">
        <div class="coord" srcNum="15600A" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        ajax = """
        <table class="table inner-part">
          <tr><td>90915-YZZE1</td><td>09/2001-06/2004</td><td>2AZFE..ACV3#</td></tr>
          <tr><td>90915-YZZE2</td><td>06/2004-</td><td>2AZFE..ACV3#</td></tr>
        </table>
        """
        url = "https://www.catcar.info/toyota/?l=Z3JvdXBfaWQ9PTExMDM%3D"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out"
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_page",
                return_value=(200, url, html),
            ), patch(
                "tools.catcar_poc.crawl_catalog.fetch_toyota_ajax_page",
                return_value=(200, "https://www.catcar.info/toyota/?l=TOKEN-15600A&st=81", ajax),
            ) as ajax_fetch, patch(
                "tools.catcar_poc.crawl_catalog.time.sleep",
            ):
                report = crawl(url, output, max_pages=1, delay=10, make="toyota")
            ajax_fetch.assert_called_once_with(
                "https://www.catcar.info/toyota/?l=TOKEN-15600A&st=81", 30
            )
            self.assertTrue(report["complete"])
            self.assertEqual(report["detail_pages_normalized"], 1)
            document_path = list((output / "normalized").glob("*.json"))[0]
            document = json.loads(document_path.read_text(encoding="utf-8"))
            self.assertEqual(document["validation"]["page_status"], "complete")
            self.assertEqual(len(document["oem_records"]), 2)
            self.assertEqual(
                [item["oem_number_raw"] for item in document["oem_records"]],
                ["90915-YZZE1", "90915-YZZE2"],
            )
            self.assertEqual(
                [item["source_group_id"] for item in document["oem_records"]],
                ["1103", "1103"],
            )
            self.assertEqual(document["parts"][0]["source_status"], "requires_ajax")
            self.assertEqual(
                document["parts"][0]["additional_source_fields"]["ajax_resolution_status"],
                "available",
            )
            self.assertEqual(len(list((output / "ajax_raw").glob("*.html"))), 1)

    def test_toyota_ajax_resume_reuses_successful_raw_rows(self):
        from tools.catcar_poc.adapters import ToyotaAdapter
        group_html = """
          <table>
            <tr name="ROW-1" onclick="getArticles(this, 'TOKEN-1', 80, '/toyota/');"><td>ROW-1</td><td>PART ONE</td></tr>
            <tr name="ROW-2" onclick="getArticles(this, 'TOKEN-2', 80, '/toyota/');"><td>ROW-2</td><td>PART TWO</td></tr>
          </table>
        """
        first_response = """
          <table><tr><td>OEM-ONE</td><td>01/2001-</td><td>ENGINE-A</td></tr></table>
        """
        second_response = """
          <table><tr><td>OEM-TWO</td><td>02/2001-</td><td>ENGINE-B</td></tr></table>
        """
        group_url = "https://www.catcar.info/toyota/?l=Z3JvdXBfaWQ9PTExMDM%3D"
        with tempfile.TemporaryDirectory() as temp:
            first_parsed = ToyotaAdapter().parse(group_html)
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_toyota_ajax_page",
                side_effect=[
                    (200, "https://www.catcar.info/toyota/?l=TOKEN-1&st=81", first_response),
                    urllib.error.URLError("temporary failure for second row"),
                ],
            ) as fetch, patch("tools.catcar_poc.crawl_catalog.time.sleep"):
                first_records, first_errors = resolve_toyota_ajax_rows(
                    first_parsed, group_url, temp, 30, request_delay=0
                )
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(len(first_records), 1)
            self.assertEqual(len(first_errors), 1)

            resumed_parsed = ToyotaAdapter().parse(group_html)
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_toyota_ajax_page",
                return_value=(200, "https://www.catcar.info/toyota/?l=TOKEN-2&st=81", second_response),
            ) as resumed_fetch, patch("tools.catcar_poc.crawl_catalog.time.sleep"):
                resumed_records, resumed_errors = resolve_toyota_ajax_rows(
                    resumed_parsed, group_url, temp, 30, request_delay=0
                )
            resumed_fetch.assert_called_once_with(
                "https://www.catcar.info/toyota/?l=TOKEN-2&st=81", 30
            )
            self.assertEqual(resumed_errors, [])
            self.assertEqual(
                [item["oem_number_raw"] for item in resumed_records],
                ["OEM-ONE", "OEM-TWO"],
            )

    def test_toyota_ajax_cache_is_scoped_to_full_group_url_not_reused_group_id(self):
        from tools.catcar_poc.adapters import ToyotaAdapter
        html = """
          <table><tr name="ROW-1" onclick="getArticles(this, 'TOKEN-1', 80, '/toyota/');">
          <td>ROW-1</td><td>PART ONE</td></tr></table>
        """
        camry_url = "https://www.catcar.info/toyota/?l=" + base64.b64encode(
            b"group_id==1103||catalog==284170"
        ).decode("ascii")
        lexus_url = "https://www.catcar.info/toyota/?l=" + base64.b64encode(
            b"group_id==1103||catalog==527510"
        ).decode("ascii")
        camry_response = "<table><tr><td>CAMRY-OEM</td><td>01/2001-</td><td>2AZFE</td></tr></table>"
        lexus_response = "<table><tr><td>LEXUS-OEM</td><td>01/2015-</td><td>8ARFTS</td></tr></table>"

        with tempfile.TemporaryDirectory() as temp:
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_toyota_ajax_page",
                side_effect=[
                    (200, "https://www.catcar.info/toyota/?l=CAMRY&st=81", camry_response),
                    (200, "https://www.catcar.info/toyota/?l=LEXUS&st=81", lexus_response),
                ],
            ) as fetch, patch("tools.catcar_poc.crawl_catalog.time.sleep"):
                camry_records, camry_errors = resolve_toyota_ajax_rows(
                    ToyotaAdapter().parse(html), camry_url, temp, 30, request_delay=0
                )
                lexus_records, lexus_errors = resolve_toyota_ajax_rows(
                    ToyotaAdapter().parse(html), lexus_url, temp, 30, request_delay=0
                )

            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(camry_errors, [])
            self.assertEqual(lexus_errors, [])
            self.assertEqual(camry_records[0]["oem_number_raw"], "CAMRY-OEM")
            self.assertEqual(lexus_records[0]["oem_number_raw"], "LEXUS-OEM")
            self.assertEqual(len(list((Path(temp) / "ajax_raw").glob("*.html"))), 2)

    def test_toyota_no_applicable_data_is_a_valid_resolved_ajax_state(self):
        from tools.catcar_poc.adapters import ToyotaAdapter
        parsed = ToyotaAdapter().parse("""
          <table><tr name="12321A" onclick="getArticles(this, 'TOKEN-12321A', 80, '/toyota/');">
          <td>12321A</td><td>CLIP</td></tr></table>
          <img class="resize" src="https://ci.catcar.info/toyota/japan/diagram.png">
        """)
        with tempfile.TemporaryDirectory() as temp:
            records, errors = resolve_toyota_ajax_rows(
                parsed,
                "https://www.catcar.info/toyota/?l=group",
                temp,
                30,
                request_delay=0,
            )
            self.assertEqual(errors, [])
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["source_status"], "no_applicable_data")
            self.assertEqual(parsed["parts"][0]["source_status"], "no_applicable_data")

    def test_toyota_ajax_failure_keeps_page_incomplete(self):
        html = """
        <table><tr name="15600A" onclick="getArticles(this, 'TOKEN-15600A', 80, '/toyota/');">
          <td>15600A</td><td>UNION(FOR OIL FILTER)</td>
        </tr></table>
        <img class="resize" src="https://ci.catcar.info/toyota/japan/diagram.png">
        """
        url = "https://www.catcar.info/toyota/?l=group"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out"
            with patch(
                "tools.catcar_poc.crawl_catalog.fetch_page",
                return_value=(200, url, html),
            ), patch(
                "tools.catcar_poc.crawl_catalog.fetch_toyota_ajax_page",
                side_effect=urllib.error.URLError("temporary AJAX failure"),
            ), patch("tools.catcar_poc.crawl_catalog.time.sleep"):
                report = crawl(url, output, max_pages=1, delay=10, make="toyota")
            self.assertEqual(report["detail_pages_normalized"], 0)
            self.assertFalse(report["complete"])
            self.assertEqual(report["incomplete_detail_pages"], 1)
            self.assertEqual(report["retry_urls_pending"], 1)
            document_files = list((output / "normalized").glob("*.json"))
            self.assertEqual(document_files, [])
            review_documents = list((output / "review").glob("*.json"))
            self.assertEqual(len(review_documents), 1)
            partial = json.loads(review_documents[0].read_text(encoding="utf-8"))
            self.assertEqual(partial["validation"]["page_status"], "incomplete")

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
            self.assertEqual(second["pages_visited"], 1)
            self.assertEqual(second["market_coverage_pages"], {"Europe": 1})
            self.assertEqual(second["fetch_errors"], 0)


if __name__ == "__main__":
    unittest.main()
