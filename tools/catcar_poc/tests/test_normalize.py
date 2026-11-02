import unittest

from tools.catcar_poc.adapters import NissanAdapter, ToyotaAdapter, VagAdapter
from tools.catcar_poc.normalize import normalize_page


class NormalizeTests(unittest.TestCase):

    def test_one_hotspot_can_link_to_multiple_part_rows(self):
        html = """
        <table>
          <tr><th>№</th><th>Номер детали</th><th>Название</th><th>Дата производства</th><th>Alt</th><th>Qty</th></tr>
          <tr><td>12010S</td><td>12000-4A00A</td><td>PISTON SET</td><td>03/2009-01/2012</td><td></td><td>03</td></tr>
          <tr><td>12010S</td><td>12000-4A00B</td><td>PISTON SET</td><td>01/2012-</td><td></td><td>03</td></tr>
        </table>
        <div class="coord" srcNum="12010S" srcTop="1" srcLeft="2" srcWidth="3" srcHeight="4"></div>
        """
        result = NissanAdapter().parse(html)
        normalized = normalize_page(result, {"brand": "Nissan"}, "https://example.test/nissan")
        self.assertEqual(normalized["parts"][0]["alternative_number_raw"], "")
        hotspot = normalized["hotspots"][0]
        self.assertEqual(hotspot["resolution_status"], "matched")
        self.assertIsNone(hotspot["source_row_id"])
        self.assertEqual(len(hotspot["source_row_ids"]), 2)

    def test_toyota_oem_variations_are_kept_and_linked_to_source_row(self):
        html = """
        <table><tr name="15600A" onclick="getArticles(this, 'TOKEN')"><td>15600A</td></tr></table>
        <div class="coord" srcNum="15600A" srcTop="1" srcLeft="2" srcWidth="3" srcHeight="4"></div>
        """
        parsed = ToyotaAdapter().parse(html)
        records = ToyotaAdapter.parse_ajax_records(
            "<table><tr><td>9151180830</td><td></td><td></td></tr></table>",
            source_row_id="15600A",
        )
        normalized = normalize_page(
            parsed, {"brand": "Toyota"}, "https://www.catcar.info/toyota/example",
            oem_records=records,
        )
        self.assertEqual(len(normalized["oem_records"]), 1)
        self.assertEqual(normalized["oem_records"][0]["source_row_id"], "15600A")
        self.assertIsNone(normalized["oem_records"][0]["production_period_raw"])

    def test_normalizes_vag_parts_diagram_and_unresolved_position(self):
        html = """
        <table>
          <tr><th></th><th></th><th>part number</th><th>Description</th><th>Remark</th><th>ST</th><th>Model data</th></tr>
          <tr><td>3</td><td></td><td>7E7067027</td><td>trim for windowsill</td><td>centre left</td><td>1</td><td></td></tr>
          <tr><td></td><td></td><td>7E7067027 92W</td><td>trim for windowsill moonrock grey</td><td>centre left 04.15 - ...</td><td></td><td></td></tr>
          <tr><td>(40)</td><td></td><td>TRANSFER</td><td>see illustration 127-020</td><td></td><td></td><td></td></tr>
        </table>
        <img src="/_sysimg/big_catalog2/ajax-loader.gif" />
        <img src="/images/logo.png" />
        <img src="/diagrams/sample.png" class="resize" />
        <div class="coord" name="3" srcTop="10" srcLeft="20" srcWidth="30" srcHeight="40"></div>
        """
        result = VagAdapter().parse(html)
        normalized = normalize_page(
            result,
            {"brand": "Volkswagen", "model": "Campmob", "source_group_id": "86735"},
            "https://www.catcar.info/audivw/example"
        )
        self.assertEqual(normalized["schema_version"], "0.1-draft")
        self.assertEqual(normalized["catalog_context"]["brand"], "Volkswagen")
        self.assertEqual(len(normalized["parts"]), 3)
        self.assertEqual(len(normalized["diagrams"]), 1)
        self.assertEqual(normalized["diagrams"][0]["source_image_url"], "/diagrams/sample.png")
        self.assertEqual(normalized["parts"][1]["row_kind"], "continuation")
        self.assertEqual(normalized["parts"][1]["parent_position_code"], None)
        self.assertEqual(normalized["diagrams"][0]["source_image_url"], "/diagrams/sample.png")
        self.assertEqual(normalized["hotspots"][0]["resolution_status"], "matched")
        self.assertEqual(normalized["hotspots"][0]["source_row_id"], normalized["parts"][0]["source_row_id"])
        self.assertEqual(normalized["validation"]["hotspot_matching"]["rows_without_hotspot"], ["(40)"])


if __name__ == "__main__":
    unittest.main()
