from .parser import parse_html, cell_texts, find_header_row, extract_getarticles_token


class BaseAdapter:
    name = "base"

    def parse(self, html):
        parsed = parse_html(html)
        return {
            "adapter": self.name,
            "rows": parsed.rows,
            "images": parsed.images,
            "hotspots": parsed.hotspots,
            "parts": [],
            "ajax_rows": [],
            "hotspot_matching": self.match_hotspots([], parsed.hotspots),
        }

    @staticmethod
    def match_hotspots(position_codes, hotspots):
        positions = set(str(x).strip() for x in position_codes if str(x).strip())
        hotspot_ids = set(x.get("position_code", "").strip() for x in hotspots
                          if x.get("position_code", "").strip())
        return {
            "matched": sorted(positions.intersection(hotspot_ids)),
            "hotspots_without_row": sorted(hotspot_ids.difference(positions)),
            "rows_without_hotspot": sorted(positions.difference(hotspot_ids)),
        }


class ToyotaAdapter(BaseAdapter):
    name = "toyota_ajax"

    def parse(self, html):
        parsed = parse_html(html)
        ajax_rows = []
        for row in parsed.rows:
            attrs = row.get("attrs", {})
            part_number = attrs.get("name", "").strip()
            token = extract_getarticles_token(attrs.get("onclick", ""))
            if part_number and token:
                ajax_rows.append({
                    "source_row_id": part_number,
                    "part_number_raw": part_number,
                    "ajax_token": token,
                    "source_status": "requires_ajax",
                })
        positions = [x.get("position_code", "") for x in parsed.hotspots]
        return {
            "adapter": self.name,
            "rows": parsed.rows,
            "images": parsed.images,
            "hotspots": parsed.hotspots,
            "parts": ajax_rows,
            "ajax_rows": ajax_rows,
            "hotspot_matching": self.match_hotspots(
                [x["source_row_id"] for x in ajax_rows], parsed.hotspots
            ),
        }

    @staticmethod
    def parse_ajax_records(html):
        parsed = parse_html(html)
        records = []
        for row in parsed.rows:
            values = [x for x in cell_texts(row) if x]
            if len(values) >= 3:
                records.append({
                    "oem_number_raw": values[0],
                    "production_period_raw": values[1],
                    "applicability_raw": values[2],
                })
        return records


class StaticTableAdapter(BaseAdapter):
    position_index = 0
    part_number_index = 1
    description_index = 2
    period_index = None
    quantity_index = None
    name = "static"

    def parse(self, html):
        parsed = parse_html(html)
        parts = []
        for order, row in enumerate(parsed.rows):
            cells = cell_texts(row)
            if not cells:
                continue
            if len(cells) <= max(self.position_index, self.part_number_index):
                continue
            position = cells[self.position_index].strip()
            part_number = cells[self.part_number_index].strip()
            if not part_number:
                continue
            parts.append({
                "source_row_id": str(order),
                "source_row_order": order,
                "diagram_position_code": position or None,
                "part_number_raw": part_number,
                "description_raw": self._value(cells, self.description_index),
                "production_period_raw": self._value(cells, self.period_index),
                "quantity_raw": self._value(cells, self.quantity_index),
                "row_kind": "positioned" if position else "continuation",
                "parent_position_code": None,
                "additional_source_fields": {},
            })
        positions = [x["diagram_position_code"] for x in parts if x["diagram_position_code"]]
        return {
            "adapter": self.name,
            "rows": parsed.rows,
            "images": parsed.images,
            "hotspots": parsed.hotspots,
            "parts": parts,
            "ajax_rows": [],
            "hotspot_matching": self.match_hotspots(positions, parsed.hotspots),
        }

    @staticmethod
    def _value(values, index):
        if index is None or index < 0 or index >= len(values):
            return ""
        return values[index].strip()


class NissanAdapter(StaticTableAdapter):
    name = "nissan_static"
    position_index = 0
    part_number_index = 1
    description_index = 2
    period_index = 3
    quantity_index = 5


class FordAdapter(StaticTableAdapter):
    name = "ford_static"
    position_index = 0
    part_number_index = 1
    description_index = 2
    period_index = 3
    quantity_index = None


class VagAdapter(StaticTableAdapter):
    name = "vag_static"
    position_index = 0
    part_number_index = 2
    description_index = 3
    period_index = None
    quantity_index = 5

    def parse(self, html):
        result = super().parse(html)
        for part in result["parts"]:
            cells = cell_texts(result["rows"][part["source_row_order"]])
            part["additional_source_fields"] = {
                "remark_raw": self._value(cells, 4),
                "st_raw": self._value(cells, 5),
                "model_data_raw": self._value(cells, 6),
            }
            if part["diagram_position_code"] == "(40)":
                part["source_status"] = "unresolved"
        return result
