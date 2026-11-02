import unittest

from tools.catcar_poc.inspect_diagram_geometry import (
    hotspot_extent,
    normalize_image_url,
    png_dimensions,
)


class DiagramGeometryTests(unittest.TestCase):
    def test_reads_png_dimensions_from_header_only(self):
        header = (
            b"\x89PNG\r\n\x1a\n"
            + (13).to_bytes(4, "big")
            + b"IHDR"
            + (1024).to_bytes(4, "big")
            + (768).to_bytes(4, "big")
        )
        self.assertEqual(png_dimensions(header), (1024, 768))
        self.assertIsNone(png_dimensions(b"not a png"))

    def test_calculates_hotspot_extent_without_guessing_scale(self):
        result = hotspot_extent([
            {"top_raw": "10", "left_raw": "20", "width_raw": "30", "height_raw": "40"},
            {"top_raw": "50", "left_raw": "60", "width_raw": "5", "height_raw": "6"},
            {"top_raw": "", "left_raw": "1", "width_raw": "2", "height_raw": "3"},
        ])
        self.assertEqual(result["valid_box_count"], 2)
        self.assertEqual(result["invalid_box_count"], 1)
        self.assertEqual(result["max_right"], 65)
        self.assertEqual(result["max_bottom"], 56)

    def test_normalizes_relative_catcar_image_url(self):
        self.assertEqual(
            normalize_image_url(
                "http://www.catcar.info/toyota/catalog",
                "/toyota_2017_04/japan/./118157 .png",
            ),
            "https://www.catcar.info/toyota_2017_04/japan/118157%20.png",
        )

    def test_rejects_non_catcar_image_host(self):
        with self.assertRaisesRegex(ValueError, "Non-CatCar"):
            normalize_image_url("https://www.catcar.info/toyota", "https://example.com/image.png")


if __name__ == "__main__":
    unittest.main()
