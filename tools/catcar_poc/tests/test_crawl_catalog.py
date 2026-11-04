import unittest
from tools.catcar_poc.crawl_catalog import (
    allowed_catalog_url, decoded_filter, discover_links
)


class CrawlCatalogTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
