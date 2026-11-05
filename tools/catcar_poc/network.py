"""Resilient HTTP transport for CatCar catalog requests.

Retries only transient transport/server failures. Structural/content errors are
returned immediately so the crawler can classify and preserve them for review.
"""
import email.utils
import time
import urllib.error
import urllib.request

TRANSIENT_HTTP_CODES = {408, 425, 429, 500, 502, 503, 504}


def fetch_html(url, timeout, headers, max_bytes, attempts=4, base_delay=2.0,
               max_delay=30.0, opener=None, sleep=time.sleep):
    """Fetch HTML with bounded exponential backoff and Retry-After support."""
    request = urllib.request.Request(url, headers=headers)
    open_url = opener or urllib.request.urlopen
    last_error = None

    for attempt in range(attempts):
        retry_after = None
        try:
            with open_url(request, timeout=timeout) as response:
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError("page_exceeds_size_limit")
                content_type = response.headers.get("Content-Type", "")
                if "html" not in content_type.lower():
                    raise ValueError("unexpected_content_type:" + content_type)
                return response.status, response.geturl(), body.decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in TRANSIENT_HTTP_CODES or attempt + 1 >= attempts:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                raise

        delay = min(max_delay, base_delay * (2 ** attempt))
        if retry_after:
            try:
                delay = max(delay, min(max_delay, float(retry_after)))
            except ValueError:
                try:
                    parsed = email.utils.parsedate_to_datetime(retry_after)
                    delay = max(delay, min(max_delay, parsed.timestamp() - time.time()))
                except (TypeError, ValueError, OverflowError):
                    pass
        sleep(max(0.0, delay))

    raise last_error
