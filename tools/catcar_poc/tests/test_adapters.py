import unittest

from tools.catcar_poc.adapters import (
    ToyotaAdapter, NissanAdapter, HondaAdapter, IsuzuAdapter, MazdaAdapter, SuzukiAdapter, SubaruAdapter, FordAdapter, VagAdapter
)


class AdapterTests(unittest.TestCase):
    def test_toyota_ajax_tokens_and_oem_variations(self):
        html = """
        <table><tr name="15600A" onclick="getArticles(this, 'TOKEN-15600A')"><td>15600A</td><td>OIL FILTER</td></tr></table>
        <div class="coord" srcNum="15600A" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        result = ToyotaAdapter().parse(html)
        self.assertEqual(result["ajax_rows"][0]["ajax_token"], "TOKEN-15600A")
        self.assertEqual(result["parts"][0]["description_raw"], "OIL FILTER")
        self.assertEqual(result["parts"][0]["additional_source_fields"]["raw_cells"], ["15600A", "OIL FILTER"])
        self.assertEqual(result["hotspot_matching"]["matched"], ["15600A"])
        self.assertEqual(result["page_status"], "incomplete")
        self.assertIn("toyota_ajax_lookup_not_implemented", result["page_warnings"])

        ajax = """
        <table>
          <tr><td>SU003-00302</td><td>09/2012-06/2013</td><td>FA20</td></tr>
          <tr><td>SU003-05813</td><td>06/2013-</td><td>FA20</td></tr>
        </table>
        """
        records = ToyotaAdapter.parse_ajax_records(ajax)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["oem_number_raw"], "SU003-00302")

    def test_toyota_ajax_preserves_empty_columns(self):
        ajax = """
        <table>
          <tr><td>OEM number</td><td>Production period</td><td>Applicability</td></tr>
          <tr><td>9151180830</td><td></td><td></td></tr>
          <tr><td>SU003-00302</td><td>09/2012-06/2013</td><td>FA20</td></tr>
        </table>
        """
        records = ToyotaAdapter.parse_ajax_records(ajax, source_row_id="ROW-1")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["source_row_id"], "ROW-1")
        self.assertEqual(records[0]["oem_number_raw"], "9151180830")
        self.assertIsNone(records[0]["production_period_raw"])
        self.assertIsNone(records[0]["applicability_raw"])
        self.assertEqual(records[1]["production_period_raw"], "09/2012-06/2013")
        self.assertEqual(records[0]["source_status"], "available")

    def test_toyota_no_applicable_data_is_preserved_as_status(self):
        records = ToyotaAdapter.parse_ajax_records("No applicable data!", source_row_id="12321A")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source_row_id"], "12321A")
        self.assertEqual(records[0]["source_status"], "no_applicable_data")
        self.assertIsNone(records[0]["oem_number_raw"])

    def test_nissan_static_table_and_srcnum(self):
        html = """
        <table>
          <tr><th>№</th><th>Номер детали</th><th>Название</th><th>Дата производства</th><th>Альтернатива</th><th>Количество</th></tr>
          <tr><td>12010S</td><td>12000-4A00A</td><td>PISTON SET</td><td>03/2009-01/2012</td><td>ALT-12000</td><td>03</td></tr>
        </table>
        <div class="coord" srcNum="12010S" srcTop="1" srcLeft="2" srcWidth="3" srcHeight="4"></div>
        """
        result = NissanAdapter().parse(html)
        self.assertEqual(result["parts"][0]["part_number_raw"], "12000-4A00A")
        self.assertEqual(result["parts"][0]["alternative_number_raw"], "ALT-12000")
        self.assertEqual(result["parts"][0]["additional_source_fields"]["raw_cells"][4], "ALT-12000")
        self.assertEqual(result["parts"][0]["additional_source_fields"]["raw_cells"][5], "03")
        self.assertEqual(result["hotspot_matching"]["matched"], ["12010S"])
        self.assertEqual(result["page_status"], "incomplete")
        self.assertIn("no_diagram_image", result["page_warnings"])


    def test_honda_accord_real_table_layout_preserves_duplicate_positions_and_options(self):
        html = """
        <table>
          <tr><td>AB3:</td><td>SIDE SRS</td></tr>
          <tr><td>ABS:</td><td>ABS</td></tr>
          <tr><td>LH:</td><td>LEFT-HAND DRIVE</td></tr>
          <tr><td>SR:</td><td>SUNROOF</td></tr>
          <tr><td>STL:</td><td>LEATHER SEAT</td></tr>
          <tr><th>Код</th><th>Артикул</th><th>Описание</th><th>Дополнительная информация</th><th>Опционные коды</th></tr>
          <tr><td>1</td><td>16400-RL2-G01</td><td>THROTTLE BODY, ELECTRONIC CONTROL(GMD2B)</td><td>Производитель автомобиля: JAPAN</td><td>AB3: SIDE SRS ABS: ABS LH: LEFT-HAND DRIVE SR: SUNROOF STL: LEATHER SEAT</td></tr>
          <tr><td>1</td><td>16400-RL2-G01</td><td>THROTTLE BODY, ELECTRONIC CONTROL(GMD2B)</td><td>Производитель автомобиля: JAPAN</td><td>AB3: SIDE SRS ABS: ABS LH: LEFT-HAND DRIVE STL: LEATHER SEAT</td></tr>
          <tr><td>2</td><td>36162-RNA-A01</td><td>VALVE ASSY., PURGE CONTROL SOLENOID</td><td></td><td></td></tr>
          <tr><td>3</td><td>37835-PGK-A01</td><td>O-RING</td><td></td><td></td></tr>
          <tr><td>4</td><td>90012-RNA-A00</td><td>BOLT-WASHER, 8X55</td><td></td><td></td></tr>
          <tr><td>5</td><td>90020-RNA-A01</td><td>BOLT-WASHER, 5X20</td><td></td><td></td></tr>
        </table>
        <img class="resize" src="http://ci.catcar.info/honda/euro/18TA0801/IMGE/E__0100.png">
        <div class="coord" srcNum="1" srcTop="792" srcLeft="1147" srcWidth="18" srcHeight="29"></div>
        <div class="coord" srcNum="2" srcTop="265" srcLeft="1009" srcWidth="25" srcHeight="29"></div>
        <div class="coord" srcNum="3" srcTop="361" srcLeft="974" srcWidth="26" srcHeight="30"></div>
        <div class="coord" srcNum="4" srcTop="26" srcLeft="1526" srcWidth="26" srcHeight="29"></div>
        <div class="coord" srcNum="4" srcTop="119" srcLeft="1371" srcWidth="26" srcHeight="29"></div>
        <div class="coord" srcNum="4" srcTop="135" srcLeft="1625" srcWidth="26" srcHeight="29"></div>
        <div class="coord" srcNum="4" srcTop="198" srcLeft="1508" srcWidth="26" srcHeight="29"></div>
        <div class="coord" srcNum="5" srcTop="213" srcLeft="1235" srcWidth="25" srcHeight="29"></div>
        <div class="coord" srcNum="5" srcTop="240" srcLeft="1173" srcWidth="25" srcHeight="29"></div>
        """
        result = HondaAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 6)
        self.assertEqual(result["parts"][0]["part_number_raw"], "16400-RL2-G01")
        self.assertEqual(result["parts"][1]["part_number_raw"], "16400-RL2-G01")
        self.assertEqual(result["parts"][0]["diagram_position_code"], "1")
        self.assertEqual(result["parts"][0]["additional_source_fields"]["additional_information_raw"],
                         "Производитель автомобиля: JAPAN")
        self.assertIn("AB3: SIDE SRS", result["parts"][0]["additional_source_fields"]["option_codes_raw"])
        self.assertEqual(result["hotspot_matching"]["matched"], ["1", "2", "3", "4", "5"])
        self.assertEqual(len(result["hotspots"]), 9)
        self.assertEqual(sum(x["position_code"] == "4" for x in result["hotspots"]), 4)
        self.assertEqual(sum(x["position_code"] == "5" for x in result["hotspots"]), 2)
        self.assertEqual(len([x for x in result["images"] if x["image_kind"] == "diagram"]), 1)

    def test_honda_b22_front_brake_preserves_shared_position_supplier_variants(self):
        html = """
        <table>
          <tr><td>AB3:</td><td>SIDE SRS</td></tr>
          <tr><td>ABS:</td><td>ABS</td></tr>
          <tr><td>LH:</td><td>LEFT-HAND DRIVE</td></tr>
          <tr><td>SR:</td><td>SUNROOF</td></tr>
          <tr><td>STL:</td><td>LEATHER SEAT</td></tr>
          <tr><th>Код</th><th>Артикул</th><th>Описание</th><th>Дополнительная информация</th><th>Опционные коды</th></tr>
          <tr><td>5</td><td>44300-TA0-A61</td><td>BEARING ASSY., FR. HUB</td><td>Производитель автомобиля: JAPAN</td><td>AB3: SIDE SRS ABS: ABS LH: LEFT-HAND DRIVE SR: SUNROOF STL: LEATHER SEAT</td></tr>
          <tr><td>5</td><td>44300-TA0-A61</td><td>BEARING ASSY., FR. HUB</td><td>Производитель автомобиля: JAPAN</td><td>AB3: SIDE SRS ABS: ABS LH: LEFT-HAND DRIVE STL: LEATHER SEAT</td></tr>
          <tr><td>18</td><td>90113-S84-901</td><td>BOLT, WHEEL (ROCKNEL FASTENER)</td><td></td><td></td></tr>
          <tr><td>18</td><td>90113-SD4-901</td><td>BOLT, WHEEL (MEIRA)</td><td></td><td></td></tr>
          <tr><td>18</td><td>90113-SD4-902</td><td>BOLT, WHEEL (SAGA)</td><td></td><td></td></tr>
          <tr><td>18</td><td>90113-SJK-901</td><td>BOLT, WHEEL (THAI MEIRA)</td><td></td><td></td></tr>
        </table>
        <img class="resize" src="http://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2200.png">
        <div class="coord" srcNum="5" srcTop="151" srcLeft="1197" srcWidth="26" srcHeight="28"></div>
        <div class="coord" srcNum="18" srcTop="246" srcLeft="1353" srcWidth="40" srcHeight="29"></div>
        """
        result = HondaAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 6)
        self.assertEqual([x["part_number_raw"] for x in result["parts"][:2]],
                         ["44300-TA0-A61", "44300-TA0-A61"])
        self.assertNotEqual(
            result["parts"][0]["additional_source_fields"]["option_codes_raw"],
            result["parts"][1]["additional_source_fields"]["option_codes_raw"],
        )
        wheel_bolts = result["parts"][2:]
        self.assertEqual(len(wheel_bolts), 4)
        self.assertEqual({x["diagram_position_code"] for x in wheel_bolts}, {"18"})
        self.assertEqual(len({x["part_number_raw"] for x in wheel_bolts}), 4)
        self.assertEqual(len(result["hotspots"]), 2)
        self.assertEqual(set(result["hotspot_matching"]["matched"]), {"5", "18"})
        self.assertEqual(len([x for x in result["images"] if x["image_kind"] == "diagram"]), 1)

    def test_honda_b28_shock_absorber_rows_keep_option_and_supplier_variants(self):
        html = """
        <table>
          <tr><td>AB3:</td><td>SIDE SRS</td></tr>
          <tr><td>ABS:</td><td>ABS</td></tr>
          <tr><td>LH:</td><td>LEFT-HAND DRIVE</td></tr>
          <tr><td>SR:</td><td>SUNROOF</td></tr>
          <tr><td>STL:</td><td>LEATHER SEAT</td></tr>
          <tr><th>Код</th><th>Артикул</th><th>Описание</th><th>Дополнительная информация</th><th>Опционные коды</th></tr>
          <tr><td>1</td><td>51401-TA0-A13</td><td>SPRING, FR.</td><td>Производитель автомобиля: JAPAN</td><td>AB3: SIDE SRS ABS: ABS LH: LEFT-HAND DRIVE SR: SUNROOF STL: LEATHER SEAT</td></tr>
          <tr><td>1</td><td>51401-TA0-A13</td><td>SPRING, FR.</td><td>Производитель автомобиля: JAPAN</td><td>AB3: SIDE SRS ABS: ABS LH: LEFT-HAND DRIVE STL: LEATHER SEAT</td></tr>
          <tr><td>2</td><td>51610-TA0-P15</td><td>ABSORBER ASSY., R. FR. SHOCK</td><td>Производитель автомобиля: JAPAN</td><td>AB3: SIDE SRS ABS: ABS LH: LEFT-HAND DRIVE SR: SUNROOF STL: LEATHER SEAT</td></tr>
          <tr><td>11</td><td>51685-SH3-014</td><td>PLATE, DUST COVER (SHOWA)</td><td></td><td></td></tr>
          <tr><td>11</td><td>51685-SR0-004</td><td>PLATE, DUST COVER (A.S.I. SHOWA)</td><td></td><td></td></tr>
          <tr><td>16</td><td>51722-SS0-004</td><td>RUBBER, FR. BUMP STOPPER (POLYURETHAN KASEI)</td><td></td><td></td></tr>
          <tr><td>16</td><td>51722-TA5-A01</td><td>RUBBER, FR. BUMP STOPPER (SHOWA)</td><td>Производитель автомобиля: JAPAN</td><td>AB3: SIDE SRS ABS: ABS LH: LEFT-HAND DRIVE SR: SUNROOF STL: LEATHER SEAT</td></tr>
        </table>
        <img class="resize" src="http://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2800.png">
        <div class="coord" srcNum="1" srcTop="701" srcLeft="806" srcWidth="18" srcHeight="29"></div>
        <div class="coord" srcNum="2" srcTop="486" srcLeft="358" srcWidth="25" srcHeight="29"></div>
        <div class="coord" srcNum="7" srcTop="105" srcLeft="715" srcWidth="25" srcHeight="29"></div>
        <div class="coord" srcNum="7" srcTop="415" srcLeft="729" srcWidth="25" srcHeight="29"></div>
        <div class="coord" srcNum="11" srcTop="104" srcLeft="1220" srcWidth="36" srcHeight="29"></div>
        <div class="coord" srcNum="16" srcTop="668" srcLeft="1220" srcWidth="40" srcHeight="30"></div>
        """
        result = HondaAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 7)
        self.assertEqual(result["parts"][0]["part_number_raw"], "51401-TA0-A13")
        self.assertEqual(result["parts"][1]["part_number_raw"], "51401-TA0-A13")
        self.assertNotEqual(
            result["parts"][0]["additional_source_fields"]["option_codes_raw"],
            result["parts"][1]["additional_source_fields"]["option_codes_raw"],
        )
        self.assertEqual(result["parts"][3]["part_number_raw"], "51685-SH3-014")
        self.assertEqual(result["parts"][4]["part_number_raw"], "51685-SR0-004")
        self.assertEqual(result["parts"][5]["part_number_raw"], "51722-SS0-004")
        self.assertEqual(result["parts"][6]["part_number_raw"], "51722-TA5-A01")
        self.assertEqual(len(result["hotspots"]), 6)
        self.assertEqual(sum(x["position_code"] == "7" for x in result["hotspots"]), 2)
        self.assertEqual(len([x for x in result["images"] if x["image_kind"] == "diagram"]), 1)

    def test_honda_b21_part_description_dimension_tokens_are_preserved(self):
        html = """
        <table>
          <tr><th>Код</th><th>Артикул</th><th>Описание</th><th>Дополнительная информация</th><th>Опционные коды</th></tr>
          <tr><td>8</td><td>44319-SE0-000</td><td>SET RING, 28X2.0</td><td></td><td></td></tr>
          <tr><td>15</td><td>44338-SA2-300</td><td>CIRCLIP, 24MM</td><td></td><td></td></tr>
          <tr><td>19</td><td>90102-SF1-000</td><td>BOLT, HEX., 10X1.25</td><td></td><td></td></tr>
        </table>
        <img class="resize" src="https://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2100.png">
        """
        result = HondaAdapter().parse(html)
        descriptions = {x["part_number_raw"]: x["description_raw"] for x in result["parts"]}
        self.assertEqual(descriptions["44319-SE0-000"], "SET RING, 28X2.0")
        self.assertEqual(descriptions["44338-SA2-300"], "CIRCLIP, 24MM")
        self.assertEqual(descriptions["90102-SF1-000"], "BOLT, HEX., 10X1.25")

    def test_honda_header_only_or_unresolved_diagram_page_is_marked_incomplete(self):
        html = """
        <table>
          <tr><td>AB3:</td><td>SIDE SRS</td></tr>
          <tr><td>ABS:</td><td>ABS</td></tr>
          <tr><th>Код</th><th>Артикул</th><th>Описание</th><th>Дополнительная информация</th><th>Опционные коды</th></tr>
        </table>
        <img class="resize" src="/honda/euro/{npl}/IMGE/B__2700.png">
        """
        result = HondaAdapter().parse(html)
        self.assertEqual(result["parts"], [])
        self.assertEqual(result["page_status"], "incomplete")
        self.assertIn("no_part_rows_after_honda_header", result["page_warnings"])
        self.assertIn("diagram_image_url_unresolved", result["page_warnings"])

    def test_honda_valid_part_table_is_marked_complete(self):
        html = """
        <table>
          <tr><th>Код</th><th>Артикул</th><th>Описание</th></tr>
          <tr><td>1</td><td>12345-ABC-001</td><td>TEST PART</td></tr>
        </table>
        <img class="resize" src="https://ci.catcar.info/honda/euro/18TA0801/IMGE/TEST.png">
        """
        result = HondaAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 1)
        self.assertEqual(result["page_status"], "complete")
        self.assertEqual(result["page_warnings"], [])


    def test_isuzu_real_russian_table_preserves_fitment_and_related_groups(self):
        html = """
        <table>
          <tr><th>Код</th><th>Номер детали</th><th>Наименование</th><th>Сторона установки</th><th>Дата производства</th><th>Применяемость</th><th>Дополнительная информация</th><th>Qty</th><th>Связанные подгруппы</th><th></th></tr>
          <tr><td>1</td><td>5-11360-377-1</td><td>PAN ASM; OIL</td><td></td><td>01.1991 - 04.1995</td><td>ABC</td><td></td><td>01</td><td></td><td></td></tr>
          <tr><td>1</td><td>8-94395-608-0</td><td>PAN ASM; OIL</td><td></td><td>05.1995 - 12.1995</td><td>D</td><td>EMISSION SYSTEM FEDERAL REQUIREMENT</td><td>01</td><td>SUBGROUP-42</td><td></td></tr>
        </table>
        <img class="resize" src="https://ci.catcar.info/isuzu_2017_01/data/211/37161.png">
        <div class="coord" srcNum="1" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        result = IsuzuAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 2)
        first = result["parts"][0]
        self.assertEqual(first["part_number_raw"], "5-11360-377-1")
        self.assertEqual(first["production_period_raw"], "01.1991 - 04.1995")
        self.assertEqual(first["additional_source_fields"]["applicability_raw"], "ABC")
        self.assertEqual(result["parts"][1]["additional_source_fields"]["additional_information_raw"],
                         "EMISSION SYSTEM FEDERAL REQUIREMENT")
        self.assertEqual(result["parts"][1]["additional_source_fields"]["related_subgroups_raw"],
                         "SUBGROUP-42")
        self.assertEqual(result["hotspot_matching"]["matched"], ["1"])
        self.assertEqual(result["page_status"], "complete")


    def test_ford_static_table_code_mapping(self):
        html = """
        <table>
          <tr><th>Code</th><th>Part number</th><th>Name</th><th>Production date</th></tr>
          <tr><td>1</td><td>1000314</td><td>Duct - Heater</td><td>01/08/1995 - 23/06/2006</td></tr>
        </table>
        <div class="coord" name="1" srcTop="1" srcLeft="2" srcWidth="3" srcHeight="4"></div>
        """
        result = FordAdapter().parse(html)
        self.assertEqual(result["parts"][0]["diagram_position_code"], "1")
        self.assertEqual(result["hotspot_matching"]["matched"], ["1"])

    def test_vag_continuation_rows_are_not_dropped_or_inherited(self):
        html = """
        <table>
          <tr><th></th><th></th><th>part number</th><th>Description</th><th>Remark</th><th>ST</th><th>Model data</th></tr>
          <tr><td>3</td><td></td><td>7E7067027</td><td>trim for windowsill</td><td>centre left</td><td>1</td><td></td></tr>
          <tr><td></td><td></td><td>7E7067027 92W</td><td>trim for windowsill moonrock grey</td><td>centre left 04.15 - ...</td><td></td><td></td></tr>
          <tr><td>(40)</td><td></td><td>TRANSFER</td><td>see illustration 127-020</td><td></td><td></td><td></td></tr>
        </table>
        <div class="coord" name="3" srcTop="1" srcLeft="2" srcWidth="3" srcHeight="4"></div>
        """
        result = VagAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 3)
        self.assertEqual(result["parts"][0]["diagram_position_code"], "3")
        self.assertEqual(result["parts"][0]["quantity_raw"], "")
        self.assertEqual(result["parts"][0]["additional_source_fields"]["st_raw"], "1")
        self.assertEqual(result["parts"][0]["additional_source_fields"]["raw_cells"][4], "centre left")
        self.assertEqual(result["parts"][1]["row_kind"], "continuation")
        self.assertIsNone(result["parts"][1]["parent_position_code"])
        self.assertEqual(result["hotspot_matching"]["matched"], ["3"])
        self.assertIn("(40)", result["hotspot_matching"]["rows_without_hotspot"])

    def test_vag_group_transition_is_not_misclassified_as_part_number(self):
        html = """
        <table>
          <tr><td>28</td><td></td><td>Переход к группе</td><td>support see illustration, item: 067-050,22</td><td></td><td></td><td></td></tr>
        </table>
        """
        result = VagAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 1)
        item = result["parts"][0]
        self.assertEqual(item["row_kind"], "group_header")
        self.assertEqual(item["source_status"], "unresolved")
        self.assertIsNone(item["part_number_raw"])
        self.assertEqual(item["additional_source_fields"]["entry_type_raw"], "Переход к группе")
        self.assertEqual(item["description_raw"], "support see illustration, item: 067-050,22")


    def test_suzuki_adapter_rejects_page_without_diagram_as_incomplete(self):
        html = """
        <table>
          <tr><th>Code</th><th>Part number</th><th>Name</th><th>Qty</th></tr>
          <tr><td>1</td><td>11402-61880</td><td>GASKET SET, ENGINE</td><td>1</td></tr>
        </table>
        """
        result = SuzukiAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 1)
        self.assertEqual(result["page_status"], "incomplete")
        self.assertIn("no_diagram_image", result["page_warnings"])

    def test_subaru_observed_parts_table_preserves_model_period_and_destination_fields(self):
        html = """
        <table>
          <tr><th>№</th><th>Part number</th><th>Options</th><th>Applicable Models</th><th>Production date</th><th>Note/Destination Code</th><th>Comment</th></tr>
          <tr><td>10100</td><td>10100CA610</td><td>ｴﾝｼﾞﾝ ｱｾﾝﾌﾞﾘ</td><td>25A FB25ASYHAA</td><td>01/08/2016-</td><td>/</td><td></td></tr>
          <tr><td>001</td><td>10921AA231</td><td>GASKET</td><td>25A FB25ASYHAA</td><td>01/08/2016-</td><td>JAPAN</td><td>sample note</td></tr>
        </table>
        <img class="resize" src="https://ci.catcar.info/subaru/japan/B15/IMGE/diagram.png">
        <div class="coord" srcNum="10100" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        result = SubaruAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 2)
        first = result["parts"][0]
        self.assertEqual(first["part_number_raw"], "10100CA610")
        self.assertEqual(first["diagram_position_code"], "10100")
        self.assertEqual(first["production_period_raw"], "01/08/2016-")
        self.assertEqual(
            first["additional_source_fields"]["applicable_models_raw"],
            "25A FB25ASYHAA",
        )
        self.assertEqual(
            first["additional_source_fields"]["note_destination_code_raw"],
            "/",
        )
        self.assertEqual(
            result["parts"][1]["additional_source_fields"]["comment_raw"],
            "sample note",
        )
        self.assertEqual(result["hotspot_matching"]["matched"], ["10100"])


    def test_suzuki_asia_parts_table_preserves_part_name_additional_info_and_quantity(self):
        html = """
        <table>
          <tr><th>Code</th><th>Part number</th><th>Name</th><th>Additional information</th><th>Qty</th></tr>
          <tr><td>1</td><td>11402-61880</td><td>GASKET SET, ENGINE</td><td></td><td>1</td></tr>
          <tr><td>2</td><td>11141-61J00</td><td>.GASKET, CYLINDER HEAD</td><td>Japan spec</td><td>1</td></tr>
        </table>
        <img class="resize" src="https://ci.catcar.info/suzuki/asia/ABC123/IMGE/diagram.png">
        <div class="coord" srcNum="1" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        result = SuzukiAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 2)
        self.assertEqual(result["parts"][0]["part_number_raw"], "11402-61880")
        self.assertEqual(result["parts"][0]["description_raw"], "GASKET SET, ENGINE")
        self.assertEqual(result["parts"][0]["quantity_raw"], "1")
        self.assertEqual(
            result["parts"][1]["additional_source_fields"]["additional_information_raw"],
            "Japan spec",
        )
        self.assertEqual(result["hotspot_matching"]["matched"], ["1"])


    def test_mazda_japan_parts_table_preserves_notes_and_duplicate_position_rows(self):
        html = """
        <table>
          <tr><th>Code</th><th>Part number</th><th>Name</th><th>Note</th></tr>
          <tr><td>20130</td><td>ZJY1-20-130</td><td>SHUTTER VALVE ACTUATOR</td><td>ILLUST NO.1</td></tr>
          <tr><td>20130</td><td>ZY01-20-130B</td><td>SHUTTER VALVE ACTUATOR</td><td>ILLUST NO.2</td></tr>
        </table>
        <img class="resize" src="https://ci.catcar.info/mazda/japan/BL5FP/IMGE/diagram.png">
        <div class="coord" srcNum="20130" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        result = MazdaAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 2)
        self.assertEqual(result["parts"][0]["part_number_raw"], "ZJY1-20-130")
        self.assertEqual(result["parts"][1]["part_number_raw"], "ZY01-20-130B")
        self.assertEqual(result["parts"][0]["diagram_position_code"], "20130")
        self.assertEqual(
            result["parts"][1]["additional_source_fields"]["note_raw"],
            "ILLUST NO.2",
        )
        self.assertEqual(result["hotspot_matching"]["matched"], ["20130"])


    def test_toyota_getarticles_ajax_request_and_observed_response(self):
        url = ToyotaAdapter.build_ajax_request_url(
            "/toyota/", "TOKEN123", state=80
        )
        self.assertEqual(url, "/toyota/?l=TOKEN123&st=81")
        redirect = ToyotaAdapter.build_ajax_request_url(
            "/toyota/", "TOKEN123", state=70
        )
        self.assertEqual(redirect, "/toyota/?l=TOKEN123")

        html = """
        <table class="table inner-part">
          <tr><td>04111-36231</td><td>12/2014-03/2015</td><td>8ARFTS..AGZ1#</td></tr>
          <tr><td>04111-36300</td><td>03/2015-02/2016</td><td>8ARFTS..AGZ1#</td></tr>
          <tr><td>04111-36301</td><td>02/2016-04/2017</td><td>8ARFTS..AGZ1#</td></tr>
          <tr><td>04111-36302</td><td>04/2017-</td><td>8ARFTS..AGZ1#</td></tr>
        </table>
        """
        rows = ToyotaAdapter.parse_ajax_records(html, source_row_id="04111")
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["oem_number_raw"], "04111-36231")
        self.assertEqual(rows[0]["production_period_raw"], "12/2014-03/2015")
        self.assertEqual(rows[0]["applicability_raw"], "8ARFTS..AGZ1#")
        self.assertEqual(rows[-1]["oem_number_raw"], "04111-36302")


    def test_mazda_real_russian_parts_header_and_note(self):
        html = """
        <table>
          <tr><th>Код</th><th>Номер запчасти</th><th>Название</th><th>Примечание</th></tr>
          <tr><td>55220</td><td>BL4C-55-21X 25</td><td>PANEL,CENTER, BN3 BEIGE METALLIC</td><td>CENTER PANEL-STD W/O ROOF RAIL</td></tr>
          <tr><td>55280J</td><td>B456-60-223</td><td>BULB</td><td>14V 1.4W</td></tr>
        </table>
        <img class="resize" src="https://ci.catcar.info/mazda/gen/323/IMGE/diagram.png">
        <div class="coord" srcNum="55220" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        result = MazdaAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 2)
        self.assertEqual(result["parts"][0]["part_number_raw"], "BL4C-55-21X 25")
        self.assertEqual(result["parts"][0]["description_raw"], "PANEL,CENTER, BN3 BEIGE METALLIC")
        self.assertEqual(result["parts"][0]["additional_source_fields"]["note_raw"], "CENTER PANEL-STD W/O ROOF RAIL")
        self.assertEqual(result["hotspot_matching"]["matched"], ["55220"])

    def test_suzuki_real_russian_parts_header(self):
        html = """
        <table>
          <tr><th>Код</th><th>Номер детали</th><th>Наименование</th><th>Дополнительная информация</th><th>Qty</th><th></th></tr>
          <tr><td>1</td><td>11200-65G40</td><td>BLOCK ASSY, CYLINDER</td><td></td><td>1</td><td></td></tr>
          <tr><td>2</td><td>11216-77E00</td><td>GASKET</td><td>Japan spec</td><td>2</td><td></td></tr>
        </table>
        <img class="resize" src="https://ci.catcar.info/suzuki/asia/ABC123/IMGE/diagram.png">
        <div class="coord" srcNum="1" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        result = SuzukiAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 2)
        self.assertEqual(result["parts"][0]["part_number_raw"], "11200-65G40")
        self.assertEqual(result["parts"][0]["description_raw"], "BLOCK ASSY, CYLINDER")
        self.assertEqual(result["parts"][1]["quantity_raw"], "2")
        self.assertEqual(result["parts"][1]["additional_source_fields"]["additional_information_raw"], "Japan spec")
        self.assertEqual(result["hotspot_matching"]["matched"], ["1"])

    def test_subaru_real_russian_parts_header_preserves_source_columns(self):
        html = """
        <table>
          <tr><th>№</th><th>Номер детали</th><th>Параметы запчасти</th><th>Параметы модели</th><th>Дата производства</th><th>Примечание/ Destination Code</th><th>Дополнительно</th><th></th></tr>
          <tr><td>10006</td><td>10006AA010</td><td>HANGER-ENGINE</td><td>XT</td><td>01/06/1985-01/06/1991</td><td>/</td><td></td><td></td></tr>
          <tr><td>11410</td><td>11410AA010</td><td>HOUSING ASSEMBLY-FLYWHEEL</td><td>3C.(DL+GL)</td><td>01/06/1985-01/06/1988</td><td>-82 1300&1600/</td><td>sample note</td><td></td></tr>
        </table>
        <img class="resize" src="https://ci.catcar.info/subaru/euro/diagram.png">
        <div class="coord" srcNum="10006" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        result = SubaruAdapter().parse(html)
        self.assertEqual(len(result["parts"]), 2)
        self.assertEqual(result["parts"][0]["part_number_raw"], "10006AA010")
        self.assertEqual(result["parts"][0]["description_raw"], "HANGER-ENGINE")
        self.assertEqual(result["parts"][0]["production_period_raw"], "01/06/1985-01/06/1991")
        self.assertEqual(result["parts"][0]["additional_source_fields"]["applicable_models_raw"], "XT")
        self.assertEqual(result["parts"][1]["additional_source_fields"]["note_destination_code_raw"], "-82 1300&1600/")
        self.assertEqual(result["parts"][1]["additional_source_fields"]["comment_raw"], "sample note")
        self.assertEqual(result["hotspot_matching"]["matched"], ["10006"])


if __name__ == "__main__":
    unittest.main()
