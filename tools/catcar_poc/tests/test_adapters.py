import unittest

from tools.catcar_poc.adapters import (
    ToyotaAdapter, NissanAdapter, FordAdapter, VagAdapter
)


class AdapterTests(unittest.TestCase):
    def test_toyota_ajax_tokens_and_oem_variations(self):
        html = """
        <table><tr name="15600A" onclick="getArticles(this, 'TOKEN-15600A')"><td>15600A</td></tr></table>
        <div class="coord" srcNum="15600A" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        result = ToyotaAdapter().parse(html)
        self.assertEqual(result["ajax_rows"][0]["ajax_token"], "TOKEN-15600A")
        self.assertEqual(result["hotspot_matching"]["matched"], ["15600A"])

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


if __name__ == "__main__":
    unittest.main()
