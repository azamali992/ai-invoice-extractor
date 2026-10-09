"""Batch mode: a folder of documents in, one Excel file out.

    python cli.py samples/ -o invoices.xlsx --provider gemini
    python cli.py inbox/ -o out.xlsx --eval samples/expected.json   # also score accuracy
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from extractor.export import to_excel
from extractor.pipeline import SUPPORTED, process
from extractor.providers import get_provider

FIELDS = ["vendor_name", "invoice_number", "invoice_date", "due_date", "currency",
          "subtotal", "tax", "shipping", "discount", "total"]


def _same(a, b) -> bool:
    if a is None or b is None:
        return a == b
    if isinstance(b, (int, float)):
        try:
            return abs(float(a) - float(b)) < 0.005
        except (TypeError, ValueError):
            return False
    return str(a).strip().lower() == str(b).strip().lower()


def score(results, expected: dict) -> dict:
    """Field-level accuracy against ground truth, plus whether flags fired where they should."""
    correct = total = flag_hits = 0
    misses = []
    for r in results:
        truth = expected.get(r.filename)
        if not truth or not r.invoice:
            continue
        for f in FIELDS:
            total += 1
            if _same(getattr(r.invoice, f), truth.get(f)):
                correct += 1
            else:
                misses.append(f"{r.filename}: {f} got {getattr(r.invoice, f)!r}, expected {truth.get(f)!r}")
        flag_hits += (r.status == "needs review") == truth["should_flag"]
    scored = sum(1 for r in results if r.filename in expected and r.invoice)
    return {"field_accuracy": correct / total if total else 0.0, "fields_checked": total,
            "flag_correct": f"{flag_hits}/{scored}", "misses": misses}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("invoices.xlsx"))
    ap.add_argument("--provider", choices=["gemini", "claude"], default="gemini")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--eval", type=Path, help="expected.json to score against")
    args = ap.parse_args()

    files = sorted(p for p in args.folder.iterdir() if p.suffix.lower() in SUPPORTED)
    if not files:
        print(f"No supported files in {args.folder}", file=sys.stderr)
        return 1
    provider = get_provider(args.provider)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda p: process(p.name, p.read_bytes(), provider), files))

    for r in results:
        print(f"{r.status:>13}  {r.filename}")
        for issue in r.issues:
            print(f"{'':>15}- {issue.message}")
        if r.error:
            print(f"{'':>15}- {r.error}")
    args.output.write_bytes(to_excel(results))
    print(f"\nWrote {args.output}")

    if args.eval:
        report = score(results, json.loads(args.eval.read_text()))
        print(f"Field accuracy: {report['field_accuracy']:.1%} over {report['fields_checked']} fields; "
              f"flags correct on {report['flag_correct']} documents")
        for m in report["misses"]:
            print("  miss:", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
