"""Offline conversion from normalized Japanese CatCar JSON to PartScope shards."""
import argparse
import json
import math
import posixpath
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

SUPPORTED_BRANDS = {"Toyota", "Nissan"}
DEFAULT_MAX_SHARD_BYTES = 2 * 1024 * 1024
DEFAULT_HOTSPOT_RADIUS = 28


def clean_sku(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def text(value):
    return "" if value is None else str(value).strip()


def vehicle_context(context):
    brand = text(context.get("brand"))
    model = text(context.get("model"))
    if not brand or not model:
        return []
    years = text(context.get("production_period_raw") or context.get("production_period"))
    engine = text(context.get("engine_code") or context.get("engine"))
    return [{
        "brand": brand,
        "model": model,
        "engine": engine,
        "years": years,
        "id": clean_sku("-".join((brand, model, engine, years))) or None,
    }]


def normalize_diagram_url(source_url, image_url):
    if not image_url:
        return ""
    resolved = urljoin(source_url, image_url)
    parts = urlsplit(resolved)
    if parts.hostname and (parts.hostname == "catcar.info" or parts.hostname.endswith(".catcar.info")):
        parts = parts._replace(scheme="https")
    path = quote(posixpath.normpath(parts.path), safe="/%:@")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def diagram_data(document):
    diagrams = document.get("diagrams") or []
    if not diagrams:
        return {"diagramUrl": "", "hotspots": []}
    source_url = text((document.get("source") or {}).get("url"))
    image_url = text(diagrams[0].get("source_image_url"))
    return {
        "diagramUrl": normalize_diagram_url(source_url, image_url),
        "hotspots": [],
    }


def validate_geometry_report(report):
    """Validate the bounded image/header and CatCar resize-script evidence."""
    script = "\n".join((report.get("coordinate_script") or {}).get("relevant_snippets") or [])
    css = "\n".join((report.get("main_css") or {}).get("relevant_snippets") or [])
    required_script = ("srcTop", "srcLeft", "srcWidth", "srcHeight", "h/nh", "w/nw")
    if not all(token in script for token in required_script):
        raise ValueError("CatCar coordinate resize script evidence is incomplete")
    if ".resize" not in css or "width:100%" not in css or "height:100%" not in css:
        raise ValueError("CatCar diagram CSS resize evidence is incomplete")

    index = {}
    for image in report.get("images") or []:
        url = text(image.get("image_url"))
        dimensions = image.get("image_dimensions") or {}
        width = dimensions.get("width")
        height = dimensions.get("height")
        if not url:
            raise ValueError("Geometry report contains an image without URL")
        if image.get("http_status") != 206 or not text(image.get("content_type")).lower().startswith("image/png"):
            raise ValueError("Diagram image was not verified as a PNG range response: %s" % url)
        if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
            raise ValueError("Diagram image dimensions are missing: %s" % url)
        if image.get("hotspot_count", 0) and image.get("all_hotspot_boxes_inside_image_bounds") is not True:
            raise ValueError("Hotspot bounds were not verified for diagram: %s" % url)
        index[url] = image
    if not index:
        raise ValueError("Geometry report contains no verified diagram images")
    return index


def _coordinate(value, field, position):
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("Invalid hotspot %s for position %s" % (field, position))
    if not math.isfinite(result):
        raise ValueError("Non-finite hotspot %s for position %s" % (field, position))
    return result


def _append_hotspot(hotspots, hotspot):
    for existing in hotspots:
        if existing.get("id") == hotspot.get("id") and existing.get("x") == hotspot.get("x") and existing.get("y") == hotspot.get("y"):
            details = text(hotspot.get("details"))
            current = text(existing.get("details"))
            if details and details not in current.split(" | "):
                existing["details"] = (current + " | " + details).strip(" |")
            return
    hotspots.append(hotspot)


def hotspots_for_row(document, row, oem, description, diagram_url, geometry_index):
    if not geometry_index or not diagram_url:
        return []
    image = geometry_index.get(diagram_url)
    if image is None:
        raise ValueError("No verified geometry report for Toyota diagram %s" % diagram_url)
    dimensions = image["image_dimensions"]
    image_width = dimensions["width"]
    image_height = dimensions["height"]
    row_id = text(row.get("source_row_id"))
    if not row_id:
        return []

    raw_number = text(oem.get("oem_number_raw"))
    period = text(oem.get("production_period_raw"))
    applicability = text(oem.get("applicability_raw"))
    details = []
    if period:
        details.append("Период: " + period)
    if applicability:
        details.append("Применимость: " + applicability)

    result = []
    for item in document.get("hotspots") or []:
        if item.get("resolution_status") != "matched":
            continue
        linked_rows = item.get("source_row_ids") or []
        if not linked_rows and item.get("source_row_id"):
            linked_rows = [item.get("source_row_id")]
        if row_id not in [text(value) for value in linked_rows]:
            continue

        position = text(item.get("source_position_code") or row.get("diagram_position_code"))
        if not position:
            continue
        top = _coordinate(item.get("top_raw"), "top", position)
        left = _coordinate(item.get("left_raw"), "left", position)
        width = _coordinate(item.get("width_raw"), "width", position)
        height = _coordinate(item.get("height_raw"), "height", position)
        if width <= 0 or height <= 0 or left < 0 or top < 0 or left + width > image_width or top + height > image_height:
            raise ValueError("Hotspot position %s exceeds verified image dimensions" % position)

        result.append({
            "id": position,
            "x": left + width / 2.0,
            "y": top + height / 2.0,
            "radius": DEFAULT_HOTSPOT_RADIUS,
            "name": description,
            "oem": raw_number,
            "details": "; ".join(details),
        })
    return result


def document_to_records(document, geometry_index=None):
    source = document.get("source") or {}
    context = document.get("catalog_context") or {}
    brand = text(context.get("brand"))
    if source.get("name") != "CatCar":
        raise ValueError("Only normalized CatCar documents are supported")
    if brand not in SUPPORTED_BRANDS:
        raise ValueError("Brand %r is not enabled; allowed: %s" %
                         (brand, ", ".join(sorted(SUPPORTED_BRANDS))))
    source_url = text(source.get("url"))
    if not source_url:
        raise ValueError("Normalized document has no source URL")

    oem_by_row = defaultdict(list)
    for item in document.get("oem_records") or []:
        row_id = text(item.get("source_row_id"))
        if row_id and item.get("source_status", "available") == "available":
            oem_by_row[row_id].append(item)

    candidates = []
    for row in document.get("parts") or []:
        raw_number = text(row.get("part_number_raw"))
        if raw_number:
            candidates.append((row, {
                "oem_number_raw": raw_number,
                "production_period_raw": row.get("production_period_raw"),
                "applicability_raw": None,
            }))
        elif row.get("source_status") == "requires_ajax":
            for item in oem_by_row.get(text(row.get("source_row_id")), []):
                candidates.append((row, item))

    result = {}
    compatibility = vehicle_context(context)
    diagram = diagram_data(document)
    catalog_name = text(context.get("group_label_raw"))
    group_id = text(context.get("source_group_id"))
    if geometry_index and brand == "Toyota" and diagram["diagramUrl"] and diagram["diagramUrl"] not in geometry_index:
        raise ValueError("Toyota diagram is missing from the verified geometry report")

    for row, oem in candidates:
        raw_number = text(oem.get("oem_number_raw"))
        sku = clean_sku(raw_number)
        if len(sku) < 2:
            continue
        description = text(row.get("description_raw")) or catalog_name
        factory = {
            "sku": raw_number,
            "name": description,
            "source_name": "CatCar",
            "source_url": text(oem.get("source_url")) or source_url,
        }
        if oem.get("source_group_id") is not None:
            factory["source_group_id"] = text(oem.get("source_group_id"))
        if oem.get("source_record_order") is not None:
            factory["source_record_order"] = oem.get("source_record_order")
        for target, source_key in (
            ("position", "diagram_position_code"),
            ("quantity", "quantity_raw"),
        ):
            value = text(row.get(source_key))
            if value:
                factory[target] = value
        for target, source_key in (
            ("production_period", "production_period_raw"),
            ("applicability", "applicability_raw"),
        ):
            value = text(oem.get(source_key))
            if value:
                factory[target] = value

        record = result.get(sku)
        if record is None:
            part_id = "%s:%s" % (brand.lower(), sku)
            if group_id:
                part_id += ":" + group_id
            record = {
                "part_id": part_id,
                "sku": sku,
                "name": description,
                "brand": brand,
                "factory_parts": [],
                "analogs": [],
                "compatibility": list(compatibility),
                "diagram": dict(diagram),
                "specifications": [],
                "technical_drawings": [],
                "source": {"name": "CatCar", "url": source_url},
            }
            result[sku] = record
        if factory not in record["factory_parts"]:
            record["factory_parts"].append(factory)
        if not record["name"] and description:
            record["name"] = description

        if geometry_index and brand == "Toyota":
            for hotspot in hotspots_for_row(
                document, row, oem, description, diagram["diagramUrl"], geometry_index
            ):
                _append_hotspot(record["diagram"]["hotspots"], hotspot)
    return result


def _iter_records(records):
    for sku, value in records.items():
        variants = value if isinstance(value, list) else [value]
        for record in variants:
            yield sku, record


def validate_export_records(records):
    """Fail closed on broken SKU, OEM provenance, or app-facing structure."""
    brands = Counter()
    records_with_years = 0
    records_with_engine = 0
    records_with_diagram = 0
    factory_part_count = 0
    hotspot_count = 0
    records_with_hotspots = 0
    record_count = 0

    for sku, record in _iter_records(records):
        record_count += 1
        if not sku or clean_sku(sku) != sku:
            raise ValueError("Invalid cleaned SKU key: %r" % sku)
        if record.get("sku") != sku:
            raise ValueError("Record SKU does not match shard key: %s" % sku)
        brand = record.get("brand")
        if brand not in SUPPORTED_BRANDS:
            raise ValueError("Unsupported exported brand for %s: %r" % (sku, brand))
        brands[brand] += 1

        source = record.get("source") or {}
        source_url = text(source.get("url"))
        parsed_source = urlsplit(source_url)
        if source.get("name") != "CatCar" or parsed_source.scheme not in ("http", "https") or not parsed_source.hostname or not (parsed_source.hostname == "catcar.info" or parsed_source.hostname.endswith(".catcar.info")):
            raise ValueError("Missing or invalid CatCar provenance for %s" % sku)

        factory_parts = record.get("factory_parts")
        if not isinstance(factory_parts, list) or not factory_parts:
            raise ValueError("No factory catalogue rows for %s" % sku)
        for factory in factory_parts:
            factory_part_count += 1
            raw_oem = text(factory.get("sku"))
            if not raw_oem or clean_sku(raw_oem) != sku:
                raise ValueError("Factory OEM number does not match record SKU: %s" % sku)
            if factory.get("source_name") != "CatCar" or not text(factory.get("source_url")):
                raise ValueError("Factory row is missing source provenance: %s" % sku)

        if not isinstance(record.get("analogs"), list):
            raise ValueError("Analogs must be a list for %s" % sku)
        if not isinstance(record.get("compatibility"), list):
            raise ValueError("Compatibility must be a list for %s" % sku)
        if any(text(vehicle.get("brand") or vehicle.get("make") or vehicle.get("manufacturer")).casefold() != brand.casefold() for vehicle in record["compatibility"]):
            raise ValueError("Compatibility make does not match record brand: %s" % sku)
        if any(text(vehicle.get("years")) for vehicle in record["compatibility"]):
            records_with_years += 1
        if any(text(vehicle.get("engine")) for vehicle in record["compatibility"]):
            records_with_engine += 1

        diagram = record.get("diagram") or {}
        diagram_url = text(diagram.get("diagramUrl"))
        if diagram_url:
            parsed_diagram = urlsplit(diagram_url)
            if parsed_diagram.scheme not in ("http", "https") or not parsed_diagram.hostname or not (parsed_diagram.hostname == "catcar.info" or parsed_diagram.hostname.endswith(".catcar.info")):
                raise ValueError("Invalid CatCar diagram URL for %s" % sku)
            records_with_diagram += 1

        hotspots = diagram.get("hotspots") or []
        if not isinstance(hotspots, list):
            raise ValueError("Diagram hotspots must be a list for %s" % sku)
        if hotspots:
            records_with_hotspots += 1
        for hotspot in hotspots:
            hotspot_count += 1
            if not text(hotspot.get("id")) or not text(hotspot.get("oem")):
                raise ValueError("Hotspot is missing position or OEM for %s" % sku)
            if clean_sku(hotspot.get("oem")) != sku:
                raise ValueError("Hotspot OEM does not match record SKU: %s" % sku)
            for field in ("x", "y", "radius"):
                value = hotspot.get(field)
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError("Hotspot %s is not numeric for %s" % (field, sku))
            if hotspot["radius"] <= 0:
                raise ValueError("Hotspot radius must be positive for %s" % sku)

    return {
        "records_validated": record_count,
        "factory_parts_validated": factory_part_count,
        "records_by_brand": dict(sorted(brands.items())),
        "records_with_compatibility_years": records_with_years,
        "records_with_engine": records_with_engine,
        "records_with_diagram_url": records_with_diagram,
        "records_with_hotspots": records_with_hotspots,
        "hotspots_validated": hotspot_count,
        "validation_passed": True,
    }


def _merge_record(existing, incoming):
    for item in incoming["factory_parts"]:
        if item not in existing["factory_parts"]:
            existing["factory_parts"].append(item)
    for vehicle in incoming["compatibility"]:
        if vehicle not in existing["compatibility"]:
            existing["compatibility"].append(vehicle)
    if text((existing.get("diagram") or {}).get("diagramUrl")) == text((incoming.get("diagram") or {}).get("diagramUrl")):
        for hotspot in (incoming.get("diagram") or {}).get("hotspots") or []:
            _append_hotspot(existing["diagram"]["hotspots"], hotspot)
    else:
        for url in incoming.get("technical_drawings") or []:
            if url not in existing["technical_drawings"]:
                existing["technical_drawings"].append(url)


def export_documents(input_paths, output_dir, max_shard_bytes=DEFAULT_MAX_SHARD_BYTES, geometry_report=None):
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Output directory must be empty; refusing stale shards")
    output_dir.mkdir(parents=True, exist_ok=True)

    geometry_index = validate_geometry_report(geometry_report) if geometry_report is not None else None
    merged = defaultdict(list)
    for input_path in input_paths:
        document = json.loads(Path(input_path).read_text(encoding="utf-8"))
        for sku, record in document_to_records(document, geometry_index=geometry_index).items():
            variants = merged[sku]
            existing = next((item for item in variants if item.get("part_id") == record.get("part_id")), None)
            if existing is None:
                variants.append(record)
            else:
                _merge_record(existing, record)

    validation = validate_export_records(merged)

    shards = defaultdict(dict)
    for sku, variants in merged.items():
        shards[sku[:2]][sku] = variants[0] if len(variants) == 1 else variants

    report_shards = []
    for prefix in sorted(shards):
        name = prefix + ".json"
        payload = json.dumps(shards[prefix], ensure_ascii=False, separators=(",", ":")) + "\n"
        encoded = payload.encode("utf-8")
        if len(encoded) > max_shard_bytes:
            raise ValueError("Shard %s exceeds the %d-byte limit" % (name, max_shard_bytes))
        (output_dir / name).write_bytes(encoded)
        variant_count = sum(len(value) if isinstance(value, list) else 1 for value in shards[prefix].values())
        report_shards.append({
            "file": name,
            "sku_keys": len(shards[prefix]),
            "records": variant_count,
            "bytes": len(encoded),
        })

    record_count = sum(len(value) for value in merged.values())
    report = {
        "exporter": "partscope-catcar-japanese-v1",
        "documents_read": len(input_paths),
        "records_exported": record_count,
        "unique_skus_exported": len(merged),
        "validation": validation,
        "shards": report_shards,
        "analogs_exported": 0,
        "physical_dimensions_exported": 0,
        "hotspots_exported": validation["hotspots_validated"],
        "notes": [
            "Factory catalogue rows are stored only in factory_parts.",
            "No analogues or physical dimensions are inferred.",
            "Toyota hotspots use source rectangle centres in natural image pixels after bounded image and resize-script verification." if geometry_index else "Hotspots are omitted without a verified geometry report.",
            "Multiple catalog-group records for one SKU remain separate PartScope candidates.",
            "Production export is restricted to Toyota and Nissan.",
        ],
    }
    (output_dir / "export-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export normalized Japanese catalogue JSON to PartScope shards")
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-shard-bytes", type=int, default=DEFAULT_MAX_SHARD_BYTES)
    parser.add_argument("--geometry-report", type=Path, help="Verified CatCar diagram geometry report")
    args = parser.parse_args(argv)
    geometry_report = json.loads(args.geometry_report.read_text(encoding="utf-8")) if args.geometry_report else None
    report = export_documents(args.input, args.output, args.max_shard_bytes, geometry_report=geometry_report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
