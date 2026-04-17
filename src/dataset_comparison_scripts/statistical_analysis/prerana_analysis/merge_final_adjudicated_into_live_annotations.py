from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_in_house_live_validation as live


DEFAULT_ANNOTATIONS = (
    "src/mturk_results/live/cisc475database-default-rtdb-InHouse-Annotations-export.json"
)
DEFAULT_SUBMISSIONS = (
    "src/mturk_results/live/cisc475database-default-rtdb-InHouse-Submissions-export.json"
)
DEFAULT_WORKBOOK = (
    "src/dataset_comparison_scripts/statistical_analysis/prerana_analysis/"
    "final_adjudicated_set - Final_adjudicated set.xlsx"
)
DEFAULT_OUTPUT_JSON = (
    "src/dataset_comparison_scripts/statistical_analysis/prerana_analysis/"
    "in_house_annotations_with_final_adjudicated_subset.json"
)
DEFAULT_OUTPUT_FLAT_CSV = (
    "src/dataset_comparison_scripts/statistical_analysis/prerana_analysis/"
    "in_house_annotations_with_final_adjudicated_subset.csv"
)
DEFAULT_OUTPUT_SUMMARY = (
    "src/dataset_comparison_scripts/statistical_analysis/prerana_analysis/"
    "in_house_annotations_with_final_adjudicated_subset_summary.json"
)
DEFAULT_OUTPUT_AUDIT = (
    "src/dataset_comparison_scripts/statistical_analysis/prerana_analysis/"
    "in_house_annotations_with_final_adjudicated_subset_replacements.csv"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Merge the final adjudicated high-disagreement subset into the full "
            "live InHouse-Annotations export and recompute binary accept/deny IRR."
        )
    )
    parser.add_argument("--annotations", default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--submissions", default=DEFAULT_SUBMISSIONS)
    parser.add_argument("--workbook", default=DEFAULT_WORKBOOK)
    parser.add_argument("--sheet", default="Final_adjudicated set")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-flat-csv", default=DEFAULT_OUTPUT_FLAT_CSV)
    parser.add_argument("--output-summary", default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-audit", default=DEFAULT_OUTPUT_AUDIT)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_loose(text: str | None) -> str:
    text = (text or "").lower().strip()
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"[^\w\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def xlsx_rows(path: Path, *, sheet_name: str) -> list[dict[str, str]]:
    ns = {
        "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }

    def col_to_index(col: str) -> int:
        value = 0
        for char in col:
            if char.isalpha():
                value = value * 26 + (ord(char.upper()) - 64)
        return value - 1

    with zipfile.ZipFile(path) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("x:si", ns):
                shared_strings.append(
                    "".join(node.text or "" for node in item.iterfind(".//x:t", ns))
                )

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        target = None
        for sheet in workbook.find("x:sheets", ns):
            if sheet.attrib.get("name") == sheet_name:
                target = "xl/" + rel_map[
                    sheet.attrib[
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                    ]
                ]
                break
        if target is None:
            raise ValueError(f"Sheet {sheet_name!r} not found in {path}")

        root = ET.fromstring(archive.read(target))
        matrix: list[list[str]] = []
        for row in root.findall(".//x:sheetData/x:row", ns):
            values = {}
            for cell in row.findall("x:c", ns):
                ref = cell.attrib.get("r", "")
                column = "".join(char for char in ref if char.isalpha())
                index = col_to_index(column)
                cell_type = cell.attrib.get("t")
                value_node = cell.find("x:v", ns)
                value = ""
                if cell_type == "s" and value_node is not None:
                    value = shared_strings[int(value_node.text)]
                elif cell_type == "inlineStr":
                    inline = cell.find("x:is", ns)
                    value = (
                        "".join(node.text or "" for node in inline.iterfind(".//x:t", ns))
                        if inline is not None
                        else ""
                    )
                elif value_node is not None:
                    value = value_node.text or ""
                values[index] = value
            if values:
                matrix.append([values.get(i, "") for i in range(max(values) + 1)])

    header = matrix[0]
    rows = [row + [""] * (len(header) - len(row)) for row in matrix[1:]]
    return [
        {header[i]: row[i] for i in range(len(header))}
        for row in rows
        if any(str(cell).strip() for cell in row)
    ]


def load_final_adjudicated_rows(path: Path, *, sheet_name: str) -> list[dict]:
    rows = []
    for row in xlsx_rows(path, sheet_name=sheet_name):
        if not str(row.get("cluster_status", "")).strip():
            continue
        rows.append(
            {
                "article_title": row["article_title"],
                "paragraph_index": int(float(row["paragraph_index"])),
                "subcategory": live.normalize_subcategory(row["subcategory"]),
                "representative_text": row["representative_text"],
                "representative_meta": row["representative_meta"],
                "accept": int(float(row["representative_accept"])),
                "deny": int(float(row["representative_deny"])),
                "vote_pattern": f"{int(float(row['representative_accept']))}-{int(float(row['representative_deny']))}",
            }
        )
    return rows


def reconstruct_clusters(raw_annotations, submissions):
    article_title_mapping = live.build_article_title_mapping(submissions)
    flattened = live.flatten_in_house_annotations(raw_annotations)
    paragraph_buckets = defaultdict(list)
    for annotation in flattened:
        paragraph_buckets[(annotation["article_index"], annotation["paragraph_index"])].append(
            annotation
        )

    clusters = []
    for (article_index, paragraph_index), paragraph_annotations in sorted(
        paragraph_buckets.items()
    ):
        for cluster_index, cluster in enumerate(live.cluster_annotations(paragraph_annotations)):
            representative = max(cluster, key=live.representative_rank)
            clusters.append(
                {
                    "article_index": article_index,
                    "article_title": article_title_mapping.get(
                        article_index, f"ARTICLE_{article_index}"
                    ),
                    "paragraph_index": paragraph_index,
                    "cluster_index": cluster_index,
                    "representative_text": representative["text"],
                    "representative_meta": representative["meta"],
                    "subcategory": representative["subcategory"],
                    "members": cluster,
                }
            )
    return clusters


def cluster_member_matches(final_row: dict, member: dict, *, require_subcategory: bool) -> bool:
    if normalize_loose(member["meta"]) != normalize_loose(final_row["representative_meta"]):
        return False
    if require_subcategory and normalize_loose(member["subcategory"]) != normalize_loose(
        final_row["subcategory"]
    ):
        return False

    member_text = normalize_loose(member["text"])
    final_text = normalize_loose(final_row["representative_text"])
    return (
        member_text == final_text
        or member_text in final_text
        or final_text in member_text
    )


def match_final_rows_to_clusters(final_rows: list[dict], clusters: list[dict]) -> list[tuple[dict, dict]]:
    matched = []
    missing = []
    ambiguous = []

    for final_row in final_rows:
        candidates = []
        for cluster in clusters:
            if normalize_loose(cluster["article_title"]) != normalize_loose(
                final_row["article_title"]
            ):
                continue
            if cluster["paragraph_index"] != final_row["paragraph_index"]:
                continue
            if any(
                cluster_member_matches(final_row, member, require_subcategory=True)
                for member in cluster["members"]
            ):
                candidates.append(cluster)

        if not candidates:
            for cluster in clusters:
                if normalize_loose(cluster["article_title"]) != normalize_loose(
                    final_row["article_title"]
                ):
                    continue
                if cluster["paragraph_index"] != final_row["paragraph_index"]:
                    continue
                if any(
                    cluster_member_matches(final_row, member, require_subcategory=False)
                    for member in cluster["members"]
                ):
                    candidates.append(cluster)

        if len(candidates) == 1:
            matched.append((final_row, candidates[0]))
        elif len(candidates) == 0:
            missing.append(final_row)
        else:
            ambiguous.append(
                {
                    "final_row": final_row,
                    "candidate_clusters": [
                        {
                            "article_index": cluster["article_index"],
                            "cluster_index": cluster["cluster_index"],
                        }
                        for cluster in candidates
                    ],
                }
            )

    if missing or ambiguous:
        raise ValueError(
            f"Could not map all adjudicated rows cleanly: missing={len(missing)}, "
            f"ambiguous={len(ambiguous)}"
        )
    return matched


def raw_lookup(raw_annotations):
    lookup = {}
    for article_index, article in enumerate(raw_annotations):
        if not isinstance(article, list):
            continue
        for paragraph_index, paragraph in enumerate(article):
            if not isinstance(paragraph, list):
                continue
            for annotation_index, annotation in enumerate(paragraph):
                if not isinstance(annotation, dict):
                    continue
                key = (
                    article_index,
                    paragraph_index,
                    annotation.get("meta", ""),
                    live.normalize_subcategory(annotation.get("subcategory")),
                    annotation.get("span", ""),
                )
                lookup[key] = (article_index, paragraph_index, annotation_index)
    return lookup


def binary_metrics(raw_annotations, *, mode: str) -> dict:
    ratings = []
    vote_patterns = Counter()
    accept_total = 0
    deny_total = 0

    for article in raw_annotations:
        if not isinstance(article, list):
            continue
        for paragraph in article:
            if not isinstance(paragraph, list):
                continue
            for annotation in paragraph:
                if not isinstance(annotation, dict):
                    continue
                accept = int(annotation.get("accept", 0) or 0)
                deny = int(annotation.get("deny", 0) or 0)
                total = accept + deny
                if mode == "eligible_ge_2" and total < 2:
                    continue
                if mode == "exactly_3" and total != 3:
                    continue
                ratings.append(["accept"] * accept + ["deny"] * deny)
                vote_patterns[f"{accept}-{deny}"] += 1
                accept_total += accept
                deny_total += deny

    if not ratings:
        return {
            "eligible_rows": 0,
            "vote_pattern_counts": {},
            "accept_total": 0,
            "deny_total": 0,
            "accept_rate": None,
            "pairwise_percent_agreement": None,
            "krippendorff_alpha_nominal": None,
            "exact_consensus_count": 0,
            "exact_consensus_rate": None,
        }

    total_pairs = 0
    agree_pairs = 0
    for row in ratings:
        counts = Counter(row)
        n = sum(counts.values())
        total_pairs += n * (n - 1) // 2
        agree_pairs += sum(count * (count - 1) // 2 for count in counts.values())
    pairwise = agree_pairs / total_pairs if total_pairs else None

    labels = sorted({label for row in ratings for label in row})
    label_index = {label: idx for idx, label in enumerate(labels)}
    coincidence = [[0] * len(labels) for _ in labels]
    for row in ratings:
        counts = Counter(row)
        for label, count in counts.items():
            idx = label_index[label]
            coincidence[idx][idx] += count * (count - 1)
        present = list(counts)
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                left, right = present[i], present[j]
                left_count = counts[left]
                right_count = counts[right]
                li = label_index[left]
                ri = label_index[right]
                coincidence[li][ri] += left_count * right_count
                coincidence[ri][li] += left_count * right_count

    total = sum(sum(row) for row in coincidence)
    observed_disagreement = (
        sum(
            coincidence[i][j]
            for i in range(len(labels))
            for j in range(len(labels))
            if i != j
        )
        / total
    )
    marginal = [sum(row) for row in coincidence]
    expected_disagreement = (
        (total * total - sum(value * value for value in marginal)) / (total * (total - 1))
    )
    alpha = 1 - (observed_disagreement / expected_disagreement)

    exact_consensus_count = sum(1 for row in ratings if len(set(row)) == 1)
    return {
        "eligible_rows": len(ratings),
        "vote_pattern_counts": dict(vote_patterns),
        "accept_total": accept_total,
        "deny_total": deny_total,
        "accept_rate": accept_total / (accept_total + deny_total),
        "pairwise_percent_agreement": pairwise,
        "krippendorff_alpha_nominal": alpha,
        "exact_consensus_count": exact_consensus_count,
        "exact_consensus_rate": exact_consensus_count / len(ratings),
    }


def flatten_for_csv(raw_annotations, submissions) -> list[dict]:
    article_titles = live.build_article_title_mapping(submissions)
    rows = []
    for article_index, article in enumerate(raw_annotations):
        if not isinstance(article, list):
            continue
        for paragraph_index, paragraph in enumerate(article):
            if not isinstance(paragraph, list):
                continue
            for annotation in paragraph:
                if not isinstance(annotation, dict):
                    continue
                accept = int(annotation.get("accept", 0) or 0)
                deny = int(annotation.get("deny", 0) or 0)
                total_votes = accept + deny
                rows.append(
                    {
                        "article_index": article_index,
                        "article_title": article_titles.get(article_index, f"ARTICLE_{article_index}"),
                        "paragraph_index": paragraph_index,
                        "meta": annotation.get("meta", ""),
                        "subcategory": live.normalize_subcategory(annotation.get("subcategory")),
                        "span": annotation.get("span", ""),
                        "accept": accept,
                        "deny": deny,
                        "total_votes": total_votes,
                        "accept_rate": round(accept / total_votes, 6) if total_votes else None,
                    }
                )
    return rows


def round_metrics(metrics: dict) -> dict:
    rounded = dict(metrics)
    for key in (
        "accept_rate",
        "pairwise_percent_agreement",
        "krippendorff_alpha_nominal",
        "exact_consensus_rate",
    ):
        if rounded[key] is not None:
            rounded[key] = round(rounded[key], 3)
    return rounded


def delta_metrics(before: dict, after: dict) -> dict:
    delta = {}
    for key in (
        "eligible_rows",
        "accept_total",
        "deny_total",
        "accept_rate",
        "pairwise_percent_agreement",
        "krippendorff_alpha_nominal",
        "exact_consensus_count",
        "exact_consensus_rate",
    ):
        left = before[key]
        right = after[key]
        delta[key] = None if left is None or right is None else round(right - left, 3)
    return delta


def main():
    args = parse_args()
    annotations_path = Path(args.annotations)
    submissions_path = Path(args.submissions)
    workbook_path = Path(args.workbook)

    raw_annotations = load_json(annotations_path)
    submissions = load_json(submissions_path)
    final_rows = load_final_adjudicated_rows(workbook_path, sheet_name=args.sheet)
    clusters = reconstruct_clusters(raw_annotations, submissions)
    matched = match_final_rows_to_clusters(final_rows, clusters)

    merged = deepcopy(raw_annotations)
    lookup = raw_lookup(merged)
    audit_rows = []
    replaced_raw_rows = 0

    for final_row, cluster in matched:
        for member in cluster["members"]:
            key = (
                member["article_index"],
                member["paragraph_index"],
                member["meta"],
                member["subcategory"],
                member["text"],
            )
            article_index, paragraph_index, annotation_index = lookup[key]
            original = merged[article_index][paragraph_index][annotation_index]
            audit_rows.append(
                {
                    "article_index": article_index,
                    "article_title": cluster["article_title"],
                    "paragraph_index": paragraph_index,
                    "cluster_index": cluster["cluster_index"],
                    "raw_meta": member["meta"],
                    "raw_subcategory": member["subcategory"],
                    "raw_span": member["text"],
                    "old_accept": int(original.get("accept", 0) or 0),
                    "old_deny": int(original.get("deny", 0) or 0),
                    "new_accept": final_row["accept"],
                    "new_deny": final_row["deny"],
                    "adjudicated_vote_pattern": final_row["vote_pattern"],
                    "adjudicated_row_meta": final_row["representative_meta"],
                    "adjudicated_row_text": final_row["representative_text"],
                }
            )
            original["accept"] = final_row["accept"]
            original["deny"] = final_row["deny"]
            replaced_raw_rows += 1

    baseline_ge_2 = binary_metrics(raw_annotations, mode="eligible_ge_2")
    baseline_exact_3 = binary_metrics(raw_annotations, mode="exactly_3")
    merged_ge_2 = binary_metrics(merged, mode="eligible_ge_2")
    merged_exact_3 = binary_metrics(merged, mode="exactly_3")

    summary = {
        "input_annotations": str(annotations_path),
        "input_submissions": str(submissions_path),
        "input_workbook": str(workbook_path),
        "input_sheet": args.sheet,
        "merge_rule": (
            "For each final adjudicated cluster, replace accept/deny counts on every "
            "raw proposal member inside that reconstructed cluster."
        ),
        "replacement_counts": {
            "matched_adjudicated_clusters": len(matched),
            "replaced_raw_proposals": replaced_raw_rows,
            "cluster_member_count_distribution": dict(
                Counter(len(cluster["members"]) for _, cluster in matched)
            ),
        },
        "baseline_binary_accept_deny": {
            "eligible_ge_2_votes": round_metrics(baseline_ge_2),
            "exactly_3_votes": round_metrics(baseline_exact_3),
        },
        "merged_binary_accept_deny": {
            "eligible_ge_2_votes": round_metrics(merged_ge_2),
            "exactly_3_votes": round_metrics(merged_exact_3),
        },
        "delta": {
            "eligible_ge_2_votes": delta_metrics(baseline_ge_2, merged_ge_2),
            "exactly_3_votes": delta_metrics(baseline_exact_3, merged_exact_3),
        },
    }

    output_json = Path(args.output_json)
    output_flat_csv = Path(args.output_flat_csv)
    output_summary = Path(args.output_summary)
    output_audit = Path(args.output_audit)
    write_json(output_json, merged)
    write_csv(
        output_flat_csv,
        flatten_for_csv(merged, submissions),
        [
            "article_index",
            "article_title",
            "paragraph_index",
            "meta",
            "subcategory",
            "span",
            "accept",
            "deny",
            "total_votes",
            "accept_rate",
        ],
    )
    write_json(output_summary, summary)
    write_csv(
        output_audit,
        audit_rows,
        [
            "article_index",
            "article_title",
            "paragraph_index",
            "cluster_index",
            "raw_meta",
            "raw_subcategory",
            "raw_span",
            "old_accept",
            "old_deny",
            "new_accept",
            "new_deny",
            "adjudicated_vote_pattern",
            "adjudicated_row_meta",
            "adjudicated_row_text",
        ],
    )

    print(f"Wrote merged annotations JSON to {output_json}")
    print(f"Wrote merged annotations flat CSV to {output_flat_csv}")
    print(f"Wrote merged summary JSON to {output_summary}")
    print(f"Wrote replacement audit CSV to {output_audit}")


if __name__ == "__main__":
    main()
