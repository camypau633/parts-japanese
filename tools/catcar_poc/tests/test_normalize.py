import unittest

from tools.catcar_poc.adapters import VagAdapter
from tools.catcar_poc.normalize import normalize_page


class NormalizeTests(unittest.TestCase):
    def test_normalizes_vag_parts_diagram_and_unresolved_position(self):
        html = """
        <table>
          <tr><th></th><th></th><th>part number</th><th>Description</th><th>Remark</th><th>ST</th><th>Model data</th></tr>
          <tr><td>3</td><td></td><td>7E7067027</td><td>trim for windowsill</td><td>centre left</td><td>1</td><td></td></tr>
          <tr><td></td><td></td><td>7E7067027 92W</td><td>trim for windowsill moonrock grey</td><td>centre left 04.15 - ...</td><td></td><td></td></tr>
          <tr><td>(40)</td><td></td><td>TRANSFER</td><td>see illustration 127-020</td><td></td><td></td><td></td></tr>
        </table>
        <img src="/diagrams/sample.png" />
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
        self.assertEqual(normalized["parts"][1]["row_kind"], "continuation")
        self.assertEqual(normalized["parts"][1]["parent_position_code"], None)
        self.assertEqual(normalized["diagrams"][0]["source_image_url"], "/diagrams/sample.png")
        self.assertEqual(normalized["hotspots"][0]["resolution_status"], "matched")
        self.assertEqual(normalized["validation"]["hotspot_matching"]["rows_without_hotspot"], ["(40)"])


if __name__ == "__main__":
    unittest.main()
