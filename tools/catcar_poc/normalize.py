def normalize_page(adapter_result, context, source_url, oem_records=None):
    """Convert an adapter result into the shared draft JSON structure.

    Context is caller-supplied metadata; this function never guesses vehicle data.
    """
    context = dict(context or {})
    parts = []
    for part in adapter_result.get("parts", []):
        parts.append({
            "source_row_id": part.get("source_row_id"),
            "source_row_order": part.get("source_row_order"),
            "diagram_position_code": part.get("diagram_position_code"),
            "part_number_raw": part.get("part_number_raw"),
            "description_raw": part.get("description_raw", ""),
            "production_period_raw": part.get("production_period_raw", ""),
            "quantity_raw": part.get("quantity_raw", ""),
            "alternative_number_raw": part.get("alternative_number_raw", ""),
            "row_kind": part.get("row_kind", "positioned"),
            "parent_position_code": part.get("parent_position_code"),
            "source_status": part.get("source_status", "available"),
            "additional_source_fields": dict(part.get("additional_source_fields", {})),
        })

    position_to_rows = {}
    for part in parts:
        position = part.get("diagram_position_code")
        if position:
            position_to_rows.setdefault(position, []).append(part.get("source_row_id"))

    images = adapter_result.get("images", [])
    diagram_images = [image for image in images if image.get("image_kind") == "diagram"]
    diagrams = []
    for index, image in enumerate(diagram_images):
        diagrams.append({
            "diagram_id": "diagram-%d" % (index + 1),
            "source_image_url": image.get("src", ""),
            "source_image_path": None,
            "source_format": None,
            "source_group_id": context.get("source_group_id"),
        })

    first_diagram_id = diagrams[0]["diagram_id"] if diagrams else None
    matching = adapter_result.get("hotspot_matching", {})
    matched = set(matching.get("matched", []))
    unresolved = set(matching.get("hotspots_without_row", []))
    hotspots = []
    for index, hotspot in enumerate(adapter_result.get("hotspots", [])):
        position = hotspot.get("position_code", "").strip()
        linked_rows = position_to_rows.get(position, [])
        if position in matched:
            status = "matched"
        elif position in unresolved or position:
            status = "unmatched"
        else:
            status = "ambiguous"
        hotspots.append({
            "hotspot_id": "hotspot-%d" % (index + 1),
            "diagram_id": first_diagram_id,
            "source_position_code": position or None,
            "source_row_id": linked_rows[0] if len(linked_rows) == 1 else None,
            "source_row_ids": linked_rows,
            "top_raw": hotspot.get("top", ""),
            "left_raw": hotspot.get("left", ""),
            "width_raw": hotspot.get("width", ""),
            "height_raw": hotspot.get("height", ""),
            "resolution_status": status,
        })

    return {
        "schema_version": "0.1-draft",
        "source": {
            "name": "CatCar",
            "adapter": adapter_result.get("adapter"),
            "url": source_url,
        },
        "catalog_context": context,
        "parts": parts,
        "oem_records": [
            {
                "oem_number_raw": item.get("oem_number_raw"),
                "production_period_raw": item.get("production_period_raw"),
                "applicability_raw": item.get("applicability_raw"),
                "source_detail_url": item.get("source_detail_url"),
                "source_record_id": item.get("source_record_id"),
                "source_row_id": item.get("source_row_id"),
                "source_status": item.get("source_status", "available"),
                "source_record_order": item.get("source_record_order"),
                "source_group_id": item.get("source_group_id"),
                "source_url": item.get("source_url"),
            }
            for item in (oem_records or [])
        ],
        "diagrams": diagrams,
        "hotspots": hotspots,
        "validation": {
            "page_status": adapter_result.get("page_status", "unknown"),
            "page_warnings": list(adapter_result.get("page_warnings", [])),
            "hotspot_matching": matching,
            "raw_table_row_count": len(adapter_result.get("rows", [])),
            "part_row_count": len(parts),
            "diagram_count": len(diagrams),
            "hotspot_count": len(hotspots),
        },
    }
