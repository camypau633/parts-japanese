import base64
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from tools.catcar_poc.normalize_toyota_oem_sample import normalize_sample


class ToyotaOemSampleTests(unittest.TestCase):
    def test_preserves_group_row_and_ajax_record_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            group_html = root / "group-1103.html"
            group_html.write_text(
                """
                <table>
                  <tr name="04111" onclick="getArticles(this, 'TOKEN-04111')"><td>04111</td></tr>
                </table>
                <img src="/diagrams/1103.png" class="resize" />
                <div class="coord" srcNum="04111" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
                """,
                encoding="utf-8",
            )
            encoded = base64.b64encode(
                b'catalog==284170||group_id==1103||ProfPeriod==200109200601||sts=={"70":"ENGINE"}'
            ).decode("ascii")
            group_url = "https://www.catcar.info/toyota/?l=" + encoded
            sample = {
                "vehicle": {
                    "make": "Toyota",
                    "model": "Camry",
                    "catalog_id": "284170",
                    "modification": "ACV30-AEPNK",
                    "engine": "2AZFE",
                },
                "sampled_groups": [{
                    "url": group_url,
                    "group_id": "1103",
                    "label_raw": "ENGINE",
                    "source_page_file": "group-1103.html",
                    "parts": [{
                        "part_number": "04111",
                        "ajax_http": 200,
                        "ajax_url": "https://www.catcar.info/toyota/?l=ajax-token",
                        "source_page_file": "part-04111.html",
                        "source_status": "available",
                        "records": [
                            {"oem": "04111-28130", "period": "09/2001-11/2002", "applicability": "2AZFE..ACV3#"},
                            {"oem": "04111-28131", "period": "09/2001-11/2002", "applicability": "2AZFE..ACV3#"},
                        ],
                    }],
                }],
            }
            schema = {
                "type": "object",
                "properties": {
                    "schema_version": {"const": "0.1-draft"},
                    "source": {"type": "object"},
                    "catalog_context": {"type": "object"},
                    "parts": {"type": "array"},
                    "oem_records": {"type": "array"},
                    "diagrams": {"type": "array"},
                    "hotspots": {"type": "array"},
                    "validation": {"type": "object"},
                },
                "required": [
                    "schema_version", "source", "catalog_context", "parts",
                    "oem_records", "diagrams", "hotspots", "validation",
                ],
            }

            documents, report = normalize_sample(sample, root, schema)
            self.assertEqual(report["group_count"], 1)
            self.assertEqual(report["part_row_count"], 1)
            self.assertEqual(report["oem_record_count"], 2)
            document = documents[0][1]
            self.assertEqual(document["catalog_context"]["source_group_id"], "1103")
            self.assertEqual(document["catalog_context"]["production_period_raw"], "09/2001-01/2006")
            self.assertEqual(document["parts"][0]["source_status"], "requires_ajax")
            self.assertEqual(document["oem_records"][0]["source_row_id"], "04111")
            self.assertEqual(document["oem_records"][0]["source_record_order"], 0)
            self.assertEqual(document["oem_records"][0]["source_url"], sample["sampled_groups"][0]["parts"][0]["ajax_url"])
            self.assertEqual(document["diagrams"][0]["source_image_url"], "/diagrams/1103.png")
            self.assertEqual(document["hotspots"][0]["resolution_status"], "matched")
            jsonschema.validate(document, schema)

    def test_rejects_unclassified_empty_ajax_response(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "group-1.html").write_text(
                '<table><tr name="123" onclick="getArticles(this, \'T\')"><td>123</td></tr></table>',
                encoding="utf-8",
            )
            sample = {
                "vehicle": {"make": "Toyota", "model": "Camry", "catalog_id": "1", "modification": "M", "engine": "E"},
                "sampled_groups": [{
                    "url": "https://www.catcar.info/toyota/?l=x",
                    "group_id": "1",
                    "source_page_file": "group-1.html",
                    "parts": [{
                        "part_number": "123",
                        "ajax_http": 200,
                        "ajax_url": "https://www.catcar.info/toyota/?l=y",
                        "source_status": "empty_unclassified",
                        "records": [],
                    }],
                }],
            }
            with self.assertRaisesRegex(ValueError, "empty, unclassified"):
                normalize_sample(sample, root, {})


if __files_never_exists:
    pass
