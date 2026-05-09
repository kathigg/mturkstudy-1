from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_SUBMISSIONS = (
    "src/mturk_results/2-20/cisc475database-default-rtdb-submissions-export.json"
)
DEFAULT_WORKBOOK = (
    "src/dataset_comparison_scripts/statistical_analysis/prerana_analysis/"
    "final_adjudicated_set - Final_adjudicated set.xlsx"
)
DEFAULT_OUTPUT_JSON = (
    "src/dataset_comparison_scripts/statistical_analysis/prerana_analysis/"
    "consolidated_paragraph_level_binary_irr_summary.json"
)
DEFAULT_OUTPUT_AUDIT = (
    "src/dataset_comparison_scripts/statistical_analysis/prerana_analysis/"
    "consolidated_paragraph_level_binary_irr_audit.csv"
)

ANNOTATOR_NAMES = ("Aarush", "Ashrey", "Prerana")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruct paragraph-level binary IRR on the 2-20 in-house subset "
            "after folding in the final adjudicated high-disagreement workbook."
        )
    )
    parser.add_argument("--submissions", default=DEFAULT_SUBMISSIONS)
    parser.add_argument("--workbook", default=DEFAULT_WORKBOOK)
    parser.add_argument("--sheet", default="Final_adjudicated set")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-audit", default=DEFAULT_OUTPUT_AUDIT)
    return parser.parse_args()


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def normalize_text(value: str | None) -> str:
    value = (value or "").strip().lower()
    value = value.replace("’", "'").replace("“", '"').replace("”", '"')
    value = re.sub(r"[^\w\s]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_name(value: str | None) -> str | None:
    text = normalize_text(value)
    if "aarush" in text:
        return "Aarush"
    if "ashrey" in text:
        return "Ashrey"
    if "prerana" in text:
        return "Prerana"
    return None


def feedback_texts(entry: dict) -> list[str]:
    survey = entry.get("surveyResponses")
    texts: list[str] = []
    if isinstance(survey, dict):
        for payload in survey.values():
            if isinstance(payload, dict):
                text = payload.get("openFeedback")
                if text:
                    texts.append(text)
    elif isinstance(survey, list):
        for payload in survey:
            if isinstance(payload, dict):
                text = payload.get("openFeedback")
                if text:
                    texts.append(text)
    return texts


def infer_name_from_entry(entry: dict) -> str | None:
    text = " ".join(feedback_texts(entry))
    direct = normalize_name(text)
    if direct:
        return direct

    # One raw row omits the name but still has a distinctive comment.
    if "overcredits the british" in normalize_text(text):
        return "Aarush"
    return None


def article_title_map_from_raw(raw_data: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in raw_data.values():
        for item in (entry.get("articleTitles") or []):
            if isinstance(item, dict) and item.get("id") is not None:
                mapping[str(item["id"])] = item.get("title", "")
    return mapping


def infer_worker_names(raw_data: dict) -> dict[str, str]:
    inferred = {worker_id: infer_name_from_entry(entry) for worker_id, entry in raw_data.items()}

    workers_by_article: dict[str, list[str]] = defaultdict(list)
    for worker_id, entry in raw_data.items():
        titles = entry.get("articleTitles") or []
        for item in titles:
            if isinstance(item, dict) and item.get("id") is not None:
                workers_by_article[str(item["id"])].append(worker_id)

    for worker_ids in workers_by_article.values():
        known = {name for worker_id in worker_ids if (name := inferred.get(worker_id))}
        unknown = [worker_id for worker_id in worker_ids if inferred.get(worker_id) is None]
        if len(unknown) == 1 and len(known) == 2:
            missing = sorted(set(ANNOTATOR_NAMES) - known)
            if len(missing) == 1:
                inferred[unknown[0]] = missing[0]

    unresolved = sorted(worker_id for worker_id, name in inferred.items() if name is None)
    if unresolved:
        raise ValueError(f"Could not infer annotator names for workers: {unresolved}")

    return {worker_id: name for worker_id, name in inferred.items() if name is not None}


def count_polarizing(labels: dict[str, str], *, polarizing_label: str) -> int:
    return sum(1 for value in labels.values() if value == polarizing_label)


def retained_vote_signature(rows: list[dict]) -> dict[str, bool]:
    return {
        "has_polarizing_3_0": any(
            row["vote_pattern"] == "3-0" and row["subcategory"] != "no polarizing language"
            for row in rows
        ),
        "has_polarizing_2_1": any(
            row["vote_pattern"] == "2-1" and row["subcategory"] != "no polarizing language"
            for row in rows
        ),
        "has_npl_3_0": any(
            row["vote_pattern"] == "3-0" and row["subcategory"] == "no polarizing language"
            for row in rows
        ),
        "has_npl_2_1": any(
            row["vote_pattern"] == "2-1" and row["subcategory"] == "no polarizing language"
            for row in rows
        ),
    }


def target_polarizing_count(signature: dict[str, bool]) -> int | None:
    # Paragraph-level binary rule:
    # if any retained polarizing span survives, the paragraph is treated as
    # polarizing for that many votes; NPL rows are only used when no retained
    # polarizing span survives in the paragraph.
    if signature["has_polarizing_3_0"]:
        return 3
    if signature["has_polarizing_2_1"]:
        return 2
    if signature["has_npl_3_0"]:
        return 0
    if signature["has_npl_2_1"]:
        return 1
    return None


def reconstruct_named_labels(
    current: dict[str, str],
    rows: list[dict],
    *,
    polarizing_label: str,
    npl_label: str,
    target_count: int,
) -> dict[str, str]:
    updated = dict(current)

    polarizing_names = {
        name
        for row in rows
        if row["subcategory"] != "no polarizing language"
        if (name := normalize_name(row["representative_meta"]))
    }
    npl_names = {
        name
        for row in rows
        if row["subcategory"] == "no polarizing language"
        if (name := normalize_name(row["representative_meta"]))
    }

    # Seed with any direct proposer signals from the adjudicated rows.
    for name in sorted(updated):
        if name in polarizing_names:
            updated[name] = polarizing_label
        elif name in npl_names and name not in polarizing_names:
            updated[name] = npl_label

    while count_polarizing(updated, polarizing_label=polarizing_label) < target_count:
        candidates = [name for name, label in updated.items() if label == npl_label]
        candidates.sort(
            key=lambda name: (
                name not in polarizing_names,
                name in npl_names,
                name,
            )
        )
        updated[candidates[0]] = polarizing_label

    while count_polarizing(updated, polarizing_label=polarizing_label) > target_count:
        candidates = [name for name, label in updated.items() if label == polarizing_label]
        candidates.sort(
            key=lambda name: (
                name not in npl_names,
                name in polarizing_names,
                name,
            )
        )
        updated[candidates[0]] = npl_label

    return updated


def summarize_units(base, deep, units: dict[tuple[str, int], dict[str, str]]) -> dict:
    unit_list = [labels for _, labels in sorted(units.items(), key=lambda item: (int(item[0][0]), item[0][1]))]
    ratings = [list(labels.values()) for labels in unit_list]
    distribution = Counter(count_polarizing(labels, polarizing_label=base.POLARIZING_LABEL) for labels in unit_list)
    return {
        "paragraph_units": len(unit_list),
        "polarizing_count_distribution": {str(key): value for key, value in sorted(distribution.items())},
        "pairwise_percent_agreement": round(base.pairwise_percent_agreement(ratings), 3),
        "exact_consensus_rate": round(deep.exact_consensus_rate(unit_list), 3),
        "fleiss_kappa": round(deep.fleiss_kappa(unit_list), 3),
        "krippendorff_alpha_nominal": round(base.krippendorff_alpha_nominal(ratings), 3),
        # This Cohen number depends on the synthetic identity-preserving assignment
        # inside the adjudicated paragraphs, so it is reported separately as such.
        "synthetic_weighted_mean_pairwise_cohen": round(
            deep.pairwise_cohen_weighted_mean(base, unit_list), 3
        ),
    }


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    stats_dir = script_dir.parent

    base = load_module(stats_dir / "in_house_density_and_agreement.py", "paragraph_base")
    deep = load_module(stats_dir / "deep_interannotator_reliability.py", "paragraph_deep")
    merge = load_module(script_dir / "merge_final_adjudicated_into_live_annotations.py", "merge_helper")

    submissions_path = Path(args.submissions)
    workbook_path = Path(args.workbook)

    raw_data = json.loads(submissions_path.read_text(encoding="utf-8"))
    worker_name_map = infer_worker_names(raw_data)
    article_titles = article_title_map_from_raw(raw_data)
    title_to_id = {normalize_text(title): article_id for article_id, title in article_titles.items()}

    _, _, annotations_by_worker_paragraph = base.load_raw_annotations(submissions_path)

    original_units: dict[tuple[str, int], dict[str, str]] = defaultdict(dict)
    for (worker_id, article_id, paragraph_index), annotations in annotations_by_worker_paragraph.items():
        label = base.derive_paragraph_binary_label(annotations)
        if label is None:
            continue
        original_units[(article_id, paragraph_index)][worker_name_map[worker_id]] = label

    bad_units = {
        key: labels
        for key, labels in original_units.items()
        if sorted(labels) != list(ANNOTATOR_NAMES)
    }
    if bad_units:
        raise ValueError(f"Unexpected annotator coverage in paragraph units: {list(bad_units)[:5]}")

    final_rows = merge.load_final_adjudicated_rows(workbook_path, sheet_name=args.sheet)
    rows_by_paragraph: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in final_rows:
        article_id = title_to_id.get(normalize_text(row["article_title"]))
        if article_id is None:
            raise ValueError(f"Could not map workbook article title: {row['article_title']!r}")
        rows_by_paragraph[(article_id, row["paragraph_index"])].append(row)

    reconstructed_units = {
        key: dict(labels)
        for key, labels in original_units.items()
    }

    audit_rows: list[dict] = []
    changed_units = 0
    signature_counter = Counter()

    for (article_id, paragraph_index), rows in sorted(rows_by_paragraph.items(), key=lambda item: (int(item[0][0]), item[0][1])):
        current = reconstructed_units[(article_id, paragraph_index)]
        signature = retained_vote_signature(rows)
        signature_key = json.dumps(signature, sort_keys=True)
        signature_counter[signature_key] += 1
        target = target_polarizing_count(signature)
        if target is None:
            continue

        updated = reconstruct_named_labels(
            current,
            rows,
            polarizing_label=base.POLARIZING_LABEL,
            npl_label=base.NPL_LABEL,
            target_count=target,
        )
        reconstructed_units[(article_id, paragraph_index)] = updated

        original_count = count_polarizing(current, polarizing_label=base.POLARIZING_LABEL)
        changed = current != updated
        changed_units += int(changed)

        audit_rows.append(
            {
                "article_id": article_id,
                "article_title": article_titles.get(article_id, ""),
                "paragraph_index": paragraph_index,
                "original_polarizing_count": original_count,
                "reconstructed_polarizing_count": target,
                "changed": changed,
                "signature": signature_key,
                "retained_rows": json.dumps(
                    [
                        {
                            "meta": row["representative_meta"],
                            "subcategory": row["subcategory"],
                            "vote_pattern": row["vote_pattern"],
                            "text": row["representative_text"],
                        }
                        for row in rows
                    ],
                    ensure_ascii=True,
                ),
                "original_labels": json.dumps(current, sort_keys=True),
                "reconstructed_labels": json.dumps(updated, sort_keys=True),
            }
        )

    summary = {
        "input_submissions": args.submissions,
        "input_workbook": args.workbook,
        "input_sheet": args.sheet,
        "paragraph_rule": (
            "Within an adjudicated paragraph, retained polarizing rows take priority over "
            "retained NPL rows because paragraph-level binary labeling is 'polarizing if any "
            "retained polarizing span survives'. The mapping is 3-0 polarizing -> 3/3 "
            "polarizing, else 2-1 polarizing -> 2/3 polarizing, else 3-0 NPL -> 0/3 "
            "polarizing, else 2-1 NPL -> 1/3 polarizing."
        ),
        "identity_note": (
            "Pairwise agreement, Fleiss' kappa, alpha, and exact consensus depend only on "
            "paragraph vote counts. The reported Cohen value is synthetic because paragraph "
            "vote-count changes do not uniquely identify which annotator flipped inside the "
            "adjudicated subset; this script preserves original names with minimal changes "
            "guided by proposer metadata."
        ),
        "coverage": {
            "total_original_paragraph_units": len(original_units),
            "adjudicated_rows": len(final_rows),
            "adjudicated_paragraph_units": len(rows_by_paragraph),
            "changed_paragraph_units": changed_units,
            "retained_row_signature_counts": {
                key: value for key, value in sorted(signature_counter.items())
            },
        },
        "original_binary_paragraph_irr": summarize_units(base, deep, original_units),
        "reconstructed_binary_paragraph_irr": summarize_units(base, deep, reconstructed_units),
    }

    write_json(Path(args.output_json), summary)
    write_csv(
        Path(args.output_audit),
        audit_rows,
        fieldnames=[
            "article_id",
            "article_title",
            "paragraph_index",
            "original_polarizing_count",
            "reconstructed_polarizing_count",
            "changed",
            "signature",
            "retained_rows",
            "original_labels",
            "reconstructed_labels",
        ],
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
