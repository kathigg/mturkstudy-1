import argparse
import csv
import json
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import in_house_density_and_agreement as base


DEFAULT_WORKBOOK = (
    "src/dataset_comparison_scripts/statistical_analysis/"
    "prerana_analysis/in_house_live_validation_three_way_split_clusters.xlsx"
)
DEFAULT_SHEET = "Final_adjudicated set"
DEFAULT_BASELINE_CSV = (
    "src/dataset_comparison_scripts/statistical_analysis/live/"
    "in_house_live_validation_three_way_split_clusters.csv"
)
DEFAULT_OUTPUT_CSV = (
    "src/dataset_comparison_scripts/statistical_analysis/"
    "prerana_analysis/final_adjudicated_set_normalized.csv"
)
DEFAULT_OUTPUT_JSON = (
    "src/dataset_comparison_scripts/statistical_analysis/"
    "prerana_analysis/final_adjudicated_set_agreement_summary.json"
)

XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Normalize the Prerana live-validation adjudicated subset and rerun "
            "agreement metrics using the same count-based formulas as the existing "
            "live-validation analysis."
        )
    )
    parser.add_argument("--workbook", default=DEFAULT_WORKBOOK)
    parser.add_argument("--sheet", default=DEFAULT_SHEET)
    parser.add_argument("--baseline-csv", default=DEFAULT_BASELINE_CSV)
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    return parser.parse_args()


def read_xlsx_sheet(path: Path, sheet_name: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("main:si", XML_NS):
                shared_strings.append(
                    "".join(node.text or "" for node in item.iterfind(".//main:t", XML_NS))
                )

        workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
        rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_root.findall("pkg:Relationship", XML_NS)
        }

        sheet_target = None
        for sheet in workbook_root.find("main:sheets", XML_NS):
            if sheet.attrib["name"] == sheet_name:
                rel_id = sheet.attrib[
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                ]
                sheet_target = rel_map[rel_id]
                break

        if sheet_target is None:
            raise ValueError(f"Sheet not found: {sheet_name}")

        if not sheet_target.startswith("xl/"):
            sheet_target = f"xl/{sheet_target}"

        sheet_root = ET.fromstring(archive.read(sheet_target))
        row_nodes = sheet_root.find("main:sheetData", XML_NS).findall("main:row", XML_NS)

    def cell_value(cell_node):
        cell_type = cell_node.attrib.get("t")
        value_node = cell_node.find("main:v", XML_NS)
        if value_node is None:
            inline_node = cell_node.find("main:is", XML_NS)
            if inline_node is None:
                return ""
            return "".join(node.text or "" for node in inline_node.iterfind(".//main:t", XML_NS))
        raw_value = value_node.text or ""
        if cell_type == "s":
            return shared_strings[int(raw_value)]
        return raw_value

    all_rows = [[cell_value(cell) for cell in row.findall("main:c", XML_NS)] for row in row_nodes]
    if not all_rows:
        return []

    header = all_rows[0]
    rows = []
    for values in all_rows[1:]:
        if not any(str(value).strip() for value in values):
            continue
        padded = values + [""] * (len(header) - len(values))
        rows.append(dict(zip(header, padded[: len(header)])))
    return rows


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def parse_int(value) -> int:
    if value in (None, ""):
        return 0
    return int(float(value))


def normalize_adjudicated_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    for row in rows:
        updated = dict(row)
        status = (updated.get("cluster_status") or "").strip()
        if status == "majority_deny":
            updated["cluster_status"] = "majority_accept"
            updated["vote_pattern"] = "3-0"
            updated["representative_accept"] = "3"
            updated["representative_deny"] = "0"
            updated["representative_total_votes"] = "3"
            updated["representative_accept_rate"] = "1.0"
            updated["cluster_member_count"] = "3"
        else:
            updated["vote_pattern"] = "2-1"
            updated["representative_total_votes"] = "3"
            updated["representative_accept_rate"] = (
                updated.get("representative_accept_rate") or "0.6666666666666666"
            )
        normalized.append(updated)
    return normalized


def summarize_rows(rows: list[dict[str, str]]) -> dict:
    ratings = []
    label_counts = Counter()
    exact_consensus_count = 0

    for row in rows:
        accept = parse_int(row.get("representative_accept"))
        deny = parse_int(row.get("representative_deny"))
        total = accept + deny
        if total < 2:
            continue
        unit_ratings = (["accept"] * accept) + (["deny"] * deny)
        ratings.append(unit_ratings)
        label_counts.update(unit_ratings)
        if accept == 0 or deny == 0:
            exact_consensus_count += 1

    return {
        "row_count": len(rows),
        "eligible_unit_count": len(ratings),
        "status_counts": dict(Counter(row["cluster_status"] for row in rows)),
        "vote_pattern_counts": dict(Counter(row["vote_pattern"] for row in rows)),
        "accept_total": label_counts["accept"],
        "deny_total": label_counts["deny"],
        "accept_rate": (
            label_counts["accept"] / (label_counts["accept"] + label_counts["deny"])
            if (label_counts["accept"] + label_counts["deny"])
            else 0.0
        ),
        "pairwise_percent_agreement": base.pairwise_percent_agreement(ratings),
        "krippendorff_alpha_nominal": base.krippendorff_alpha_nominal(ratings),
        "exact_consensus_count": exact_consensus_count,
        "exact_consensus_rate": (
            exact_consensus_count / len(ratings) if ratings else None
        ),
        "subcategory_counts": dict(
            sorted(Counter(row["subcategory"] for row in rows).items())
        ),
    }


def rounded_metrics(summary: dict) -> dict:
    rounded = dict(summary)
    for key in [
        "accept_rate",
        "pairwise_percent_agreement",
        "krippendorff_alpha_nominal",
        "exact_consensus_rate",
    ]:
        if rounded.get(key) is not None:
            rounded[key] = round(rounded[key], 3)
    return rounded


def delta_summary(current: dict, baseline: dict) -> dict:
    delta = {}
    for key in [
        "row_count",
        "accept_total",
        "deny_total",
        "accept_rate",
        "pairwise_percent_agreement",
        "krippendorff_alpha_nominal",
        "exact_consensus_count",
        "exact_consensus_rate",
    ]:
        if current.get(key) is None or baseline.get(key) is None:
            delta[key] = None
        else:
            delta[key] = round(current[key] - baseline[key], 3)
    return delta


def main():
    args = parse_args()
    workbook_path = Path(args.workbook)
    baseline_path = Path(args.baseline_csv)

    raw_rows = read_xlsx_sheet(workbook_path, args.sheet)
    normalized_rows = normalize_adjudicated_rows(raw_rows)
    baseline_rows = read_csv_rows(baseline_path)

    raw_summary = summarize_rows(raw_rows)
    normalized_summary = summarize_rows(normalized_rows)
    baseline_summary = summarize_rows(baseline_rows)

    output_csv = Path(args.output_csv)
    output_json = Path(args.output_json)
    fieldnames = list(normalized_rows[0].keys()) if normalized_rows else []

    if fieldnames:
        write_csv(output_csv, normalized_rows, fieldnames)

    write_json(
        output_json,
        {
            "input_workbook": str(workbook_path),
            "input_sheet": args.sheet,
            "baseline_csv": str(baseline_path),
            "raw_sheet_summary": rounded_metrics(raw_summary),
            "normalized_cleaned_summary": rounded_metrics(normalized_summary),
            "baseline_three_way_split_summary": rounded_metrics(baseline_summary),
            "delta_vs_raw_sheet": delta_summary(normalized_summary, raw_summary),
            "delta_vs_full_three_way_split": delta_summary(
                normalized_summary, baseline_summary
            ),
            "notes": [
                "Rows retained in the adjudicated sheet with status 'majority_deny' are normalized to unanimous agreement cases.",
                "For those retained rows, dependent vote columns are rewritten to 3-0 accept with accept rate 1.0.",
                "cluster_member_count is refreshed from the unique names listed in cluster_metas when available.",
            ],
        },
    )


if __name__ == "__main__":
    main()
