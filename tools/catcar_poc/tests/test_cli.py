import json
import tempfile
import unittest
from pathlib import Path

from tools.catcar_poc.cli import main


class CliTests(unittest.TestCase):
    def test_offline_cli_writes_valid_normalized_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html_path = root / "page.html"
            context_path = root / "context.json"
            output_path = root / "out" / "catalog.json"

            html_path.write_text(
                """
                <table>
                  <tr><th>Code</th><th>Part number</th><th>Name</th><th>Date</th></tr>
                  <tr><td>1</td><td>1000314</td><td>Duct - Heater</td><td>1995-2002</td></tr>
                </table>
                <img src="/loader.gif" />
                <img src="/diagram.png" class="resize" />
                <div class="coord" name="1" srcTop="1" srcLeft="2" srcWidth="3" srcHeight="4"></div>
                """,
                encoding="utf-8",
            )
            context_path.write_text(json.dumps({"brand": "Ford"}), encoding="utf-8")

            result = main([
                "--adapter", "ford",
                "--input", str(html_path),
                "--output", str(output_path),
                "--source-url", "https://www.catcar.info/test",
                "--context", str(context_path),
            ])

            self.assertEqual(result, 0)
            document = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(document["source"]["adapter"], "ford_static")
            self.assertEqual(document["parts"][0]["part_number_raw"], "1000314")
            self.assertEqual(len(document["diagrams"]), 1)
            self.assertEqual(document["diagrams"][0]["source_image_url"], "/diagram.png")
            self.assertEqual(document["validation"]["hotspot_count"], 1)


if __name__ == "__main__":
    unittest.main()
