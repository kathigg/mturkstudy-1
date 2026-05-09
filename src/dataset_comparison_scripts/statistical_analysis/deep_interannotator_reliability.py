from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean


DEFAULT_INPUT = "src/mturk_results/2-20/2-20_polarizing_annotation.json"
DEFAULT_OUTPUT_JSON = (
    "src/dataset_comparison_scripts/statistical_analysis/2-20/"
    "2-20_human_interannotator_reliability_deep.json"
)
DEFAULT_OUTPUT_MD = (
    "src/dataset_comparison_scripts/statistical_analysis/2-20/"
    "2-20_human_interannotator_reliability_deep.md"
)
DEFAULT_OUTPUT_CSV = (
    "src/dataset_comparison_scripts/statistical_analysis/2-20/"
    "2-20_article_level_binary_reliability.csv"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Deep interannotator reliability audit for paragraph-level human annotations."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--bootstrap-iters", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=13)
    return parser.parse_args()


def load_base_module():
    helper_path = Path(__file__).resolve().parent / "in_house_density_and_agreement.py"
    spec = importlib.util.spec_from_file_location("iaa_base", helper_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def normalize_article_titles(raw_data) -> dict[str, str]:
    titles = {}
    for entry in raw_data.values():
        article_titles = entry.get("articleTitles") or []
        if isinstance(article_titles, list):
            for item in article_titles:
                if isinstance(item, dict) and item.get("id") is not None:
                    titles[str(item["id"])] = item.get("title", "")
        elif isinstance(article_titles, dict):
            for article_id, title in article_titles.items():
                titles[str(article_id)] = title
    return titles


def units_to_list(units: dict[tuple[str, int], dict[str, str]]) -> list[dict[str, str]]:
    return [worker_labels for _, worker_labels in sorted(units.items())]


def build_units_from_list(unit_list: list[dict[str, str]]) -> dict[tuple[str, int], dict[str, str]]:
    return {("bootstrap", index): labels for index, labels in enumerate(unit_list)}


def label_counts_from_unit_list(unit_list: list[dict[str, str]]) -> dict[str, int]:
    return dict(Counter(label for worker_labels in unit_list for label in worker_labels.values()))


def exact_consensus_rate(unit_list: list[dict[str, str]]) -> float | None:
    if not unit_list:
        return None
    consensus = sum(1 for worker_labels in unit_list if len(set(worker_labels.values())) == 1)
    return consensus / len(unit_list)


def fleiss_kappa(unit_list: list[dict[str, str]]) -> float | None:
    if not unit_list:
        return None

    rater_counts = {len(worker_labels) for worker_labels in unit_list}
    if len(rater_counts) != 1:
        return None
    n_raters = next(iter(rater_counts))
    if n_raters < 2:
        return None

    labels = sorted({label for worker_labels in unit_list for label in worker_labels.values()})
    if len(labels) < 2:
        return None

    p_i_values = []
    label_totals = Counter()
    total_assignments = len(unit_list) * n_raters

    for worker_labels in unit_list:
        counts = Counter(worker_labels.values())
        label_totals.update(counts)
        p_i = sum(count * (count - 1) for count in counts.values()) / (n_raters * (n_raters - 1))
        p_i_values.append(p_i)

    p_bar = sum(p_i_values) / len(p_i_values)
    p_e = sum((label_totals[label] / total_assignments) ** 2 for label in labels)
    if p_e == 1.0:
        return 1.0
    return (p_bar - p_e) / (1 - p_e)


def pairwise_cohen_weighted_mean(base, unit_list: list[dict[str, str]]) -> float | None:
    return base.pairwise_cohen_kappa(build_units_from_list(unit_list))["weighted_mean_kappa"]


def bootstrap_ci(unit_list, metric_fn, *, iterations: int, seed: int):
    if not unit_list:
        return {"lower": None, "upper": None, "samples": 0}

    rng = random.Random(seed)
    n_units = len(unit_list)
    values = []
    for _ in range(iterations):
        sample = [unit_list[rng.randrange(n_units)] for _ in range(n_units)]
        value = metric_fn(sample)
        if value is not None:
            values.append(value)

    if not values:
        return {"lower": None, "upper": None, "samples": 0}

    values.sort()
    lower_index = max(0, int(0.025 * len(values)) - 1)
    upper_index = min(len(values) - 1, int(0.975 * len(values)))
    return {
        "lower": round(values[lower_index], 3),
        "upper": round(values[upper_index], 3),
        "samples": len(values),
    }


def metric_bundle(base, units, *, iterations: int, seed: int):
    unit_list = units_to_list(units)
    ratings = [list(worker_labels.values()) for worker_labels in unit_list if len(worker_labels) >= 2]

    pairwise_percent = base.pairwise_percent_agreement(ratings)
    cohen_weighted = pairwise_cohen_weighted_mean(base, unit_list)
    fleiss = fleiss_kappa(unit_list)
    kripp = base.krippendorff_alpha_nominal(ratings)
    exact_consensus = exact_consensus_rate(unit_list)

    bundle = {
        "units": len(unit_list),
        "raters_per_unit_distribution": dict(Counter(len(worker_labels) for worker_labels in unit_list)),
        "label_counts": label_counts_from_unit_list(unit_list),
        "pairwise_percent_agreement": round(pairwise_percent, 3) if pairwise_percent is not None else None,
        "exact_consensus_rate": round(exact_consensus, 3) if exact_consensus is not None else None,
        "pairwise_cohen_weighted_mean": round(cohen_weighted, 3) if cohen_weighted is not None else None,
        "fleiss_kappa": round(fleiss, 3) if fleiss is not None else None,
        "krippendorff_alpha_nominal": round(kripp, 3) if kripp is not None else None,
        "bootstrap_95ci": {
            "pairwise_percent_agreement": bootstrap_ci(
                unit_list,
                lambda sampled: base.pairwise_percent_agreement(
                    [list(worker_labels.values()) for worker_labels in sampled]
                ),
                iterations=iterations,
                seed=seed + 1,
            ),
            "exact_consensus_rate": bootstrap_ci(
                unit_list,
                exact_consensus_rate,
                iterations=iterations,
                seed=seed + 2,
            ),
            "pairwise_cohen_weighted_mean": bootstrap_ci(
                unit_list,
                lambda sampled: pairwise_cohen_weighted_mean(base, sampled),
                iterations=iterations,
                seed=seed + 3,
            ),
            "fleiss_kappa": bootstrap_ci(
                unit_list,
                fleiss_kappa,
                iterations=iterations,
                seed=seed + 4,
            ),
            "krippendorff_alpha_nominal": bootstrap_ci(
                unit_list,
                lambda sampled: base.krippendorff_alpha_nominal(
                    [list(worker_labels.values()) for worker_labels in sampled]
                ),
                iterations=iterations,
                seed=seed + 5,
            ),
        },
    }
    return bundle


def greedy_match_pairs(base, annotations_a, annotations_b, *, include_npl: bool):
    used_b = set()
    matched = []
    sorted_b = base.sorted_annotations(annotations_b)

    for ann_a in base.sorted_annotations(annotations_a):
        for idx_b, ann_b in enumerate(sorted_b):
            if idx_b in used_b:
                continue
            if base.spans_match(ann_a, ann_b, include_npl=include_npl):
                used_b.add(idx_b)
                matched.append((ann_a, ann_b))
                break
    return matched


def matched_span_label_agreement(base, worker_annotations_by_article, *, include_npl: bool):
    pair_summaries = []
    total_matches = 0
    total_category_agree = 0
    total_subcategory_agree = 0

    for article_id, by_worker in sorted(worker_annotations_by_article.items()):
        worker_ids = sorted(by_worker)
        for worker_a_index in range(len(worker_ids)):
            for worker_b_index in range(worker_a_index + 1, len(worker_ids)):
                worker_a = worker_ids[worker_a_index]
                worker_b = worker_ids[worker_b_index]
                matched = greedy_match_pairs(
                    base,
                    by_worker[worker_a],
                    by_worker[worker_b],
                    include_npl=include_npl,
                )
                if not matched:
                    continue
                category_agree = sum(1 for left, right in matched if left["category"] == right["category"])
                subcategory_agree = sum(
                    1 for left, right in matched if left["subcategory"] == right["subcategory"]
                )
                total_matches += len(matched)
                total_category_agree += category_agree
                total_subcategory_agree += subcategory_agree
                pair_summaries.append(
                    {
                        "article_id": article_id,
                        "worker_a": worker_a,
                        "worker_b": worker_b,
                        "matched_spans": len(matched),
                        "category_agreement_rate": round(category_agree / len(matched), 3),
                        "subcategory_agreement_rate": round(subcategory_agree / len(matched), 3),
                    }
                )

    if not pair_summaries:
        return {
            "pair_count": 0,
            "matched_spans_total": 0,
            "micro_category_agreement_rate": None,
            "micro_subcategory_agreement_rate": None,
            "macro_category_agreement_rate": None,
            "macro_subcategory_agreement_rate": None,
            "pair_examples": [],
        }

    macro_category = mean(item["category_agreement_rate"] for item in pair_summaries)
    macro_subcategory = mean(item["subcategory_agreement_rate"] for item in pair_summaries)
    return {
        "pair_count": len(pair_summaries),
        "matched_spans_total": total_matches,
        "micro_category_agreement_rate": round(total_category_agree / total_matches, 3) if total_matches else None,
        "micro_subcategory_agreement_rate": round(total_subcategory_agree / total_matches, 3) if total_matches else None,
        "macro_category_agreement_rate": round(macro_category, 3),
        "macro_subcategory_agreement_rate": round(macro_subcategory, 3),
        "pair_examples": pair_summaries[:10],
    }


def article_level_metrics(base, units, article_titles):
    by_article = defaultdict(dict)
    for (article_id, paragraph_index), worker_labels in units.items():
        by_article[str(article_id)][(str(article_id), paragraph_index)] = worker_labels

    rows = []
    for article_id, article_units in sorted(by_article.items(), key=lambda item: int(item[0])):
        unit_list = units_to_list(article_units)
        ratings = [list(worker_labels.values()) for worker_labels in unit_list]
        pairwise_percent = base.pairwise_percent_agreement(ratings)
        rows.append(
            {
                "article_id": article_id,
                "title": article_titles.get(article_id, ""),
                "paragraph_units": len(unit_list),
                "pairwise_percent_agreement": round(pairwise_percent, 3) if pairwise_percent is not None else None,
                "exact_consensus_rate": round(exact_consensus_rate(unit_list) or 0.0, 3),
                "fleiss_kappa": round(fleiss_kappa(unit_list) or 0.0, 3),
                "krippendorff_alpha_nominal": round(base.krippendorff_alpha_nominal(ratings) or 0.0, 3),
            }
        )
    return rows


def augment_one_vs_rest(base, annotations_by_worker_paragraph, *, label_mode: str, labels):
    units_by_label = base.build_one_vs_rest_units(
        annotations_by_worker_paragraph,
        label_mode=label_mode,
        labels=labels,
    )
    result = {}
    total_units = len(annotations_by_worker_paragraph)

    for label, units in units_by_label.items():
        unit_list = units_to_list(units)
        ratings = [list(worker_labels.values()) for worker_labels in unit_list]
        positive_ratings = sum(
            1 for worker_labels in units.values() for value in worker_labels.values() if value == "present"
        )
        result[label] = {
            "positive_ratings": positive_ratings,
            "positive_share_of_worker_paragraph_units": round(
                positive_ratings / total_units, 4
            )
            if total_units
            else 0.0,
            "pairwise_percent_agreement": round(base.pairwise_percent_agreement(ratings) or 0.0, 3),
            "exact_consensus_rate": round(exact_consensus_rate(unit_list) or 0.0, 3),
            "pairwise_cohen_weighted_mean": round(
                pairwise_cohen_weighted_mean(base, unit_list) or 0.0, 3
            ),
            "fleiss_kappa": round(fleiss_kappa(unit_list) or 0.0, 3),
            "krippendorff_alpha_nominal": round(base.krippendorff_alpha_nominal(ratings) or 0.0, 3),
        }
    return result


def round_nested(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {key: round_nested(subvalue) for key, subvalue in value.items()}
    if isinstance(value, list):
        return [round_nested(item) for item in value]
    return value


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def format_ci(ci):
    if not ci or ci["lower"] is None or ci["upper"] is None:
        return "n/a"
    return f"[{ci['lower']:.3f}, {ci['upper']:.3f}]"


def write_markdown_report(path: Path, payload):
    overall = payload["paragraph_level_agreement"]
    binary_articles = payload["article_level_binary"]
    worst_binary = sorted(binary_articles, key=lambda row: (row["fleiss_kappa"], row["krippendorff_alpha_nominal"]))[:5]
    best_binary = sorted(binary_articles, key=lambda row: (row["fleiss_kappa"], row["krippendorff_alpha_nominal"]), reverse=True)[:5]

    lines = []
    lines.append("# 2-20 Deep Interannotator Reliability Audit")
    lines.append("")
    lines.append("## Design Choices")
    lines.append("")
    lines.append("- Fixed unit of analysis: paragraph within article.")
    lines.append("- All paragraph units in the raw `2-20` file have exactly 3 raters, so Fleiss' kappa is valid on the full paragraph-level dataset.")
    lines.append("- Category and subcategory analyses use majority label per paragraph; ties are resolved by first label encountered in that paragraph. One-vs-rest results are included to check label-specific behavior.")
    lines.append("- Span overlap is reported separately from paragraph-level chance-corrected reliability because span selection and label assignment are different reliability problems.")
    lines.append("")
    lines.append("## Dataset Summary")
    lines.append("")
    summary = payload["dataset_summary"]
    lines.append(f"- Workers: `{summary['workers']}`")
    lines.append(f"- Articles: `{summary['articles']}`")
    lines.append(f"- Paragraph units: `{summary['paragraph_units']}`")
    lines.append(f"- Raters per paragraph unit: `{summary['raters_per_unit']}`")
    lines.append(f"- Raw annotations: `{summary['raw_annotations']}`")
    lines.append("")
    lines.append("## Paragraph-Level Agreement")
    lines.append("")
    for mode_key, label in [
        ("binary", "Binary"),
        ("category", "Category"),
        ("subcategory", "Subcategory"),
    ]:
        metrics = overall[mode_key]
        lines.append(f"### {label}")
        lines.append("")
        lines.append(f"- Pairwise percent agreement: `{metrics['pairwise_percent_agreement']}` with 95% bootstrap CI `{format_ci(metrics['bootstrap_95ci']['pairwise_percent_agreement'])}`")
        lines.append(f"- Exact 3-rater consensus rate: `{metrics['exact_consensus_rate']}` with 95% bootstrap CI `{format_ci(metrics['bootstrap_95ci']['exact_consensus_rate'])}`")
        lines.append(f"- Weighted mean pairwise Cohen's kappa: `{metrics['pairwise_cohen_weighted_mean']}` with 95% bootstrap CI `{format_ci(metrics['bootstrap_95ci']['pairwise_cohen_weighted_mean'])}`")
        lines.append(f"- Fleiss' kappa: `{metrics['fleiss_kappa']}` with 95% bootstrap CI `{format_ci(metrics['bootstrap_95ci']['fleiss_kappa'])}`")
        lines.append(f"- Krippendorff's alpha (nominal): `{metrics['krippendorff_alpha_nominal']}` with 95% bootstrap CI `{format_ci(metrics['bootstrap_95ci']['krippendorff_alpha_nominal'])}`")
        lines.append(f"- Label counts: `{metrics['label_counts']}`")
        lines.append("")
    lines.append("## Span-Level Reliability")
    lines.append("")
    span_overlap = payload["span_overlap"]
    matched = payload["matched_span_label_agreement"]
    lines.append(f"- Dice/F1 including `no polarizing language`: macro `{span_overlap['including_npl']['macro_dice_f1']}`, micro `{span_overlap['including_npl']['micro_dice_f1']}`")
    lines.append(f"- Dice/F1 polarizing-only: macro `{span_overlap['polarizing_only']['macro_dice_f1']}`, micro `{span_overlap['polarizing_only']['micro_dice_f1']}`")
    lines.append(f"- Among matched polarizing spans, category agreement: micro `{matched['polarizing_only']['micro_category_agreement_rate']}`, subcategory agreement: micro `{matched['polarizing_only']['micro_subcategory_agreement_rate']}`")
    lines.append("")
    lines.append("## Article-Level Binary Reliability")
    lines.append("")
    lines.append("### Lowest Fleiss' Kappa")
    lines.append("")
    for row in worst_binary:
        lines.append(
            f"- `{row['article_id']}` {row['title']}: Fleiss `{row['fleiss_kappa']}`, alpha `{row['krippendorff_alpha_nominal']}`, agreement `{row['pairwise_percent_agreement']}`, paragraphs `{row['paragraph_units']}`"
        )
    lines.append("")
    lines.append("### Highest Fleiss' Kappa")
    lines.append("")
    for row in best_binary:
        lines.append(
            f"- `{row['article_id']}` {row['title']}: Fleiss `{row['fleiss_kappa']}`, alpha `{row['krippendorff_alpha_nominal']}`, agreement `{row['pairwise_percent_agreement']}`, paragraphs `{row['paragraph_units']}`"
        )
    lines.append("")
    lines.append("## Interpretation Notes")
    lines.append("")
    lines.append("- If percent agreement is moderate but kappa/alpha stay near zero or below, that usually means prevalence and label imbalance are dominating the chance-corrected metrics.")
    lines.append("- If span overlap is low but matched-span subcategory agreement is higher, the main disagreement is span selection rather than taxonomy understanding.")
    lines.append("- Rare one-vs-rest labels can show high agreement but unstable alpha because nearly everyone marks them absent.")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    base = load_base_module()

    input_path = Path(args.input)
    raw_data, worker_annotations_by_article, annotations_by_worker_paragraph = base.load_raw_annotations(input_path)
    article_titles = normalize_article_titles(raw_data)

    units_binary = base.build_unit_labels(annotations_by_worker_paragraph, label_mode="binary")
    units_category = base.build_unit_labels(annotations_by_worker_paragraph, label_mode="category")
    units_subcategory = base.build_unit_labels(annotations_by_worker_paragraph, label_mode="subcategory")

    payload = {
        "input_path": str(input_path),
        "dataset_summary": {
            "workers": len(raw_data),
            "articles": len(article_titles),
            "paragraph_units": len(units_binary),
            "raters_per_unit": 3,
            "raw_annotations": sum(len(annotations) for annotations in annotations_by_worker_paragraph.values()),
        },
        "paragraph_level_agreement": {
            "binary": metric_bundle(base, units_binary, iterations=args.bootstrap_iters, seed=args.seed + 10),
            "category": metric_bundle(base, units_category, iterations=args.bootstrap_iters, seed=args.seed + 20),
            "subcategory": metric_bundle(base, units_subcategory, iterations=args.bootstrap_iters, seed=args.seed + 30),
        },
        "span_overlap": {
            "including_npl": base.pairwise_span_overlap(worker_annotations_by_article, include_npl=True),
            "polarizing_only": base.pairwise_span_overlap(worker_annotations_by_article, include_npl=False),
        },
        "matched_span_label_agreement": {
            "including_npl": matched_span_label_agreement(
                base, worker_annotations_by_article, include_npl=True
            ),
            "polarizing_only": matched_span_label_agreement(
                base, worker_annotations_by_article, include_npl=False
            ),
        },
        "one_vs_rest": {
            "category": augment_one_vs_rest(
                base,
                annotations_by_worker_paragraph,
                label_mode="category",
                labels=[base.NPL_LABEL, "persuasive propaganda", "inflammatory language"],
            ),
            "subcategory": augment_one_vs_rest(
                base,
                annotations_by_worker_paragraph,
                label_mode="subcategory",
                labels=[
                    base.NPL_LABEL,
                    "exaggeration",
                    "doubt",
                    "slogans",
                    "casual oversimplification",
                    "scapegoating",
                    "bandwagon",
                    "demonization",
                    "name-calling",
                ],
            ),
        },
        "article_level_binary": article_level_metrics(base, units_binary, article_titles),
        "article_level_category": article_level_metrics(base, units_category, article_titles),
        "article_level_subcategory": article_level_metrics(base, units_subcategory, article_titles),
    }

    payload = round_nested(payload)

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_csv = Path(args.output_csv)

    write_json(output_json, payload)
    write_markdown_report(output_md, payload)
    write_csv(output_csv, payload["article_level_binary"])

    print(f"Wrote deep reliability JSON to {output_json}")
    print(f"Wrote deep reliability report to {output_md}")
    print(f"Wrote article-level binary CSV to {output_csv}")


if __name__ == "__main__":
    main()
