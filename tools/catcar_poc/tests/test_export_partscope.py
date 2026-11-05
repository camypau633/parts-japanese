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
    def test_all_japanese_catalog_brands_are_exportable(self):
        for brand in ("Toyota", "Lexus", "Nissan", "Infiniti", "Honda",
                      "Suzuki", "Mazda", "Mitsubishi", "Isuzu", "Subaru"):
            with self.subTest(brand=brand):
                records = document_to_records(sample(brand))
                self.assertEqual(records["120004A00A"]["brand"], brand)

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


    def test_honda_static_export_preserves_option_variants_and_repeated_hotspots(self):
        document = {
            "source": {"name": "CatCar", "url": "https://www.catcar.info/honda/accord/e1"},
            "catalog_context": {
                "brand": "Honda", "model": "Accord", "model_year": "2011",
                "region": "Austria (KW)", "transmission": "5AT", "grade": "2.0EX",
                "source_group_id": "E-1",
            },
            "parts": [
                {"source_row_id": "6", "diagram_position_code": "1", "part_number_raw": "16400-RL2-G01",
                 "description_raw": "THROTTLE BODY, ELECTRONIC CONTROL(GMD2B)", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH SR STL"}},
                {"source_row_id": "7", "diagram_position_code": "1", "part_number_raw": "16400-RL2-G01",
                 "description_raw": "THROTTLE BODY, ELECTRONIC CONTROL(GMD2B)", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH STL"}},
                {"source_row_id": "8", "diagram_position_code": "2", "part_number_raw": "36162-RNA-A01",
                 "description_raw": "VALVE ASSY., PURGE CONTROL SOLENOID", "additional_source_fields": {}},
                {"source_row_id": "9", "diagram_position_code": "3", "part_number_raw": "37835-PGK-A01",
                 "description_raw": "O-RING", "additional_source_fields": {}},
                {"source_row_id": "10", "diagram_position_code": "4", "part_number_raw": "90012-RNA-A00",
                 "description_raw": "BOLT-WASHER, 8X55", "additional_source_fields": {}},
                {"source_row_id": "11", "diagram_position_code": "5", "part_number_raw": "90020-RNA-A01",
                 "description_raw": "BOLT-WASHER, 5X20", "additional_source_fields": {}},
            ],
            "oem_records": [],
            "diagrams": [{"diagram_id": "diagram-1", "source_image_url": "http://ci.catcar.info/honda/euro/18TA0801/IMGE/E__0100.png"}],
            "hotspots": [
                {"hotspot_id": "hotspot-1", "diagram_id": "diagram-1", "source_position_code": "1", "source_row_ids": ["6", "7"], "top_raw": "792", "left_raw": "1147", "width_raw": "18", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "hotspot-2", "diagram_id": "diagram-1", "source_position_code": "2", "source_row_ids": ["8"], "top_raw": "265", "left_raw": "1009", "width_raw": "25", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "hotspot-3", "diagram_id": "diagram-1", "source_position_code": "3", "source_row_ids": ["9"], "top_raw": "361", "left_raw": "974", "width_raw": "26", "height_raw": "30", "resolution_status": "matched"},
                {"hotspot_id": "hotspot-4", "diagram_id": "diagram-1", "source_position_code": "4", "source_row_ids": ["10"], "top_raw": "26", "left_raw": "1526", "width_raw": "26", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "hotspot-5", "diagram_id": "diagram-1", "source_position_code": "4", "source_row_ids": ["10"], "top_raw": "119", "left_raw": "1371", "width_raw": "26", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "hotspot-6", "diagram_id": "diagram-1", "source_position_code": "4", "source_row_ids": ["10"], "top_raw": "135", "left_raw": "1625", "width_raw": "26", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "hotspot-7", "diagram_id": "diagram-1", "source_position_code": "4", "source_row_ids": ["10"], "top_raw": "198", "left_raw": "1508", "width_raw": "26", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "hotspot-8", "diagram_id": "diagram-1", "source_position_code": "5", "source_row_ids": ["11"], "top_raw": "213", "left_raw": "1235", "width_raw": "25", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "hotspot-9", "diagram_id": "diagram-1", "source_position_code": "5", "source_row_ids": ["11"], "top_raw": "240", "left_raw": "1173", "width_raw": "25", "height_raw": "29", "resolution_status": "matched"},
            ],
        }
        image_url = "https://ci.catcar.info/honda/euro/18TA0801/IMGE/E__0100.png"
        geometry = verified_geometry([image_url])
        geometry["images"][0].update({
            "http_status": 200,
            "content_type": "image/png",
            "image_dimensions": {"width": 1920, "height": 959},
            "hotspot_count": 9,
            "all_hotspot_boxes_inside_image_bounds": True,
        })
        geometry_index = validate_geometry_report(geometry)
        records = document_to_records(document, geometry_index=geometry_index)
        self.assertEqual(set(records), {
            "16400RL2G01", "36162RNAA01", "37835PGKA01", "90012RNAA00", "90020RNAA01"
        })
        throttle = records["16400RL2G01"]
        self.assertEqual(len(throttle["factory_parts"]), 2)
        self.assertNotEqual(
            throttle["factory_parts"][0]["source_fields"]["option_codes_raw"],
            throttle["factory_parts"][1]["source_fields"]["option_codes_raw"],
        )
        self.assertEqual(throttle["compatibility"][0]["years"], "2011")
        self.assertEqual(throttle["compatibility"][0]["engine"], "")
        self.assertEqual(len(throttle["diagram"]["hotspots"]), 1)
        self.assertEqual(len(records["90012RNAA00"]["diagram"]["hotspots"]), 4)
        self.assertEqual(len(records["90020RNAA01"]["diagram"]["hotspots"]), 2)
        report = validate_export_records(records)
        self.assertEqual(report["records_by_brand"], {"Honda": 5})
        self.assertEqual(report["factory_parts_validated"], 6)
        self.assertEqual(report["hotspots_validated"], 9)

    def test_honda_b22_export_maps_multiple_oems_at_one_position(self):
        document = {
            "source": {"name": "CatCar", "url": "https://www.catcar.info/honda/accord/b22"},
            "catalog_context": {
                "brand": "Honda", "model": "Accord", "model_year": "2011",
                "region": "Austria (KW)", "transmission": "5AT", "grade": "2.0EX",
                "source_group_id": "B-22",
            },
            "parts": [
                {"source_row_id": "6", "diagram_position_code": "5", "part_number_raw": "44300-TA0-A61",
                 "description_raw": "BEARING ASSY., FR. HUB", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH SR STL"}},
                {"source_row_id": "7", "diagram_position_code": "5", "part_number_raw": "44300-TA0-A61",
                 "description_raw": "BEARING ASSY., FR. HUB", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH STL"}},
                {"source_row_id": "8", "diagram_position_code": "18", "part_number_raw": "90113-S84-901",
                 "description_raw": "BOLT, WHEEL (ROCKNEL FASTENER)", "additional_source_fields": {}},
                {"source_row_id": "9", "diagram_position_code": "18", "part_number_raw": "90113-SD4-901",
                 "description_raw": "BOLT, WHEEL (MEIRA)", "additional_source_fields": {}},
                {"source_row_id": "10", "diagram_position_code": "18", "part_number_raw": "90113-SD4-902",
                 "description_raw": "BOLT, WHEEL (SAGA)", "additional_source_fields": {}},
                {"source_row_id": "11", "diagram_position_code": "18", "part_number_raw": "90113-SJK-901",
                 "description_raw": "BOLT, WHEEL (THAI MEIRA)", "additional_source_fields": {}},
                {"source_row_id": "12", "diagram_position_code": "12", "part_number_raw": "45240-SM4-003",
                 "description_raw": "BOLT, FLANGE, 10X24", "additional_source_fields": {}},
                {"source_row_id": "13", "diagram_position_code": "13", "part_number_raw": "45251-TA1-A00",
                 "description_raw": "DISK, FR. BRAKE", "additional_source_fields": {}},
            ],
            "oem_records": [],
            "diagrams": [{"diagram_id": "diagram-1", "source_image_url": "http://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2200.png"}],
            "hotspots": [
                {"hotspot_id": "h5", "diagram_id": "diagram-1", "source_position_code": "5", "source_row_ids": ["6", "7"],
                 "top_raw": "151", "left_raw": "1197", "width_raw": "26", "height_raw": "28", "resolution_status": "matched"},
                {"hotspot_id": "h18", "diagram_id": "diagram-1", "source_position_code": "18", "source_row_ids": ["8", "9", "10", "11"],
                 "top_raw": "246", "left_raw": "1353", "width_raw": "40", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "h12a", "diagram_id": "diagram-1", "source_position_code": "12", "source_row_ids": ["12"],
                 "top_raw": "632", "left_raw": "1126", "width_raw": "40", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "h12b", "diagram_id": "diagram-1", "source_position_code": "12", "source_row_ids": ["12"],
                 "top_raw": "884", "left_raw": "1121", "width_raw": "43", "height_raw": "34", "resolution_status": "matched"},
                {"hotspot_id": "h13a", "diagram_id": "diagram-1", "source_position_code": "13", "source_row_ids": ["13"],
                 "top_raw": "548", "left_raw": "364", "width_raw": "40", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "h13b", "diagram_id": "diagram-1", "source_position_code": "13", "source_row_ids": ["13"],
                 "top_raw": "848", "left_raw": "403", "width_raw": "40", "height_raw": "29", "resolution_status": "matched"},
            ],
        }
        image_url = "https://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2200.png"
        geometry = verified_geometry([image_url])
        geometry["images"][0].update({
            "http_status": 200,
            "content_type": "image/png",
            "image_dimensions": {"width": 1920, "height": 959},
            "hotspot_count": 23,
            "all_hotspot_boxes_inside_image_bounds": True,
        })
        records = document_to_records(document, geometry_index=validate_geometry_report(geometry))
        self.assertEqual(len(records["44300TA0A61"]["factory_parts"]), 2)
        self.assertNotEqual(
            records["44300TA0A61"]["factory_parts"][0]["source_fields"]["option_codes_raw"],
            records["44300TA0A61"]["factory_parts"][1]["source_fields"]["option_codes_raw"],
        )
        wheel_bolt_skus = ["90113S84-901", "90113SD4-901", "90113SD4-902", "90113SJK-901"]
        for sku in wheel_bolt_skus:
            normalized = sku.replace("-", "")
            self.assertEqual(len(records[normalized]["diagram"]["hotspots"]), 1)
        self.assertEqual(len(records["45240SM4003"]["diagram"]["hotspots"]), 2)
        self.assertEqual(len(records["45251TA1A00"]["diagram"]["hotspots"]), 2)
        report = validate_export_records(records)
        self.assertEqual(report["records_by_brand"], {"Honda": 7})
        self.assertEqual(report["factory_parts_validated"], 8)
        self.assertEqual(report["hotspots_validated"], 9)

    def test_honda_b28_export_preserves_duplicate_option_rows_and_diagram_geometry(self):
        document = {
            "source": {"name": "CatCar", "url": "https://www.catcar.info/honda/accord/b28"},
            "catalog_context": {
                "brand": "Honda", "model": "Accord", "model_year": "2011",
                "region": "Austria (KW)", "transmission": "5AT", "grade": "2.0EX",
                "source_group_id": "B-28",
            },
            "parts": [
                {"source_row_id": "1", "diagram_position_code": "1", "part_number_raw": "51401-TA0-A13",
                 "description_raw": "SPRING, FR.", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH SR STL"}},
                {"source_row_id": "2", "diagram_position_code": "1", "part_number_raw": "51401-TA0-A13",
                 "description_raw": "SPRING, FR.", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH STL"}},
                {"source_row_id": "3", "diagram_position_code": "2", "part_number_raw": "51610-TA0-P15",
                 "description_raw": "ABSORBER ASSY., R. FR. SHOCK", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH"}},
                {"source_row_id": "4", "diagram_position_code": "7", "part_number_raw": "51605-TA0-A01",
                 "description_raw": "BASE, FR. SHOCK ABSORBER", "additional_source_fields": {}},
            ],
            "oem_records": [],
            "diagrams": [{"diagram_id": "diagram-1", "source_image_url": "http://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2800.png"}],
            "hotspots": [
                {"hotspot_id": "hotspot-1", "diagram_id": "diagram-1", "source_position_code": "1",
                 "source_row_ids": ["1", "2"], "top_raw": "701", "left_raw": "806",
                 "width_raw": "18", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "hotspot-2", "diagram_id": "diagram-1", "source_position_code": "7",
                 "source_row_ids": ["4"], "top_raw": "105", "left_raw": "715",
                 "width_raw": "25", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "hotspot-3", "diagram_id": "diagram-1", "source_position_code": "7",
                 "source_row_ids": ["4"], "top_raw": "415", "left_raw": "729",
                 "width_raw": "25", "height_raw": "29", "resolution_status": "matched"},
            ],
        }
        image_url = "https://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2800.png"
        geometry = verified_geometry([image_url])
        geometry["images"][0].update({
            "http_status": 200,
            "content_type": "image/png",
            "image_dimensions": {"width": 1920, "height": 959},
            "hotspot_count": 20,
            "all_hotspot_boxes_inside_image_bounds": True,
        })
        records = document_to_records(document, geometry_index=validate_geometry_report(geometry))
        spring = records["51401TA0A13"]
        self.assertEqual(len(spring["factory_parts"]), 2)
        self.assertNotEqual(
            spring["factory_parts"][0]["source_fields"]["option_codes_raw"],
            spring["factory_parts"][1]["source_fields"]["option_codes_raw"],
        )
        self.assertEqual(spring["compatibility"][0]["years"], "2011")
        self.assertEqual(spring["compatibility"][0]["engine"], "")
        self.assertEqual(records["51605TA0A01"]["diagram"]["diagramUrl"],
                         "https://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2800.png")
        self.assertEqual(len(records["51605TA0A01"]["diagram"]["hotspots"]), 2)
        report = validate_export_records(records)
        self.assertEqual(report["records_by_brand"], {"Honda": 3})
        self.assertEqual(report["factory_parts_validated"], 4)
        self.assertEqual(report["hotspots_validated"], 3)

    def test_honda_b2710_export_preserves_three_option_variant_pairs(self):
        document = {
            "source": {"name": "CatCar", "url": "https://www.catcar.info/honda/accord/b27-10"},
            "catalog_context": {
                "brand": "Honda", "model": "Accord", "model_year": "2011",
                "region": "Austria (KW)", "transmission": "5AT", "grade": "2.0EX",
                "source_group_id": "B-27-10",
            },
            "parts": [
                {"source_row_id": "6", "diagram_position_code": "3", "part_number_raw": "51300-TA0-A01",
                 "description_raw": "SPRING, FR. STABILIZER", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH SR STL"}},
                {"source_row_id": "7", "diagram_position_code": "3", "part_number_raw": "51300-TA0-A01",
                 "description_raw": "SPRING, FR. STABILIZER", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH STL"}},
                {"source_row_id": "8", "diagram_position_code": "4", "part_number_raw": "51306-TA0-A01",
                 "description_raw": "BUSH, FR. STABILIZER HOLDER", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH SR STL"}},
                {"source_row_id": "9", "diagram_position_code": "4", "part_number_raw": "51306-TA0-A01",
                 "description_raw": "BUSH, FR. STABILIZER HOLDER", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH STL"}},
                {"source_row_id": "10", "diagram_position_code": "9", "part_number_raw": "51360-TA0-000",
                 "description_raw": "ARM COMP., L. FR. LOWER", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH SR STL"}},
                {"source_row_id": "11", "diagram_position_code": "9", "part_number_raw": "51360-TA0-000",
                 "description_raw": "ARM COMP., L. FR. LOWER", "additional_source_fields": {"option_codes_raw": "AB3 ABS LH STL"}},
            ],
            "oem_records": [],
            "diagrams": [{"diagram_id": "diagram-1", "source_image_url": "http://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2710.png"}],
            "hotspots": [
                {"hotspot_id": "h3", "diagram_id": "diagram-1", "source_position_code": "3", "source_row_ids": ["6", "7"],
                 "top_raw": "211", "left_raw": "362", "width_raw": "25", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "h4", "diagram_id": "diagram-1", "source_position_code": "4", "source_row_ids": ["8", "9"],
                 "top_raw": "379", "left_raw": "867", "width_raw": "26", "height_raw": "29", "resolution_status": "matched"},
                {"hotspot_id": "h9", "diagram_id": "diagram-1", "source_position_code": "9", "source_row_ids": ["10", "11"],
                 "top_raw": "689", "left_raw": "508", "width_raw": "26", "height_raw": "29", "resolution_status": "matched"},
            ],
        }
        image_url = "https://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2710.png"
        geometry = verified_geometry([image_url])
        geometry["images"][0].update({
            "http_status": 200,
            "content_type": "image/png",
            "image_dimensions": {"width": 1920, "height": 959},
            "hotspot_count": 20,
            "all_hotspot_boxes_inside_image_bounds": True,
        })
        records = document_to_records(document, geometry_index=validate_geometry_report(geometry))
        self.assertEqual(set(records), {"51300TA0A01", "51306TA0A01", "51360TA0000"})
        for sku in ("51300TA0A01", "51306TA0A01", "51360TA0000"):
            record = records[sku]
            self.assertEqual(len(record["factory_parts"]), 2)
            self.assertNotEqual(
                record["factory_parts"][0]["source_fields"]["option_codes_raw"],
                record["factory_parts"][1]["source_fields"]["option_codes_raw"],
            )
            self.assertEqual(record["compatibility"][0]["years"], "2011")
            self.assertEqual(len(record["diagram"]["hotspots"]), 1)
        report = validate_export_records(records)
        self.assertEqual(report["records_by_brand"], {"Honda": 3})
        self.assertEqual(report["factory_parts_validated"], 6)
        self.assertEqual(report["hotspots_validated"], 3)

    def test_honda_same_oem_across_groups_remains_two_partscope_candidates(self):
        image_a = "https://ci.catcar.info/honda/euro/18TA0801/IMGE/E__0100.png"
        image_b = "https://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2710.png"

        def group_document(group_id, image_url, position, row_id, description):
            return {
                "source": {"name": "CatCar", "url": "https://www.catcar.info/honda/accord/" + group_id.lower()},
                "catalog_context": {
                    "brand": "Honda", "model": "Accord", "model_year": "2011",
                    "region": "Austria (KW)", "transmission": "5AT", "grade": "2.0EX",
                    "source_group_id": group_id,
                },
                "parts": [{
                    "source_row_id": row_id, "diagram_position_code": position,
                    "part_number_raw": "51300-TA0-A01", "description_raw": description,
                    "additional_source_fields": {"option_codes_raw": "AB3 ABS LH STL"},
                }],
                "oem_records": [],
                "diagrams": [{"diagram_id": "diagram-1", "source_image_url": image_url}],
                "hotspots": [{
                    "hotspot_id": "hotspot-" + group_id, "diagram_id": "diagram-1",
                    "source_position_code": position, "source_row_ids": [row_id],
                    "top_raw": "100", "left_raw": "200", "width_raw": "25", "height_raw": "29",
                    "resolution_status": "matched",
                }],
            }

        geometry = validate_geometry_report(verified_geometry([image_a, image_b]))
        documents = [
            group_document("B-27-10", "http://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2710.png",
                           "3", "6", "SPRING, FR. STABILIZER"),
            group_document("E-1", "http://ci.catcar.info/honda/euro/18TA0801/IMGE/E__0100.png",
                           "1", "6", "THROTTLE BODY"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = []
            for index, document in enumerate(documents):
                path = root / ("group-%s.json" % index)
                path.write_text(json.dumps(document), encoding="utf-8")
                inputs.append(path)
            output = root / "out"
            report = export_documents(inputs, output, geometry_report={
                "coordinate_script": {"relevant_snippets": ["srcTop srcLeft srcWidth srcHeight h/nh w/nw"]},
                "main_css": {"relevant_snippets": [".resize { width:100%; height:100%; }"]},
                "images": [
                    {"image_url": image_a, "http_status": 200, "content_type": "image/png",
                     "image_dimensions": {"width": 1920, "height": 959}, "hotspot_count": 20,
                     "all_hotspot_boxes_inside_image_bounds": True},
                    {"image_url": image_b, "http_status": 200, "content_type": "image/png",
                     "image_dimensions": {"width": 1920, "height": 959}, "hotspot_count": 20,
                     "all_hotspot_boxes_inside_image_bounds": True},
                ],
            })
            shard = json.loads((output / "51.json").read_text(encoding="utf-8"))
        candidates = shard["51300TA0A01"]
        self.assertEqual(len(candidates), 2)
        self.assertEqual({x["part_id"].split(":")[-1] for x in candidates}, {"B-27-10", "E-1"})
        self.assertEqual({x["diagram"]["diagramUrl"] for x in candidates}, {image_a, image_b})
        self.assertTrue(all(len(x["factory_parts"]) == 1 for x in candidates))
        self.assertTrue(all(len(x["diagram"]["hotspots"]) == 1 for x in candidates))
        self.assertEqual(report["documents_read"], 2)
        self.assertEqual(report["unique_skus_exported"], 1)
        self.assertEqual(report["records_exported"], 2)
        self.assertEqual(report["hotspots_exported"], 2)

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


    def test_incomplete_honda_page_is_rejected_before_export(self):
        document = sample("Honda")
        document.setdefault("validation", {})["page_status"] = "incomplete"
        document["validation"]["page_warnings"] = ["no_part_rows_after_honda_header"]
        with self.assertRaisesRegex(ValueError, "Refusing to export incomplete CatCar page"):
            document_to_records(document)

if __name__ == "__main__":
    unittest.main()
