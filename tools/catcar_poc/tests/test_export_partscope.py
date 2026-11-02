import json
import tempfile
import unittest
from pathlib import Path

from tools.catcar_poc.export_partscope import (\n    document_to_records, export_documents, validate_export_records,\n)


def sample(brand="Nissan"):
    return {
        "source": {"name": "CatCar", "url": "https://www.catcar.info/nissan/catalog"},
        "catalog_context": {
            "brand": brand, "model": "Pixo", "engine_code": "K9K",
            "production_period_raw": "2009-2013",
        },
        "parts": [{
            "source_row_id": "12010S", "diagram_position_code": "12010S",
            "part_number_raw": "12000-4A00A", "description_raw": "PISTON SET",
            "production_period_raw": "03/2009-01/2012", "quantity_raw": "03",
            "source_status": "available",
        }],
        "oem_records": [],
        "diagrams": [{"diagram_id": "diagram-1", "source_image_url": "/diagrams/pixo.png"}],
        "hotspots": [{
            "hotspot_id": "hotspot-1", "source_position_code": "12010S",
            "top_raw": "10", "left_raw": "20", "width_raw": "3", "height_raw": "4",
        }],
    }


class PartScopeExportTests(unittest.TestCase):
    def test_static_nissan_row_maps_to_factory_parts(self):
        records = document_to_records(sample())
        record = records["120004A00A"]
        self.assertEqual(record["brand"], "Nissan")
        self.assertEqual(record["factory_parts"][0]["sku"], "12000-4A00A")
        self.assertEqual(record["factory_parts"][0]["position"], "12010S")
        self.assertEqual(record["factory_parts"][0]["quantity"], "03")
        self.assertEqual(record["analogs"], [])
        self.assertEqual(record["specifications"], [])
        self.assertEqual(record["diagram"]["diagramUrl"], "https://www.catcar.info/diagrams/pixo.png")
        self.assertEqual(record["diagram"]["hotspots"], [])

    def test_toyota_ajax_oem_variants_link_to_catalogue_row(self):
        doc = sample("Toyota")
        doc["catalog_context"]["model"] = "Camry"
        doc["catalog_context"]["group_label_raw"] = "ФИЛЬТР МАСЛЯНЫЙ"
        doc["diagrams"] = [{"diagram_id": "diagram-1", "source_image_url": "http://ci.catcar.info/toyota_2017_04/japan/./150397 .png"}]
        doc["parts"] = [{
            "source_row_id": "15600A", "diagram_position_code": "15600A",
            "part_number_raw": None, "description_raw": "",
            "production_period_raw": "", "quantity_raw": "",
            "source_status": "requires_ajax",
        }]
        doc["oem_records"] = [
            {"source_row_id": "15600A", "oem_number_raw": "90915-YZZE1",
             "production_period_raw": "2001-2006", "applicability_raw": "1AZ-FE",
             "source_status": "available"},
            {"source_row_id": "15600A", "oem_number_raw": "90915-YZZE2",
             "production_period_raw": "2006-", "applicability_raw": "2AZ-FE",
             "source_status": "available"},
            {"source_row_id": "15600A", "oem_number_raw": None,
             "source_status": "no_applicable_data"},
        ]
        records = document_to_records(doc)
        self.assertEqual(set(records), {"90915YZZE1", "90915YZZE2"})
        self.assertEqual(records["90915YZZE1"]["name"], "ФИЛЬТР МАСЛЯНЫЙ")
        self.assertEqual(records["90915YZZE1"]["factory_parts"][0]["name"], "ФИЛЬТР МАСЛЯНЫЙ")
        self.assertEqual(records["90915YZZE1"]["diagram"]["diagramUrl"],
                         "https://ci.catcar.info/toyota_2017_04/japan/150397%20.png")
        self.assertEqual(records["90915YZZE1"]["factory_parts"][0]["position"], "15600A")
        self.assertEqual(records["90915YZZE1"]["factory_parts"][0]["applicability"], "1AZ-FE")
        self.assertEqual(records["90915YZZE2"]["factory_parts"][0]["production_period"], "2006-")

    def test_export_validator_reports_provenance_and_context_coverage(self):
        records = document_to_records(sample())
        report = validate_export_records(records)
        self.assertTrue(report["validation_passed"])
        self.assertEqual(report["records_validated"], 1)
        self.assertEqual(report["factory_parts_validated"], 1)
        self.assertEqual(report["records_by_brand"], {"Nissan": 1})
        self.assertEqual(report["records_with_compatibility_years"], 1)
        self.assertEqual(report["records_with_engine"], 1)
        self.assertEqual(report["records_with_diagram_url"], 1)

    def test_export_validator_rejects_factory_sku_mismatch(self):
        records = document_to_records(sample())
        records["120004A00A"]["factory_parts"][0]["sku"] = "99999"
        with self.assertRaisesRegex(ValueError, "does not match record SKU"):
            validate_export_records(records)

    def test_export_validator_rejects_missing_factory_provenance(self):
        records = document_to_records(sample())
        records["120004A00A"]["factory_parts"][0]["source_url"] = ""
        with self.assertRaisesRegex(ValueError, "missing source provenance"):
            validate_export_records(records)

    def test_non_japanese_research_brand_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not enabled"):
            document_to_records(sample("Ford"))

    def test_export_creates_two_character_shard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "normalized.json"
            source.write_text(json.dumps(sample()), encoding="utf-8")
            output = root / "out"
            report = export_documents([source], output)
            self.assertEqual(report["records_exported"], 1)
            shard = json.loads((output / "12.json").read_text(encoding="utf-8"))
            self.assertIn("120004A00A", shard)
            self.assertTrue((output / "export-report.json").exists())

    def test_export_refuses_nonempty_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "normalized.json"
            source.write_text(json.dumps(sample()), encoding="utf-8")
            output = root / "out"
            output.mkdir()
            (output / "stale.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                export_documents([source], output)


if __name__ == "__main__":
    unittest.main()
