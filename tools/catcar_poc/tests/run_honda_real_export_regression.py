"""Run the offline PartScope exporter against six captured Honda CatCar pages.

The inputs are GitHub Actions artifacts from bounded, previously completed probes.
No network requests are made by this script.
"""
import json
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from tools.catcar_poc.adapters import HondaAdapter
from tools.catcar_poc.normalize import normalize_page
from tools.catcar_poc.export_partscope import export_documents


GROUPS = [
    ("E-1", "e1", "honda-accord-e1-throttle-body.html", "honda-accord-e1-inspection.json", 6, 9,
     "https://ci.catcar.info/honda/euro/18TA0801/IMGE/E__0100.png"),
    ("B-28", "b28", "honda-accord-b28.html", "honda-accord-b28-inspection.json", 31, 20,
     "https://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2800.png"),
    ("B-22", "b22", "honda-accord-b22.html", "honda-accord-b22-inspection.json", 25, 23,
     "https://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2200.png"),
    ("B-19-10", "b19-10", "honda-accord-b19-10.html", "honda-accord-b19-10-inspection.json", 36, 26,
     "https://ci.catcar.info/honda/euro/18TA0801/IMGE/B__1910.png"),
    ("B-29", "b29", "honda-accord-b29.html", "honda-accord-b29-inspection.json", 44, 41,
     "https://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2900.png"),
    ("B-27-10", "b27-10", "honda-accord-b27-10.html", "honda-accord-b27-10-inspection.json", 23, 20,
     "https://ci.catcar.info/honda/euro/18TA0801/IMGE/B__2710.png"),
]


def read_json(path):
    raw = Path(path).read_text(encoding="utf-8")
    return json.JSONDecoder().raw_decode(raw.lstrip())[0]


def main(root):
    root = Path(root)
    docs_dir = root / "normalized"
    if docs_dir.exists():
        shutil.rmtree(docs_dir)
    docs_dir.mkdir(parents=True)

    adapter = HondaAdapter()
    documents = []
    summary = []
    total_parts = 0
    all_rows_by_group = {}

    for group_id, folder, html_name, json_name, expected_parts, expected_hotspots, expected_image in GROUPS:
        folder_path = root / "sources" / folder
        metadata = read_json(folder_path / json_name)
        html_path = folder_path / html_name
        html = html_path.read_text(encoding="utf-8", errors="replace")
        if metadata.get("http_status") != 200:
            raise AssertionError("%s source response is not HTTP 200" % group_id)
        if metadata.get("region") != "Austria (KW)":
            raise AssertionError("%s sample region changed; expected Austria (KW)" % group_id)
        parsed = adapter.parse(html)
        parts = parsed["parts"]
        if len(parts) != expected_parts:
            raise AssertionError("%s: expected %d source rows, parsed %d" %
                                 (group_id, expected_parts, len(parts)))
        if len(parsed["hotspots"]) != expected_hotspots:
            raise AssertionError("%s: expected %d hotspots, parsed %d" %
                                 (group_id, expected_hotspots, len(parsed["hotspots"])))
        diagram_images = [x for x in parsed["images"] if x.get("image_kind") == "diagram"]
        if len(diagram_images) != 1 or diagram_images[0].get("src") != expected_image:
            raise AssertionError("%s diagram URL mismatch: %r" % (group_id, diagram_images))
        # Check actual adapter rows against the independently captured inspection table.
        table_rows = metadata["table_rows"]
        header = next(i for i, row in enumerate(table_rows)
                      if len(row) >= 3 and [str(x).strip().lower() for x in row[:3]] ==
                      ["код", "артикул", "описание"])
        inspected_parts = [row for row in table_rows[header + 1:]
                           if len(row) >= 3 and str(row[1]).strip()]
        if len(inspected_parts) != len(parts):
            raise AssertionError("%s: inspection/adapter row counts differ" % group_id)
        for index, (row, inspected) in enumerate(zip(parts, inspected_parts)):
            raw_cells = row["additional_source_fields"]["raw_cells"]
            if raw_cells[:3] != inspected[:3]:
                raise AssertionError("%s row %d changed position/OEM/description" % (group_id, index))
            if row["additional_source_fields"]["option_codes_raw"] != (
                    inspected[4].strip() if len(inspected) > 4 else ""):
                raise AssertionError("%s row %d lost option codes" % (group_id, index))

        context = {
            "brand": "Honda",
            "model": "Accord",
            "model_year": str(metadata["year"]),
            "region": metadata["region"],
            "transmission": metadata["transmission"],
            "grade": metadata["grade"],
            "source_group_id": group_id,
            "group_label_raw": metadata.get("subgroup") or metadata.get("group") or group_id,
        }
        document = normalize_page(parsed, context, metadata["final_url"])
        if len(document["parts"]) != expected_parts or len(document["diagrams"]) != 1:
            raise AssertionError("%s normalized document lost parts or diagram" % group_id)
        if len([x for x in document["hotspots"] if x["resolution_status"] == "matched"]) != expected_hotspots:
            raise AssertionError("%s normalized document lost matched hotspots" % group_id)
        output_path = docs_dir / (folder + ".json")
        output_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        documents.append(output_path)
        total_parts += expected_parts
        all_rows_by_group[group_id] = parts
        summary.append({
            "group": group_id, "part_rows": len(parts),
            "unique_oem": len(set(x["part_number_raw"] for x in parts)),
            "hotspots": len(parsed["hotspots"]), "diagram": expected_image,
        })

    # Build the geometry report only from the previously audited real PNGs.
    audit_dir = root / "audit"
    audit_files = {
        "E-1": "honda-diagram-audit.json",
        "B-28": "honda-b28-diagram-audit.json",
        "B-22": "honda-b22-diagram-audit.json",
        "B-19-10": "honda-b19-10-diagram-audit.json",
        "B-29": "honda-b29-diagram-audit.json",
        "B-27-10": "honda-b2710-diagram-audit.json",
    }
    geometry = {
        "coordinate_script": {"relevant_snippets": [
            "srcTop srcLeft srcWidth srcHeight h/nh w/nw"
        ]},
        "main_css": {"relevant_snippets": [
            ".resize { width:100%; height:100%; }"
        ]},
        "images": [],
    }
    for group_id, filename in audit_files.items():
        audit = read_json(audit_dir / filename)
        if audit.get("http_status") != 200 or audit.get("content_type") != "image/png":
            raise AssertionError("%s diagram was not verified as PNG" % group_id)
        if audit.get("all_hotspots_inside_image") is not True:
            raise AssertionError("%s contains out-of-bounds hotspot rectangles" % group_id)
        geometry["images"].append({
            "image_url": audit["diagram_url"],
            "http_status": audit["http_status"],
            "content_type": audit["content_type"],
            "image_dimensions": audit["dimensions"],
            "hotspot_count": audit["hotspot_count"],
            "all_hotspot_boxes_inside_image_bounds": audit["all_hotspots_inside_image"],
        })

    output_dir = root / "export"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    report = export_documents(documents, output_dir, geometry_report=geometry)
    if report["documents_read"] != len(GROUPS):
        raise AssertionError("Not all six real catalog groups were exported")
    if report["validation"]["factory_parts_validated"] != total_parts:
        raise AssertionError("Factory row count mismatch: expected %d, got %d" %
                             (total_parts, report["validation"]["factory_parts_validated"]))
    if report["validation"]["hotspots_validated"] <= 0:
        raise AssertionError("No verified hotspots were exported")

    shard_records = {}
    for shard_path in output_dir.glob("*.json"):
        if shard_path.name == "export-report.json":
            continue
        shard_records.update(read_json(shard_path))

    variants = {}
    for sku, value in shard_records.items():
        variants[sku] = value if isinstance(value, list) else [value]
        for record in variants[sku]:
            if record["brand"] != "Honda":
                raise AssertionError("Non-Honda record leaked into Honda export")
            if record["compatibility"][0]["years"] != "2011":
                raise AssertionError("2011 compatibility context was lost for %s" % sku)
            if record["compatibility"][0]["engine"] != "":
                raise AssertionError("Unverified engine code was invented for %s" % sku)
            if not record["diagram"]["diagramUrl"]:
                raise AssertionError("Diagram URL missing for %s" % sku)

    # Real OEMs shared between different groups must remain separate candidates.
    shared = {
        "43352SM4951": {"B-22", "B-19-10"},
        "43353SD5003": {"B-22", "B-19-10"},
        "93600060140H": {"B-22", "B-19-10"},
        "90306SB2013": {"B-29", "B-27-10"},
    }
    for sku, expected_groups in shared.items():
        candidates = variants.get(sku, [])
        actual_groups = {x["part_id"].split(":")[-1] for x in candidates}
        if actual_groups != expected_groups:
            raise AssertionError("%s group candidates mismatch: %r" % (sku, actual_groups))
        if len({x["diagram"]["diagramUrl"] for x in candidates}) != len(expected_groups):
            raise AssertionError("%s candidates lost their separate diagrams" % sku)

    # All source rows, including option variants, must survive as factory rows.
    exported_factory_rows = sum(len(record["factory_parts"])
                                for values in variants.values() for record in values)
    if exported_factory_rows != total_parts:
        raise AssertionError("Factory rows did not round-trip: expected %d, got %d" %
                             (total_parts, exported_factory_rows))

    final = {
        "validation_passed": True,
        "source_region": "Austria (KW), not JDM",
        "groups": summary,
        "source_part_rows": total_parts,
        "exported_factory_rows": exported_factory_rows,
        "unique_cleaned_skus": report["unique_skus_exported"],
        "partscope_candidates": report["records_exported"],
        "verified_diagrams": len(geometry["images"]),
        "exported_hotspot_associations": report["hotspots_exported"],
        "shared_oem_cross_group_candidates": {
            sku: sorted({x["part_id"].split(":")[-1] for x in variants[sku]})
            for sku in shared
        },
        "export_report": report,
    }
    (root / "honda-real-export-regression-report.json").write_text(
        json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: run_honda_real_export_regression.py ROOT")
    raise SystemExit(main(sys.argv[1]))
