"""Offline CLI for converting one saved CatCar HTML page to normalized JSON.

This command never performs network requests. Toyota AJAX responses can be
provided separately through --oem-records as a JSON array.
"""
import argparse
import json
from pathlib import Path

from .adapters import FordAdapter, NissanAdapter, ToyotaAdapter, VagAdapter
from .normalize import normalize_page


ADAPTERS = {
    "toyota": ToyotaAdapter,
    "nissan": NissanAdapter,
    "ford": FordAdapter,
    "vag": VagAdapter,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Normalize one saved CatCar HTML page")
    parser.add_argument("--adapter", required=True, choices=sorted(ADAPTERS))
    parser.add_argument("--input", required=True, type=Path, help="Saved HTML file")
    parser.add_argument("--output", required=True, type=Path, help="Output JSON file")
    parser.add_argument("--source-url", required=True, help="Original page URL")
    parser.add_argument("--context", type=Path, help="JSON object with explicit catalog metadata")
    parser.add_argument("--oem-records", type=Path, help="JSON array of already extracted Toyota OEM records")
    args = parser.parse_args(argv)

    html = args.input.read_text(encoding="utf-8", errors="replace")
    context = json.loads(args.context.read_text(encoding="utf-8")) if args.context else {}
    oem_records = json.loads(args.oem_records.read_text(encoding="utf-8")) if args.oem_records else []

    if not isinstance(context, dict):
        parser.error("--context must contain a JSON object")
    if not isinstance(oem_records, list):
        parser.error("--oem-records must contain a JSON array")

    adapter = ADAPTERS[args.adapter]()
    adapter_result = adapter.parse(html)
    document = normalize_page(
        adapter_result,
        context,
        args.source_url,
        oem_records=oem_records,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
