import re
from html.parser import HTMLParser


class CatalogHTMLParser(HTMLParser):
    """Preserve table row/cell attributes, text, image URLs and diagram hotspots."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.images = []
        self.hotspots = []
        self._row = None
        self._cell = None
        self._hotspot = None

    def handle_starttag(self, tag, attrs):
        attrs = {str(k).lower(): (v or "") for k, v in attrs}
        if tag == "tr":
            if self._row is not None:
                self._finish_row()
            self._row = {"attrs": attrs, "cells": []}
        elif tag in ("td", "th") and self._row is not None:
            self._cell = {"tag": tag, "attrs": attrs, "text_parts": [], "links": []}
        elif tag == "a" and self._cell is not None:
            href = attrs.get("href")
            if href:
                self._cell.setdefault("links", []).append({"href": href, "attrs": attrs})
        elif tag == "img":
            src = attrs.get("src") or attrs.get("data-src")
            if src:
                image_classes = attrs.get("class", "").split()
                self.images.append({
                    "src": src,
                    "attrs": attrs,
                    "image_kind": "diagram" if "resize" in image_classes else "other",
                })
        elif tag == "div" and "coord" in attrs.get("class", "").split():
            self.hotspots.append({
                "position_code": attrs.get("srcnum") or attrs.get("name") or "",
                "name": attrs.get("name", ""),
                "src_num": attrs.get("srcnum", ""),
                "top": attrs.get("srctop", ""),
                "left": attrs.get("srcleft", ""),
                "width": attrs.get("srcwidth", ""),
                "height": attrs.get("srcheight", ""),
                "attrs": attrs,
            })

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["text_parts"].append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._finish_cell()
        elif tag == "tr" and self._row is not None:
            self._finish_row()

    def close(self):
        super().close()
        if self._cell is not None:
            self._finish_cell()
        if self._row is not None:
            self._finish_row()

    def _finish_cell(self):
        text = " ".join(" ".join(self._cell["text_parts"]).split())
        self._cell["text"] = text
        del self._cell["text_parts"]
        self._row["cells"].append(self._cell)
        self._cell = None

    def _finish_row(self):
        if self._cell is not None:
            self._finish_cell()
        if self._row and any(cell.get("text") for cell in self._row["cells"]):
            self.rows.append(self._row)
        self._row = None


def parse_html(source):
    parser = CatalogHTMLParser()
    parser.feed(source or "")
    parser.close()
    return parser


def cell_texts(row):
    return [cell.get("text", "") for cell in row.get("cells", [])]


def find_header_row(rows, expected):
    expected = set(x.lower() for x in expected)
    for index, row in enumerate(rows):
        values = set(x.strip().lower() for x in cell_texts(row) if x.strip())
        if expected.intersection(values):
            return index, values
    return None, set()


def extract_getarticles_token(onclick):
    match = re.search(r"getArticles\s*\(\s*this\s*,\s*['\"]([^'\"]+)['\"]", onclick or "", re.I)
    return match.group(1) if match else ""
