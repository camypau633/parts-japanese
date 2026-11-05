import unittest

from tools.catcar_poc.crawl_catalog import classify_unrecognized_page


class UnrecognizedPageClassificationTests(unittest.TestCase):
    def test_detects_empty_or_script_shell(self):
        result = classify_unrecognized_page("<html><head><title>Catalog</title></head><body></body></html>")
        self.assertEqual(result["classification"], "shell_or_empty_response")
        self.assertEqual(result["recommended_action"], "inspect_scripts_and_network_requests")

    def test_detects_table_for_adapter_fallback(self):
        html = "<table><tr><th>OEM</th><th>Part number</th></tr><tr><td>1</td><td>ABC123</td></tr></table>"
        result = classify_unrecognized_page(html, adapter_message="header mismatch")
        self.assertEqual(result["classification"], "unrecognized_table")
        self.assertEqual(result["row_count"], 2)

    def test_detects_access_challenge(self):
        result = classify_unrecognized_page("<html>Access denied: robot check captcha</html>")
        self.assertEqual(result["classification"], "access_challenge")

    def test_detects_navigation_selector(self):
        result = classify_unrecognized_page(
            "<html><a href='/toyota/?st=70'>Engine</a></html>",
            links=[{"url": "https://www.catcar.info/toyota/?st=70"}],
        )
        self.assertEqual(result["classification"], "navigation_selector")


if __name__ == "__main__":
    unittest.main()
