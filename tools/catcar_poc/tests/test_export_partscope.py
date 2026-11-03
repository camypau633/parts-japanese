import json
import tempfile
import unittest
from pathlib import Path

from tools.catcar_poc.export_partscope import (
    document_to_records, export_documents, validate_export_records, validate_geometry_report,
)


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


def verified_geometry(urls):
    return {
        "coordinate_script": {
            "relevant_snippets": [
                "srcTop srcLeft srcWidth srcHeight h/nh w/nw",
            ],
        },
        "main_css": {
            "relevant_snippets": [".resize { width:100%; height:100%; }"],
        },
        "images": [
            {
                "image_url": url,
                "http_status": 206,
                "content_type": "image/png",
                "image_dimensions": {"width": 760, "height": 1112},
                "hotspot_count": 1,
                "all_hotspot_boxes_inside_image_bounds": True,
            }
            for url in urls
        ],
    }


def toyota_group_document(group_id, position, image_path):
    return {
        "source": {"name": "CatCar", "url": "https://www.catcar.info/toyota/group/%s" % group_id},
        "catalog_context": {
            "brand": "Toyota", "model": "Camry", "engine_code": "2AZFE",
            "production_period_raw": "09/2001-01/2006",
            "source_group_id": group_id, "group_label_raw": "ENGINE GROUP",
        },
        "parts": [{
            "source_row_id": position, "diagram_position_code": position,
            "part_number_raw": None, "description_raw": "PART " + position,
            "production_period_raw": "", "quantity_raw": "",
            "source_status": "requires_ajax",
        }],
        "oem_records": [{
            "source_row_id": position, "oem_number_raw": "11310-28071",
            "production_period_raw": "09/2005-01/2006",
            "applicability_raw": "2AZFE..ACV3#", "source_status": "available",
            "source_group_id": group_id, "source_record_order": 0,
            "source_url": "https://www.catcar.info/toyota/ajax/%s" % position,
        }],
        "diagrams": [{"diagram_id": "diagram-1", "source_image_url": image_path}],
        "hotspots": [{
            "hotspot_id": "hotspot-1", "diagram_id": "diagram-1",
            "source_position_code": position, "source_row_id": position,
            "source_row_ids": [position], "top_raw": "10", "left_raw": "20",
            "width_raw": "40", "height_raw": "20", "resolution_status": "matched",
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

    def test_verified_nissan_hotspot_uses_natural_image_pixel_centres(self):
        doc = sample()
        doc["hotspots"][0].update({
            "diagram_id": "diagram-1",
            "source_row_id": "12010S",
            "source_row_ids": ["12010S"],
            "resolution_status": "matched",
        })
        url = "https://www.catcar.info/diagrams/pixo.png"
        geometry = validate_geometry_report(verified_geometry([url]))
        records = document_to_records(doc, geometry_index=geometry)
        hotspot = records["120004A00A"]["diagram"]["hotspots"][0]
        self.assertEqual(hotspot["id"], "12010S")
        self.assertEqual(hotspot["x"], 21.5)
        self.assertEqual(hotspot["y"], 12.0)
        self.assertEqual(hotspot["oem"], "12000-4A00A")
        self.assertIn("03/2009-01/2012", hotspot["details"])
        report = validate_export_records(records)
        self.assertEqual(report["hotspots_validated"], 1)

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
             "source_status": "available", "source_group_id": "1502",
             "source_record_order": 0, "source_url": "https://www.catcar.info/toyota/?l=ajax-token"},
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
        self.assertEqual(records["90915YZZE1"]["factory_parts"][0]["source_group_id"], "1502")
        self.assertEqual(records["90915YZZE1"]["factory_parts"][0]["source_record_order"], 0)
        self.assertEqual(records["90915YZZE1"]["factory_parts"][0]["source_url"], "https://www.catcar.info/toyota/?l=ajax-token")
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

    def test_verified_toyota_hotspot_uses_natural_image_pixel_centres(self):
        doc = toyota_group_document("1103", "04111", "/diagrams/camry.png")
        url = "https://www.catcar.info/diagrams/camry.png"
        geometry = validate_geometry_report(verified_geometry([url]))
        records = document_to_records(doc, geometry_index=geometry)
        hotspot = records["1131028071"]["diagram"]["hotspots"][0]
        self.assertEqual(hotspot["id"], "04111")
        self.assertEqual(hotspot["x"], 40.0)
        self.assertEqual(hotspot["y"], 20.0)
        self.assertEqual(hotspot["radius"], 28)
        self.assertEqual(hotspot["oem"], "11310-28071")
        self.assertIn("09/2005-01/2006", hotspot["details"])
        report = validate_export_records(records)
        self.assertEqual(report["hotspots_validated"], 1)

    def test_hotspot_lists_are_not_shared_between_different_skus(self):
        doc = toyota_group_document("1103", "04111", "/diagrams/camry.png")
        doc["oem_records"].append({
            "source_row_id": "04111", "oem_number_raw": "11310-28072",
            "production_period_raw": "01/2006-", "applicability_raw": "2AZFE",
            "source_status": "available", "source_group_id": "1103",
            "source_record_order": 1, "source_url": "https://www.catcar.info/toyota/ajax/04111b",
        })
        geometry = validate_geometry_report(verified_geometry(["https://www.catcar.info/diagrams/camry.png"]))
        records = document_to_records(doc, geometry_index=geometry)
        first = records["1131028071"]["diagram"]["hotspots"]
        second = records["1131028072"]["diagram"]["hotspots"]
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(first[0]["oem"], "11310-28071")
        self.assertEqual(second[0]["oem"], "11310-28072")
        self.assertIsNot(first, second)

    def test_same_sku_in_different_groups_exports_separate_diagram_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "group-1104.json"
            second = root / "group-1106.json"
            first_doc = toyota_group_document("1104", "11101", "/diagrams/engine-head.png")
            second_doc = toyota_group_document("1106", "11302", "/diagrams/timing-cover.png")
            first.write_text(json.dumps(first_doc), encoding="utf-8")
            second.write_text(json.dumps(second_doc), encoding="utf-8")
            geometry = verified_geometry([
                "https://www.catcar.info/diagrams/engine-head.png",
                "https://www.catcar.info/diagrams/timing-cover.png",
            ])
            output = root / "out"
            report = export_documents([first, second], output, geometry_report=geometry)
            self.assertEqual(report["records_exported"], 2)
            self.assertEqual(report["unique_skus_exported"], 1)
            self.assertEqual(report["hotspots_exported"], 2)
            shard = json.loads((output / "11.json").read_text(encoding="utf-8"))
            variants = shard["1131028071"]
            self.assertIsInstance(variants, list)
            self.assertEqual(len(variants), 2)
            self.assertEqual({item["part_id"] for item in variants}, {"toyota:1131028071:1104", "toyota:1131028071:1106"})
            self.assertEqual({item["diagram"]["diagramUrl"] for item in variants}, {
                "https://www.catcar.info/diagrams/engine-head.png",
                "https://www.catcar.info/diagrams/timing-cover.png",
            })
            self.assertEqual({item["diagram"]["hotspots"][0]["id"] for item in variants}, {"11101", "11302"})

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
