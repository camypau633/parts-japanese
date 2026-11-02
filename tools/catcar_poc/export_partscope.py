"""Offline conversion from normalized Japanese CatCar JSON to PartScope shards."""
import argparse
import json
import posixpath
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

SUPPORTED_BRANDS = {"Toyota", "Nissan"}
DEFAULT_MAX_SHARD_BYTES = 2 * 1024 * 1024


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
    # PartScope is hosted over HTTPS; HTTP images would be blocked as mixed
    # content. CatCar's image host uses the site's wildcard TLS certificate.
    if parts.hostname and parts.hostname.endswith("catcar.info"):
        parts = parts._replace(scheme="https")
    # Source paths occasionally contain literal spaces in image filenames.
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


def document_to_records(document):
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
            record = {
                "part_id": "%s:%s" % (brand.lower(), sku),
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
    return result



def validate_export_records(records):
    """Fail closed on broken SKU, OEM provenance, or app-facing structure."""
    brands = Counter()
    records_with_years = 0
    records_with_engine = 0
    records_with_diagram = 0
    factory_part_count = 0

    for sku, record in records.items():
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

        diagram_url = text((record.get("diagram") or {}).get("diagramUrl"))
        if diagram_url:
            parsed_diagram = urlsplit(diagram_url)
            if parsed_diagram.scheme not in ("http", "https") or not parsed_diagram.hostname or not (parsed_diagram.hostname == "catcar.info" or parsed_diagram.hostname.endswith(".catcar.info")):
                raise ValueError("Invalid CatCar diagram URL for %s" % sku)
            records_with_diagram += 1

    return {
        "records_validated": len(records),
        "factory_parts_validated": factory_part_count,
        "records_by_brand": dict(sorted(brands.items())),
        "records_with_compatibility_years": records_with_years,
        "records_with_engine": records_with_engine,
        "records_with_diagram_url": records_with_diagram,
        "validation_passed": True,
    }

def export_documents(input_paths, output_dir, max_shard_bytes=DEFAULT_MAX_SHARD_BYTES):
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Output directory must be empty; refusing stale shards")
    output_dir.mkdir(parents=True, exist_ok=True)

    merged = {}
    for input_path in input_paths:
        document = json.loads(Path(input_path).read_text(encoding="utf-8"))
        for sku, record in document_to_records(document).items():
            existing = merged.get(sku)
            if existing is None:
                merged[sku] = record
                continue
            for item in record["factory_parts"]:
                if item not in existing["factory_parts"]:
                    existing["factory_parts"].append(item)
            for vehicle in record["compatibility"]:
                if vehicle not in existing["compatibility"]:
                    existing["compatibility"].append(vehicle)

    validation = validate_export_records(merged)

    shards = defaultdict(dict)
    for sku, record in merged.items():
        shards[sku[:2]][sku] = record

    report_shards = []
    for prefix in sorted(shards):
        name = prefix + ".json"
        payload = json.dumps(shards[prefix], ensure_ascii=False, separators=(",", ":")) + "\n"
        encoded = payload.encode("utf-8")
        if len(encoded) > max_shard_bytes:
            raise ValueError("Shard %s exceeds the %d-byte limit" % (name, max_shard_bytes))
        (output_dir / name).write_bytes(encoded)
        report_shards.append({"file": name, "records": len(shards[prefix]), "bytes": len(encoded)})

    report = {
        "exporter": "partscope-catcar-japanese-v1",
        "documents_read": len(input_paths),
        "records_exported": len(merged),
        "validation": validation,
        "shards": report_shards,
        "analogs_exported": 0,
        "physical_dimensions_exported": 0,
        "hotspots_exported": 0,
        "notes": [
            "Factory catalogue rows are stored only in factory_parts.",
            "No analogues or physical dimensions are inferred.",
            "Hotspots are omitted until source coordinates are calibrated to image coordinates.",
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
    args = parser.parse_args(argv)
    report = export_documents(args.input, args.output, args.max_shard_bytes)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
