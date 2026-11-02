"""Offline conversion from normalized Japanese CatCar JSON to PartScope shards."""
import argparse
import json
import posixpath
import re
from collections import defaultdict
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
            "source_url": source_url,
        }
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
