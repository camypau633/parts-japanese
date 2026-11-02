"""Offline normalizer for bounded Toyota CatCar group/AJAX probe artifacts.

It requires the raw group HTML saved by the probe so part rows, diagrams and
hotspots are linked from the same source page. It performs no network access.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import jsonschema

from .adapters import ToyotaAdapter
from .normalize import normalize_page
from .validate_real_artifacts import catcar_filter_params


def _catcar_url(value):
    parsed = urlsplit(value or "")
    host = (parsed.hostname or "").lower()
    return parsed.scheme in ("http", "https") and (
        host == "catcar.info" or host.endswith(".catcar.info")
    )


def _profile_period(value):
    """Decode the explicitly encoded CatCar YYYYMMYYYYMM profile period."""
    match = re.fullmatch(r"(\d{4})(\d{2})(\d{4})(\d{2})", str(value or ""))
    if not match:
        return None
    sy, sm, ey, em = [int(part) for part in match.groups()]
    if not (1 <= sm <= 12 and 1 <= em <= 12):
        return None
    return "%02d/%04d-%02d/%04d" % (sm, sy, em, ey)


def _group_metadata(group):
    url = group.get("url", "")
    params = catcar_filter_params(url)
    group_id = str(group.get("group_id") or params.get("group_id") or "").strip()
    label = str(group.get("label_raw") or "").strip()
    if not label:
        try:
            filters = json.loads(params.get("sts", "{}"))
        except (TypeError, ValueError):
            filters = {}
        label = str(filters.get("70") or "").strip()
    if not group_id:
        raise ValueError("Group URL has no explicit CatCar group_id")
    return group_id, label, params


def _safe_source_file(root, relative_path):
    path = (root / str(relative_path or "")).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        raise ValueError("Source HTML path escapes the artifact directory")
    if not path.is_file():
        raise ValueError("Missing saved source HTML: %s" % relative_path)
    return path


def normalize_sample(sample, artifact_dir, schema):
    vehicle = sample.get("vehicle") or {}
    if str(vehicle.get("make", "")).casefold() != "toyota":
        raise ValueError("This normalizer accepts Toyota samples only")
    for field in ("model", "catalog_id", "modification", "engine"):
        if not str(vehicle.get(field) or "").strip():
            raise ValueError("Toyota sample is missing vehicle.%s" % field)

    root = Path(artifact_dir)
    output_documents = []
    seen_groups = set()
    total_parts = 0
    total_oem_records = 0
    unique_oems = set()

    for group in sample.get("sampled_groups") or []:
        group_url = group.get("url", "")
        if not _catcar_url(group_url):
            raise ValueError("Invalid CatCar group URL")
        group_id, group_label, filter_params = _group_metadata(group)
        if group_id in seen_groups:
            raise ValueError("Duplicate CatCar group_id: %s" % group_id)
        seen_groups.add(group_id)

        group_file = _safe_source_file(root, group.get("source_page_file"))
        html = group_file.read_text(encoding="utf-8", errors="replace")
        parsed = ToyotaAdapter().parse(html)
        sampled_parts = group.get("parts") or []
        sampled_ids = [str(item.get("part_number") or "").strip() for item in sampled_parts]
        parsed_ids = [str(item.get("source_row_id") or "").strip() for item in parsed.get("parts", [])]

        if any(not value for value in sampled_ids):
            raise ValueError("Group %s contains a part row without part_number" % group_id)
        if len(sampled_ids) != len(set(sampled_ids)):
            raise ValueError("Group %s contains duplicate sampled part numbers" % group_id)
        if set(sampled_ids) != set(parsed_ids) or len(sampled_ids) != len(parsed_ids):
            raise ValueError(
                "Group %s sampled part rows do not match saved HTML (sampled=%d, html=%d)"
                % (group_id, len(sampled_ids), len(parsed_ids))
            )

        part_by_id = {str(item["source_row_id"]): item for item in parsed["parts"]}
        normalized_parts = []
        oem_records = []
        for order, sample_part in enumerate(sampled_parts):
            part_number = str(sample_part["part_number"]).strip()
            parsed_part = part_by_id[part_number]
            source_status = sample_part.get("source_status", "available")
            records = sample_part.get("records") or []
            ajax_url = sample_part.get("ajax_url", "")
            if not _catcar_url(ajax_url):
                raise ValueError("Part %s has no valid source AJAX URL" % part_number)
            if sample_part.get("ajax_http") != 200:
                raise ValueError("Part %s AJAX response was not HTTP 200" % part_number)
            if sample_part.get("error"):
                raise ValueError("Part %s AJAX extraction failed: %s" % (part_number, sample_part["error"]))
            if source_status == "empty_unclassified":
                raise ValueError("Part %s has an empty, unclassified AJAX response" % part_number)
            if source_status == "available" and not records:
                raise ValueError("Part %s is marked available but has no OEM records" % part_number)
            if source_status == "no_applicable_data" and records:
                raise ValueError("Part %s is marked no_applicable_data but has OEM rows" % part_number)
            if source_status not in ("available", "no_applicable_data"):
                raise ValueError("Part %s has unsupported source status %r" % (part_number, source_status))

            normalized_parts.append({
                "source_row_id": part_number,
                "source_row_order": order,
                "diagram_position_code": parsed_part.get("diagram_position_code"),
                "part_number_raw": None,
                "description_raw": "",
                "production_period_raw": "",
                "quantity_raw": "",
                "alternative_number_raw": "",
                "row_kind": "positioned",
                "parent_position_code": None,
                "source_status": "requires_ajax" if source_status == "available" else "no_applicable_data",
                "additional_source_fields": {
                    "ajax_token": parsed_part.get("ajax_token", ""),
                    "source_page_file": sample_part.get("source_page_file", ""),
                },
            })

            total_parts += 1
            if source_status == "no_applicable_data":
                oem_records.append({
                    "oem_number_raw": None,
                    "production_period_raw": None,
                    "applicability_raw": None,
                    "source_record_id": None,
                    "source_row_id": part_number,
                    "source_status": "no_applicable_data",
                    "source_record_order": None,
                    "source_group_id": group_id,
                    "source_url": ajax_url,
                })
                total_oem_records += 1
                continue

            for record_order, record in enumerate(records):
                oem = str(record.get("oem") or "").strip()
                period = str(record.get("period") or "").strip()
                applicability = str(record.get("applicability") or "").strip()
                oem_records.append({
                    "oem_number_raw": oem or None,
                    "production_period_raw": period or None,
                    "applicability_raw": applicability or None,
                    "source_record_id": None,
                    "source_row_id": part_number,
                    "source_status": "available",
                    "source_record_order": record_order,
                    "source_group_id": group_id,
                    "source_url": ajax_url,
                })
                if oem:
                    unique_oems.add(oem)
            total_oem_records += len(records)

        profile_period = _profile_period(filter_params.get("ProfPeriod"))
        context = {
            "brand": "Toyota",
            "model": str(vehicle["model"]),
            "catalog_id": str(vehicle["catalog_id"]),
            "modification_name": str(vehicle["modification"]),
            "engine_code": str(vehicle["engine"]),
            "source_group_id": group_id,
            "group_label_raw": group_label,
        }
        if profile_period:
            context["production_period_raw"] = profile_period
        elif filter_params.get("ProfPeriod"):
            context["source_profile_period_raw"] = filter_params["ProfPeriod"]

        adapter_result = {
            "adapter": parsed.get("adapter"),
            "rows": parsed.get("rows", []),
            "images": parsed.get("images", []),
            "hotspots": parsed.get("hotspots", []),
            "parts": normalized_parts,
            "ajax_rows": normalized_parts,
            "hotspot_matching": ToyotaAdapter.match_hotspots(
                [part.get("diagram_position_code") for part in normalized_parts],
                parsed.get("hotspots", []),
            ),
        }
        document = normalize_page(adapter_result, context, group_url, oem_records=oem_records)
        jsonschema.validate(instance=document, schema=schema)
        output_documents.append((group_id, document))

    report = {
        "normalization": "toyota_camry_oem_variation_sample",
        "network_requests": 0,
        "group_count": len(output_documents),
        "part_row_count": total_parts,
        "oem_record_count": total_oem_records,
        "unique_oem_number_count": len(unique_oems),
        "diagram_count": sum(len(doc["diagrams"]) for _, doc in output_documents),
        "hotspot_count": sum(len(doc["hotspots"]) for _, doc in output_documents),
        "schema_valid": True,
    }
    return output_documents, report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Normalize bounded Toyota CatCar group/AJAX artifacts offline")
    parser.add_argument("--sample", type=Path, required=True, help="oem_variation_sample.json")
    parser.add_argument("--schema", type=Path, required=True, help="Shared CatCar JSON schema")
    parser.add_argument("--output", type=Path, required=True, help="Empty output directory")
    args = parser.parse_args(argv)

    output_dir = args.output
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Output directory must be empty; refusing stale normalized documents")
    output_dir.mkdir(parents=True, exist_ok=True)

    sample = json.loads(args.sample.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    documents, report = normalize_sample(sample, args.sample.parent, schema)
    for group_id, document in documents:
        path = output_dir / ("toyota-camry-group-%s.json" % group_id)
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
