import io
import unittest
import urllib.error
from email.message import Message

from tools.catcar_poc.network import fetch_html


class FakeResponse:
    status = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, body=b"<html>ok</html>"):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body[:size]

    def geturl(self):
        return "https://www.catcar.info/toyota/"


class ResilientNetworkTests(unittest.TestCase):
    def test_retries_gateway_timeout_then_succeeds(self):
        calls = []
        waits = []

        def opener(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                headers = Message()
                raise urllib.error.HTTPError(
                    request.full_url, 504, "Gateway Timeout", headers, io.BytesIO()
                )
            return FakeResponse()

        result = fetch_html(
            "https://www.catcar.info/toyota/", 5,
            {"User-Agent": "test"}, 1024,
            opener=opener, sleep=waits.append,
        )
        self.assertEqual(result[0], 200)
        self.assertEqual(len(calls), 2)
        self.assertEqual(waits, [2.0])

    def test_does_not_retry_non_transient_http_errors(self):
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            headers = Message()
            raise urllib.error.HTTPError(
                request.full_url, 404, "Not Found", headers, io.BytesIO()
            )

        with self.assertRaises(urllib.error.HTTPError):
            fetch_html(
                "https://www.catcar.info/toyota/", 5,
                {"User-Agent": "test"}, 1024,
                opener=opener, sleep=lambda _: self.fail("must not sleep"),
            )
        self.assertEqual(len(calls), 1)

    def test_rejects_non_html_without_retry(self):
        class NonHtml(FakeResponse):
            headers = {"Content-Type": "application/json"}

        calls = []

        def opener(request, timeout):
            calls.append(1)
            return NonHtml(b'{"error":true}')

        with self.assertRaisesRegex(ValueError, "unexpected_content_type"):
            fetch_html(
                "https://www.catcar.info/toyota/", 5,
                {"User-Agent": "test"}, 1024,
                opener=opener, sleep=lambda _: self.fail("must not sleep"),
            )
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
