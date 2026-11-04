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
                cells = cell_texts(row)
                ajax_rows.append({
                    "source_row_id": part_number,
                    "diagram_position_code": part_number,
                    "part_number_raw": None,
                    "description_raw": cells[1].strip() if len(cells) > 1 else "",
                    "additional_source_fields": {"raw_cells": list(cells)},
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
    def parse_ajax_records(html, source_row_id=None):
        parsed = parse_html(html)
        records = []
        for row in parsed.rows:
            values = cell_texts(row)
            if len(values) < 3:
                continue
            first = values[0].strip().lower()
            if first in (
                "oem", "oem number", "part number", "number",
                "номер детали", "номер запчасти"
            ):
                continue
            records.append({
                "source_row_id": source_row_id,
                "oem_number_raw": values[0].strip() or None,
                "production_period_raw": values[1].strip() or None,
                "applicability_raw": values[2].strip() or None,
            })
        if not records and "no applicable data" in (html or "").lower():
            return [{
                "source_row_id": source_row_id,
                "oem_number_raw": None,
                "production_period_raw": None,
                "applicability_raw": None,
                "source_status": "no_applicable_data",
            }]
        for record in records:
            record["source_status"] = "available"
        return records


class StaticTableAdapter(BaseAdapter):
    position_index = 0
    part_number_index = 1
    description_index = 2
    period_index = None
    quantity_index = None
    alternative_number_index = None
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
            if not part_number or part_number.lower() in (
                "part number", "номер детали", "номер запчасти"
            ):
                continue
            parts.append({
                "source_row_id": str(order),
                "source_row_order": order,
                "diagram_position_code": position or None,
                "part_number_raw": part_number,
                "description_raw": self._value(cells, self.description_index),
                "production_period_raw": self._value(cells, self.period_index),
                "quantity_raw": self._value(cells, self.quantity_index),
                "alternative_number_raw": self._value(cells, self.alternative_number_index),
                "row_kind": "positioned" if position else "continuation",
                "parent_position_code": None,
                "additional_source_fields": {"raw_cells": list(cells)},
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
    alternative_number_index = 4



class HondaAdapter(StaticTableAdapter):
    """Parse Honda's observed code/part/description table and preserve option metadata."""

    name = "honda_static"

    def parse(self, html):
        parsed = parse_html(html)
        header_index, _ = find_header_row(parsed.rows, ("код", "артикул", "описание"))
        if header_index is None:
            raise ValueError("Honda parts table header not found")

        parts = []
        for order, row in enumerate(parsed.rows[header_index + 1:], start=header_index + 1):
            cells = cell_texts(row)
            if len(cells) < 3:
                continue
            position = cells[0].strip()
            part_number = cells[1].strip()
            if not part_number:
                continue
            parts.append({
                "source_row_id": str(order),
                "source_row_order": order,
                "diagram_position_code": position or None,
                "part_number_raw": part_number,
                "description_raw": cells[2].strip(),
                "production_period_raw": "",
                "quantity_raw": "",
                "alternative_number_raw": "",
                "row_kind": "positioned" if position else "continuation",
                "parent_position_code": None,
                "additional_source_fields": {
                    "raw_cells": list(cells),
                    "additional_information_raw": self._value(cells, 3),
                    "option_codes_raw": self._value(cells, 4),
                },
            })

        positions = [item["diagram_position_code"] for item in parts
                     if item["diagram_position_code"]]
        diagram_images = [image for image in parsed.images
                          if image.get("image_kind") == "diagram"]
        diagram_src = diagram_images[0].get("src", "") if len(diagram_images) == 1 else ""
        template_image = "{npl}" in diagram_src or "{" in diagram_src or "}" in diagram_src
        page_status = "complete" if parts and len(diagram_images) == 1 and diagram_src and not template_image else "incomplete"
        warnings = []
        if not parts:
            warnings.append("no_part_rows_after_honda_header")
        if len(diagram_images) != 1:
            warnings.append("expected_exactly_one_diagram_image")
        elif not diagram_src or template_image:
            warnings.append("diagram_image_url_unresolved")
        return {
            "adapter": self.name,
            "page_status": page_status,
            "page_warnings": warnings,
            "rows": parsed.rows,
            "images": parsed.images,
            "hotspots": parsed.hotspots,
            "parts": parts,
            "ajax_rows": [],
            "hotspot_matching": self.match_hotspots(positions, parsed.hotspots),
        }


class MazdaAdapter(StaticTableAdapter):
    """Parse the inspected Mazda parts-list table with Note preserved verbatim."""

    name = "mazda_static"

    def parse(self, html):
        parsed = parse_html(html)
        header_index, _ = find_header_row(
            parsed.rows, ("code", "part number", "name")
        )
        if header_index is None:
            raise ValueError("Mazda parts table header not found")

        headers = [value.strip().lower() for value in cell_texts(parsed.rows[header_index])]

        def column(*names):
            for name in names:
                if name in headers:
                    return headers.index(name)
            return None

        position_index = column("code", "№", "no.")
        part_number_index = column("part number")
        description_index = column("name", "description")
        note_index = column("note", "additional information")

        if position_index is None or part_number_index is None:
            raise ValueError("Mazda parts table required columns are missing")

        parts = []
        for order, row in enumerate(parsed.rows[header_index + 1:], start=header_index + 1):
            cells = cell_texts(row)
            if len(cells) <= max(position_index, part_number_index):
                continue
            part_number = self._value(cells, part_number_index)
            if not part_number:
                continue
            position = self._value(cells, position_index)
            parts.append({
                "source_row_id": str(order),
                "source_row_order": order,
                "diagram_position_code": position or None,
                "part_number_raw": part_number,
                "description_raw": self._value(cells, description_index),
                "production_period_raw": "",
                "quantity_raw": "",
                "alternative_number_raw": "",
                "row_kind": "positioned" if position else "continuation",
                "parent_position_code": None,
                "additional_source_fields": {
                    "raw_cells": list(cells),
                    "note_raw": self._value(cells, note_index),
                },
            })

        positions = [item["diagram_position_code"] for item in parts
                     if item["diagram_position_code"]]
        return {
            "adapter": self.name,
            "rows": parsed.rows,
            "images": parsed.images,
            "hotspots": parsed.hotspots,
            "parts": parts,
            "ajax_rows": [],
            "hotspot_matching": self.match_hotspots(positions, parsed.hotspots),
        }


class SuzukiAdapter(StaticTableAdapter):
    """Parse the inspected Suzuki CatCar parts table used by the Asia/APV branch."""

    name = "suzuki_static"

    def parse(self, html):
        parsed = parse_html(html)
        header_index, _ = find_header_row(
            parsed.rows, ("code", "part number", "name")
        )
        if header_index is None:
            raise ValueError("Suzuki parts table header not found")

        headers = [value.strip().lower() for value in cell_texts(parsed.rows[header_index])]

        def column(*names):
            for name in names:
                if name in headers:
                    return headers.index(name)
            return None

        position_index = column("code", "№", "no.")
        part_number_index = column("part number")
        description_index = column("name", "description")
        additional_index = column("additional information", "additional info")
        quantity_index = column("qty", "quantity")

        if position_index is None or part_number_index is None:
            raise ValueError("Suzuki parts table required columns are missing")

        parts = []
        for order, row in enumerate(parsed.rows[header_index + 1:], start=header_index + 1):
            cells = cell_texts(row)
            if len(cells) <= max(position_index, part_number_index):
                continue
            part_number = self._value(cells, part_number_index)
            if not part_number:
                continue
            position = self._value(cells, position_index)
            parts.append({
                "source_row_id": str(order),
                "source_row_order": order,
                "diagram_position_code": position or None,
                "part_number_raw": part_number,
                "description_raw": self._value(cells, description_index),
                "production_period_raw": "",
                "quantity_raw": self._value(cells, quantity_index),
                "alternative_number_raw": "",
                "row_kind": "positioned" if position else "continuation",
                "parent_position_code": None,
                "additional_source_fields": {
                    "raw_cells": list(cells),
                    "additional_information_raw": self._value(cells, additional_index),
                },
            })

        positions = [item["diagram_position_code"] for item in parts
                     if item["diagram_position_code"]]
        return {
            "adapter": self.name,
            "rows": parsed.rows,
            "images": parsed.images,
            "hotspots": parsed.hotspots,
            "parts": parts,
            "ajax_rows": [],
            "hotspot_matching": self.match_hotspots(positions, parsed.hotspots),
        }


class SubaruAdapter(StaticTableAdapter):
    """Parse the observed Subaru CatCar parts-list table.

    The parser is intentionally header-driven. It preserves applicable-model,
    destination-code and comment columns rather than treating them as OEM data.
    """

    name = "subaru_static"

    def parse(self, html):
        parsed = parse_html(html)
        header_index, headers = find_header_row(
            parsed.rows, ("part number", "options", "applicable models")
        )
        if header_index is None:
            raise ValueError("Subaru parts table header not found")

        header_cells = [value.strip().lower() for value in cell_texts(parsed.rows[header_index])]

        def column(*names):
            for name in names:
                if name in header_cells:
                    return header_cells.index(name)
            return None

        position_index = column("№", "no.", "no")
        part_number_index = column("part number")
        description_index = column("options", "description")
        applicable_index = column("applicable models")
        period_index = column("production date", "production period")
        destination_index = column("note/destination code", "destination code", "note")
        comment_index = column("comment")

        if position_index is None or part_number_index is None:
            raise ValueError("Subaru parts table required columns are missing")

        parts = []
        for order, row in enumerate(parsed.rows[header_index + 1:], start=header_index + 1):
            cells = cell_texts(row)
            if len(cells) <= max(position_index, part_number_index):
                continue
            part_number = self._value(cells, part_number_index)
            if not part_number:
                continue
            position = self._value(cells, position_index)
            parts.append({
                "source_row_id": str(order),
                "source_row_order": order,
                "diagram_position_code": position or None,
                "part_number_raw": part_number,
                "description_raw": self._value(cells, description_index),
                "production_period_raw": self._value(cells, period_index),
                "quantity_raw": "",
                "alternative_number_raw": "",
                "row_kind": "positioned" if position else "continuation",
                "parent_position_code": None,
                "additional_source_fields": {
                    "raw_cells": list(cells),
                    "applicable_models_raw": self._value(cells, applicable_index),
                    "note_destination_code_raw": self._value(cells, destination_index),
                    "comment_raw": self._value(cells, comment_index),
                },
            })

        positions = [item["diagram_position_code"] for item in parts
                     if item["diagram_position_code"]]
        return {
            "adapter": self.name,
            "rows": parsed.rows,
            "images": parsed.images,
            "hotspots": parsed.hotspots,
            "parts": parts,
            "ajax_rows": [],
            "hotspot_matching": self.match_hotspots(positions, parsed.hotspots),
        }


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
    quantity_index = None

    def parse(self, html):
        result = super().parse(html)
        for part in result["parts"]:
            cells = cell_texts(result["rows"][part["source_row_order"]])
            part["additional_source_fields"] = {
                "raw_cells": list(cells),
                "remark_raw": self._value(cells, 4),
                "st_raw": self._value(cells, 5),
                "model_data_raw": self._value(cells, 6),
            }
            if part["part_number_raw"].strip().lower() in ("переход к группе", "group transition"):
                part["row_kind"] = "group_header"
                part["source_status"] = "unresolved"
                part["additional_source_fields"]["entry_type_raw"] = part["part_number_raw"]
                part["part_number_raw"] = None
            elif part["diagram_position_code"] == "(40)":
                part["source_status"] = "unresolved"
        return result


class DiscoveryOnlyAdapter(BaseAdapter):
    """Preserve source pages while a make-specific detail parser is pending."""

    name = "discovery_only"

    def parse(self, html):
        raise ValueError(
            "detail_adapter_not_implemented: page retained for structural review"
        )
