"""Validate adapters against previously captured, bounded CatCar probe artifacts.

This tool is offline: it reads only the supplied artifact directories and never
contacts CatCar. Raw HTML stays in the temporary GitHub Actions workspace.
"""
import argparse
import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import jsonschema

from .adapters import FordAdapter, NissanAdapter, ToyotaAdapter, VagAdapter
from .normalize import normalize_page


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def catcar_filter_params(source_url):
    """Decode CatCar's l= filter without guessing absent vehicle fields."""
    encoded = parse_qs(urlsplit(source_url).query).get("l", [""])[0]
    if not encoded:
        return {}
    padded = encoded + ("=" * (-len(encoded) % 4))
    try:
        decoded = base64.b64decode(padded).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return {}
    params = {}
    for item in decoded.split("||"):
        if "==" not in item:
            continue
        key, value = item.split("==", 1)
        params[key.strip()] = value.strip()
    return params


def nissan_context_from_url(source_url):
    """Build only the Nissan context explicitly encoded in the captured URL."""
    params = catcar_filter_params(source_url)
    context = {
        "brand": "Nissan",
        "model": "PIXO (UA0)",
        "catalog_id": params.get("mod_id", "43"),
        "region": "Europe LHD",
    }
    start = params.get("start")
    end = params.get("end")
    if start or end:
        context["production_period_raw"] = "%s — %s" % (start or "", end or "")
    group_start = params.get("startgrp")
    group_end = params.get("endgrp")
    if group_start or group_end:
        context["source_group_period_raw"] = "%s — %s" % (group_start or "", group_end or "")
    return context


def validate_case(name, adapter, html_path, source_url, context, schema, output_dir, oem_records=None):
    html_path = Path(html_path)
    html = html_path.read_text(encoding="utf-8", errors="replace")
    parsed = adapter.parse(html)
    document = normalize_page(parsed, context, source_url, oem_records=oem_records or [])
    jsonschema.validate(instance=document, schema=schema)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (name + ".json")
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    matching = document["validation"]["hotspot_matching"]
    metrics = {
        "name": name,
        "adapter": document["source"]["adapter"],
        "source_url": source_url,
        "raw_table_row_count": document["validation"]["raw_table_row_count"],
        "part_row_count": document["validation"]["part_row_count"],
        "diagram_count": document["validation"]["diagram_count"],
        "hotspot_count": document["validation"]["hotspot_count"],
        "matched_position_count": len(matching["matched"]),
        "hotspots_without_row_count": len(matching["hotspots_without_row"]),
        "rows_without_hotspot_count": len(matching["rows_without_hotspot"]),
        "oem_record_count": len(document["oem_records"]),
        "catalog_engine_present": bool(document["catalog_context"].get("engine_code") or document["catalog_context"].get("engine")),
        "catalog_production_period_present": bool(document["catalog_context"].get("production_period_raw") or document["catalog_context"].get("production_period")),
        "no_applicable_data_oem_record_count": sum(
            item.get("source_status") == "no_applicable_data" for item in document["oem_records"]
        ),
        "schema_valid": True,
        "output": str(output_path),
    }

    if metrics["part_row_count"] < 1:
        raise ValueError("%s: no part rows parsed" % name)
    if metrics["diagram_count"] < 1:
        raise ValueError("%s: no confirmed diagram image parsed" % name)
    if metrics["hotspot_count"] < 1 or metrics["matched_position_count"] < 1:
        raise ValueError("%s: no hotspot-to-row matches" % name)
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    root = args.root
    schema = load_json(args.schema)
    results = []

    # Toyota group page and the separately captured AJAX response pages.
    toyota_dir = root / "toyota-group"
    toyota_meta = load_json(toyota_dir / "catalog_records.json")
    oem_records = []
    no_applicable_pages = []
    for page in sorted(toyota_dir.glob("part-*.html")):
        source_row_id = page.stem[len("part-"):]
        body = page.read_text(encoding="utf-8", errors="replace")
        records = ToyotaAdapter.parse_ajax_records(body, source_row_id=source_row_id)
        oem_records.extend(records)
        if any(item.get("source_status") == "no_applicable_data" for item in records):
            no_applicable_pages.append(source_row_id)

    vehicle = toyota_meta["vehicle"]
    group = toyota_meta["group"]
    toyota_context = {
        "brand": vehicle["make"],
        "model": vehicle["model"],
        "catalog_id": vehicle["catalog_id"],
        "modification_name": vehicle["modification"],
        "engine_code": vehicle["engine"],
        "production_period_raw": vehicle["modification_period"],
        "source_group_id": group["id"],
        "group_label_raw": group["name"],
    }
    toyota_url = (
        "https://www.catcar.info/toyota/?l="
        "bWFya2V0PT1qYXBhbnx8c3Q9PTcwfHxzdHM9PXsiMTAiOiJcdTA0MjBcdTA0NGJcdTA0M2RcdTA0M2VcdTA0M2EiLCIyMCI6Ilx1MDQyZlx1MDQxZlx1MDQxZVx1MDQxZFx1MDQxOFx1MDQyZiIsIjMwIjoiQ0FNUlkgMjg0MTcwIiwiNjAiOiJBQ1YzMC1BRVBOSyIsIjcwIjoiMTUtMDIgXHUwNDI0XHUwNDE4XHUwNDFiXHUwNDJjXHUwNDIyXHUwNDIwIFx1MDQxY1x1MDQxMFx1MDQyMVx1MDQxYlx1MDQyZlx1MDQxZFx1MDQyYlx1MDQxOSJ9fHxjYXRhbG9nPT0yODQxNzB8fHJlYz09QTF8fG1vZGlmbmFtZT09QUNWMzAtQUVQTkt8fGVuZ2luZT09MkFaRkV8fG1vZGVsbm89PTAwMXx8UHJvZlBlcmlvZD09MjAwMTA5MjAwNjAxfHxtb2RfaW5mbzA9PTI0R3x8Z3JvdXBfaWQ9PTE1MDJ8fHBhZ2U3MD09MA%3D%3D"
    )
    results.append(validate_case(
        "toyota-camry-oil-filter",
        ToyotaAdapter(),
        toyota_dir / "camry-oil-filter.html",
        toyota_url,
        toyota_context,
        schema,
        args.output,
        oem_records=oem_records,
    ))

    # Nissan, Ford, and VAG metadata are read from the captured probe summaries.
    nissan_dir = root / "nissan"
    nissan_meta = load_json(nissan_dir / "nissan-pixo-inspection.json")
    results.append(validate_case(
        "nissan-pixo",
        NissanAdapter(),
        nissan_dir / "nissan-pixo-catalog.html",
        nissan_meta["url"],
        nissan_context_from_url(nissan_meta["url"]),
        schema,
        args.output,
    ))

    ford_dir = root / "ford"
    ford_meta = load_json(ford_dir / "ford-fiesta-detail.json")
    results.append(validate_case(
        "ford-fiesta",
        FordAdapter(),
        ford_dir / "ford-fiesta-detail.html",
        ford_meta["detail_url"],
        {"brand": "Ford", "model": "Fiesta", "catalog_id": "424"},
        schema,
        args.output,
    ))

    vag_dir = root / "vag"
    vag_meta = load_json(vag_dir / "vw-inspection.json")
    results.append(validate_case(
        "vag-campmob",
        VagAdapter(),
        vag_dir / "vw-leaf.html",
        vag_meta["url"],
        {"brand": "Volkswagen", "model": "Campmob. (Typ2/Transp./LT)", "region": "Europe", "model_year": "2018", "source_group_id": "86735"},
        schema,
        args.output,
    ))

    report = {
        "validation_type": "offline_real_artifact_regression",
        "network_requests": 0,
        "cases": results,
        "toyota_no_applicable_data_page_count": len(no_applicable_pages),
        "toyota_no_applicable_data_source_row_ids": no_applicable_pages,
        "all_schema_valid": all(item["schema_valid"] for item in results),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
