"""
Filter MTurk HIT JSON exports by month and/or date range and write a date-sorted JSON file.

Input format: top-level object keyed by submission id, each value contains a "timestamp" field.
Output format (default): dict keyed by submission id, same shape as input, with out-of-range entries removed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class FilterConfig:
    start: datetime | None
    end: datetime | None
    month: int | None
    year: int | None


def _parse_timestamp(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        # Accept ISO 8601 with Z suffix.
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_date(date_str: str) -> datetime:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.replace(tzinfo=timezone.utc)


def _parse_month(value: str) -> int:
    value = value.strip().lower()
    if value.isdigit():
        month = int(value)
        if 1 <= month <= 12:
            return month
        raise ValueError(f"Month must be between 1 and 12, got {value}.")
    if value in MONTHS:
        return MONTHS[value]
    raise ValueError(f"Unrecognized month: {value}")


def _build_filter(args: argparse.Namespace) -> FilterConfig:
    start = _parse_date(args.start) if args.start else None
    end = _parse_date(args.end) if args.end else None
    if end is not None:
        end = datetime.combine(end.date(), time.max, tzinfo=timezone.utc)

    month = _parse_month(args.month) if args.month else None
    year = int(args.year) if args.year else None
    return FilterConfig(start=start, end=end, month=month, year=year)


def _matches_filter(dt: datetime, cfg: FilterConfig) -> bool:
    if cfg.start and dt < cfg.start:
        return False
    if cfg.end and dt > cfg.end:
        return False
    if cfg.month and dt.month != cfg.month:
        return False
    if cfg.year and dt.year != cfg.year:
        return False
    return True


def _sorted_entries(entries: Iterable[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any], datetime]]:
    out: list[tuple[str, dict[str, Any], datetime]] = []
    for key, value in entries:
        ts = _parse_timestamp(value.get("timestamp"))
        if ts is None:
            continue
        out.append((key, value, ts))
    out.sort(key=lambda item: item[2])
    return out


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Expected top-level JSON object keyed by submission id.")
    return data


def _write_output(
    items: list[tuple[str, dict[str, Any], datetime]],
    output: Path,
    fmt: str,
) -> None:
    if fmt == "list":
        payload = []
        for key, value, _ in items:
            entry = dict(value)
            entry["submissionId"] = key
            payload.append(entry)
    else:
        ordered = OrderedDict()
        for key, value, _ in items:
            ordered[key] = value
        payload = ordered

    output.write_text(json.dumps(payload, indent=2, ensure_ascii=True))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter MTurk HIT JSON exports by month and/or date range.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input JSON (e.g., src/mturk_results/1-8HIT.json).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output JSON (date-sorted).",
    )
    parser.add_argument(
        "--month",
        help="Month name or number (e.g., January or 1).",
    )
    parser.add_argument(
        "--year",
        help="Year (e.g., 2026). Optional when using --month.",
    )
    parser.add_argument(
        "--start",
        help="Start date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end",
        help="End date (YYYY-MM-DD). Inclusive.",
    )
    parser.add_argument(
        "--output-format",
        choices=("list", "dict"),
        default="dict",
        help="Output as dict keyed by submission id (default) or sorted list.",
    )

    args = parser.parse_args()
    cfg = _build_filter(args)

    data = _load_json(Path(args.input))

    kept: list[tuple[str, dict[str, Any], datetime]] = []
    skipped_missing = 0
    for key, value in data.items():
        ts = _parse_timestamp(value.get("timestamp"))
        if ts is None:
            skipped_missing += 1
            continue
        if _matches_filter(ts, cfg):
            kept.append((key, value, ts))

    kept.sort(key=lambda item: item[2])
    _write_output(kept, Path(args.output), args.output_format)

    print(f"Total entries: {len(data)}")
    print(f"Matched entries: {len(kept)}")
    if skipped_missing:
        print(f"Skipped (missing/invalid timestamp): {skipped_missing}", file=sys.stderr)
    print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
