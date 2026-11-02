import json
import unittest
from pathlib import Path

import jsonschema

from tools.catcar_poc.adapters import FordAdapter, NissanAdapter, ToyotaAdapter, VagAdapter
from tools.catcar_poc.normalize import normalize_page


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "schemas" / "catcar-extraction-v0.1.schema.json"


class SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with SCHEMA_PATH.open(encoding="utf-8") as handle:
            cls.schema = json.load(handle)

    def test_normalized_documents_validate_against_shared_schema(self):
        samples = [
            (
                ToyotaAdapter(),
                """<table><tr name="15600A" onclick="getArticles(this, 'T')"><td>15600A</td></tr></table>
                <div class="coord" srcNum="15600A" srcTop="1" srcLeft="2" srcWidth="3" srcHeight="4"></div>""",
                {"brand": "Toyota"},
                ToyotaAdapter.parse_ajax_records(
                    "<table><tr><td>SU003-00302</td><td>09/2012-</td><td>FA20</td></tr></table>",
                    source_row_id="15600A",
                ),
            ),
            (
                NissanAdapter(),
                """<table><tr><th>№</th><th>Номер детали</th><th>Название</th><th>Дата</th><th>Alt</th><th>Qty</th></tr>
                <tr><td>12010S</td><td>12000-4A00A</td><td>PISTON SET</td><td>03/2009-</td><td></td><td>03</td></tr></table>
                <div class="coord" srcNum="12010S" srcTop="1" srcLeft="2" srcWidth="3" srcHeight="4"></div>""",
                {"brand": "Nissan"},
                [],
            ),
            (
                FordAdapter(),
                """<table><tr><th>Code</th><th>Part number</th><th>Name</th><th>Date</th></tr>
                <tr><td>1</td><td>1000314</td><td>Duct</td><td>1995-2002</td></tr></table>
                <div class="coord" name="1" srcTop="1" srcLeft="2" srcWidth="3" srcHeight="4"></div>""",
                {"brand": "Ford"},
                [],
            ),
            (
                VagAdapter(),
                """<table><tr><th></th><th></th><th>part number</th><th>Description</th><th>Remark</th><th>ST</th><th>Model data</th></tr>
                <tr><td>3</td><td></td><td>7E7067027</td><td>Trim</td><td>left</td><td>1</td><td></td></tr>
                <tr><td></td><td></td><td>7E7067027 92W</td><td>Trim grey</td><td>left</td><td></td><td></td></tr></table>
                <div class="coord" name="3" srcTop="1" srcLeft="2" srcWidth="3" srcHeight="4"></div>""",
                {"brand": "Volkswagen"},
                [],
            ),
        ]
        for adapter, html, context, oem_records in samples:
            with self.subTest(adapter=adapter.name):
                parsed = adapter.parse(html)
                document = normalize_page(
                    parsed, context, "https://www.catcar.info/test", oem_records=oem_records
                )
                jsonschema.validate(instance=document, schema=self.schema)


if __name__ == "__main__":
    unittest.main()
