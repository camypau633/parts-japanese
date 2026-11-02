import base64
import unittest
from urllib.parse import quote

from tools.catcar_poc.validate_real_artifacts import (
    catcar_filter_params,
    nissan_context_from_url,
)


class NissanContextTests(unittest.TestCase):
    def test_reads_vehicle_and_group_dates_from_catcar_filter(self):
        raw = "region==el||mod_id==43||start==2009-03-01||end==2013-08-01||startgrp==2012-01-01||endgrp==2013-08-01"
        encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        url = "https://www.catcar.info/nissan/?l=" + quote(encoded, safe="")
        params = catcar_filter_params(url)
        self.assertEqual(params["mod_id"], "43")
        context = nissan_context_from_url(url)
        self.assertEqual(context["production_period_raw"], "2009-03-01 — 2013-08-01")
        self.assertEqual(context["source_group_period_raw"], "2012-01-01 — 2013-08-01")
        self.assertNotIn("engine_code", context)
        self.assertNotIn("engine", context)

    def test_missing_dates_remain_missing(self):
        raw = "region==el||mod_id==43"
        encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        url = "https://www.catcar.info/nissan/?l=" + quote(encoded, safe="")
        context = nissan_context_from_url(url)
        self.assertNotIn("production_period_raw", context)
        self.assertNotIn("source_group_period_raw", context)
        self.assertNotIn("engine_code", context)


if __name__ == "__main__":
    unittest.main()
