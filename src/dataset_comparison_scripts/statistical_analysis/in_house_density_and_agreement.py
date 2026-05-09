from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Iterable


NPL_LABEL = "no polarizing language"
POLARIZING_LABEL = "polarizing language"
MULTI_CATEGORY_LABEL = "multiple polarizing categories"
MULTI_SUBCATEGORY_LABEL = "multiple polarizing subcategories"

STOP_WORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
    "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she",
    "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
    "theirs", "themselves", "what", "which", "who", "whom", "this", "that",
    "these", "those", "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an",
    "the", "and", "but", "if", "or", "because", "as", "until", "while", "of",
    "at", "by", "for", "with", "about", "against", "between", "into", "through",
    "during", "before", "after", "above", "below", "to", "from", "up", "down",
    "in", "out", "on", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "can",
    "will", "just", "don", "should", "now",
}


def normalize_label(label: str | None) -> str:
    if not label:
        return ""
    return re.sub(r"[_]", " ", label).strip().lower()


def normalize_span(text: str | None) -> str:
    text = re.sub(r"[^\w\s]", " ", text or "").lower()
    return re.sub(r"\s+", " ", text).strip()


def tokenize_span(text: str | None) -> list[str]:
    return normalize_span(text).split()


def longest_common_token_run(span1: str | None, span2: str | None) -> int:
    tokens1 = tokenize_span(span1)
    tokens2 = tokenize_span(span2)
    if not tokens1 or not tokens2:
        return 0

    best = 0
    prev = [0] * (len(tokens2) + 1)
    for token1 in tokens1:
        curr = [0] * (len(tokens2) + 1)
        for j, token2 in enumerate(tokens2, start=1):
            if token1 == token2:
                curr[j] = prev[j - 1] + 1
                if curr[j] > best:
                    best = curr[j]
        prev = curr
    return best


def is_no_polarizing_annotation(ann: dict) -> bool:
    return (
        normalize_label(ann.get("category")) == NPL_LABEL
        or normalize_label(ann.get("subcategory")) == NPL_LABEL
    )


def canonical_category(ann: dict) -> str:
    label = normalize_label(ann.get("category"))
    if label == NPL_LABEL:
        return NPL_LABEL
    return label


def canonical_subcategory(ann: dict) -> str:
    label = normalize_label(ann.get("subcategory"))
    if label == "no polarizing":
        return NPL_LABEL
    return label


def non_stopword_overlap(span1: str | None, span2: str | None) -> bool:
    tokens1 = set(tokenize_span(span1)) - STOP_WORDS
    tokens2 = set(tokenize_span(span2)) - STOP_WORDS
    return len(tokens1 & tokens2) >= 2


def spans_match(a: dict, b: dict, *, include_npl: bool) -> bool:
    if a.get("paragraphIndex") != b.get("paragraphIndex"):
        return False

    a_npl = is_no_polarizing_annotation(a)
    b_npl = is_no_polarizing_annotation(b)

    if a_npl or b_npl:
        if not include_npl:
            return False
        return a_npl and b_npl

    span1 = normalize_span(a.get("text"))
    span2 = normalize_span(b.get("text"))
    return (
        (span1 in span2 or span2 in span1 or longest_common_token_run(a.get("text"), b.get("text")) >= 3)
        and non_stopword_overlap(a.get("text"), b.get("text"))
    )


def sorted_annotations(annotations: Iterable[dict]) -> list[dict]:
    return sorted(
        annotations,
        key=lambda ann: (
            int(ann.get("paragraphIndex") or -1),
            normalize_label(ann.get("category")),
            canonical_subcategory(ann),
            normalize_span(ann.get("text")),
        ),
    )


def greedy_match(annotations_a: list[dict], annotations_b: list[dict], *, include_npl: bool) -> int:
    used_b: set[int] = set()
    matched = 0

    for ann_a in sorted_annotations(annotations_a):
        for idx_b, ann_b in enumerate(sorted_annotations(annotations_b)):
            if idx_b in used_b:
                continue
            if spans_match(ann_a, ann_b, include_npl=include_npl):
                used_b.add(idx_b)
                matched += 1
                break

    return matched


def dice_f1(match_count: int, a_count: int, b_count: int) -> float:
    denom = a_count + b_count
    return (2 * match_count / denom) if denom else 0.0


def jaccard(match_count: int, a_count: int, b_count: int) -> float:
    denom = a_count + b_count - match_count
    return (match_count / denom) if denom else 0.0


def pairwise_span_overlap(worker_annotations: dict[str, dict[str, list[dict]]], *, include_npl: bool) -> dict:
    pair_summaries: list[dict] = []
    total_match = total_a = total_b = 0

    for article_id, by_worker in sorted(worker_annotations.items()):
        worker_ids = sorted(by_worker)
        for worker_a, worker_b in combinations(worker_ids, 2):
            anns_a = by_worker[worker_a]
            anns_b = by_worker[worker_b]
            match_count = greedy_match(anns_a, anns_b, include_npl=include_npl)
            a_count = len([ann for ann in anns_a if include_npl or not is_no_polarizing_annotation(ann)])
            b_count = len([ann for ann in anns_b if include_npl or not is_no_polarizing_annotation(ann)])
            f1 = dice_f1(match_count, a_count, b_count)
            jac = jaccard(match_count, a_count, b_count)
            pair_summaries.append(
                {
                    "article_id": article_id,
                    "worker_a": worker_a,
                    "worker_b": worker_b,
                    "count_a": a_count,
                    "count_b": b_count,
                    "matched": match_count,
                    "dice_f1": round(f1, 3),
                    "jaccard": round(jac, 3),
                }
            )
            total_match += match_count
            total_a += a_count
            total_b += b_count

    macro_f1 = sum(item["dice_f1"] for item in pair_summaries) / len(pair_summaries) if pair_summaries else 0.0
    macro_jaccard = sum(item["jaccard"] for item in pair_summaries) / len(pair_summaries) if pair_summaries else 0.0
    micro_f1 = dice_f1(total_match, total_a, total_b)
    micro_jaccard = jaccard(total_match, total_a, total_b)

    return {
        "pair_count": len(pair_summaries),
        "macro_dice_f1": round(macro_f1, 3),
        "macro_jaccard": round(macro_jaccard, 3),
        "micro_dice_f1": round(micro_f1, 3),
        "micro_jaccard": round(micro_jaccard, 3),
        "matched_spans": total_match,
        "total_annotations_a": total_a,
        "total_annotations_b": total_b,
        "pair_examples": pair_summaries[:10],
    }


def derive_paragraph_category_label(annotations: list[dict]) -> str | None:
    polarizing = [canonical_category(ann) for ann in annotations if not is_no_polarizing_annotation(ann)]
    if polarizing:
        counts = Counter(polarizing)
        best_count = max(counts.values())
        # For category alpha, collapse multi-label paragraphs to the most frequent
        # top-level category; on ties, keep the first polarizing category encountered.
        for label in polarizing:
            if counts[label] == best_count:
                return label
    if any(is_no_polarizing_annotation(ann) for ann in annotations):
        return NPL_LABEL
    return None


def derive_paragraph_binary_label(annotations: list[dict]) -> str | None:
    if any(not is_no_polarizing_annotation(ann) for ann in annotations):
        return POLARIZING_LABEL
    if any(is_no_polarizing_annotation(ann) for ann in annotations):
        return NPL_LABEL
    return None


def derive_paragraph_subcategory_label(annotations: list[dict]) -> str | None:
    polarizing = [canonical_subcategory(ann) for ann in annotations if not is_no_polarizing_annotation(ann)]
    if polarizing:
        counts = Counter(polarizing)
        best_count = max(counts.values())
        # Mirror category behavior: majority subcategory; on ties, keep first seen.
        for label in polarizing:
            if counts[label] == best_count:
                return label
    if any(is_no_polarizing_annotation(ann) for ann in annotations):
        return NPL_LABEL
    return None


def pairwise_percent_agreement(unit_ratings: list[list[str]]) -> float | None:
    total_pairs = 0
    agree_pairs = 0
    for ratings in unit_ratings:
        counts = Counter(ratings)
        n = sum(counts.values())
        if n < 2:
            continue
        total_pairs += n * (n - 1) / 2
        agree_pairs += sum(count * (count - 1) / 2 for count in counts.values())
    if total_pairs == 0:
        return None
    return agree_pairs / total_pairs


def krippendorff_alpha_nominal(unit_ratings: list[list[str]]) -> float | None:
    labels = sorted({label for ratings in unit_ratings for label in ratings})
    if len(labels) < 2:
        return None

    label_index = {label: idx for idx, label in enumerate(labels)}
    coincidence = [[0] * len(labels) for _ in labels]

    for ratings in unit_ratings:
        counts = Counter(ratings)
        n = sum(counts.values())
        if n < 2:
            continue
        for label, count in counts.items():
            idx = label_index[label]
            coincidence[idx][idx] += count * (count - 1)
        count_labels = list(counts.keys())
        for i in range(len(count_labels)):
            for j in range(i + 1, len(count_labels)):
                li = count_labels[i]
                lj = count_labels[j]
                ci = counts[li]
                cj = counts[lj]
                idx_i = label_index[li]
                idx_j = label_index[lj]
                coincidence[idx_i][idx_j] += ci * cj
                coincidence[idx_j][idx_i] += ci * cj

    total = sum(sum(row) for row in coincidence)
    if total == 0:
        return None

    observed_disagreement = 0.0
    for i in range(len(labels)):
        for j in range(len(labels)):
            if i != j:
                observed_disagreement += coincidence[i][j]
    observed_disagreement /= total

    marginal = [sum(row) for row in coincidence]
    if total <= 1:
        return None
    expected_disagreement = (total * total - sum(m * m for m in marginal)) / (total * (total - 1))
    if expected_disagreement == 0:
        return 1.0
    return 1 - (observed_disagreement / expected_disagreement)


def cohen_kappa_for_pair(labels_a: list[str], labels_b: list[str]) -> float | None:
    if len(labels_a) != len(labels_b) or len(labels_a) < 2:
        return None
    observed = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / len(labels_a)
    counts_a = Counter(labels_a)
    counts_b = Counter(labels_b)
    all_labels = set(counts_a) | set(counts_b)
    expected = sum((counts_a[label] / len(labels_a)) * (counts_b[label] / len(labels_b)) for label in all_labels)
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1 - expected)


def pairwise_cohen_kappa(units: dict[tuple[str, int], dict[str, str]]) -> dict:
    by_worker_pair: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for worker_labels in units.values():
        for worker_a, worker_b in combinations(sorted(worker_labels), 2):
            by_worker_pair[(worker_a, worker_b)].append((worker_labels[worker_a], worker_labels[worker_b]))

    kappas = []
    weighted_sum = 0.0
    weight_total = 0
    for (worker_a, worker_b), labels in by_worker_pair.items():
        if len(labels) < 2:
            continue
        labels_a = [a for a, _ in labels]
        labels_b = [b for _, b in labels]
        kappa = cohen_kappa_for_pair(labels_a, labels_b)
        if kappa is None:
            continue
        kappas.append(
            {
                "worker_a": worker_a,
                "worker_b": worker_b,
                "shared_units": len(labels),
                "kappa": round(kappa, 3),
            }
        )
        weighted_sum += kappa * len(labels)
        weight_total += len(labels)

    weighted_mean = (weighted_sum / weight_total) if weight_total else None
    return {
        "pair_count": len(kappas),
        "weighted_mean_kappa": round(weighted_mean, 3) if weighted_mean is not None else None,
        "pair_examples": kappas[:10],
    }


def load_raw_annotations(path: Path) -> tuple[dict, dict[str, dict[str, list[dict]]], dict[tuple[str, str, int], list[dict]]]:
    raw_data = json.loads(path.read_text())
    annotations_by_worker_article: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    annotations_by_worker_paragraph: dict[tuple[str, str, int], list[dict]] = defaultdict(list)

    for worker_id, entry in raw_data.items():
        article_title_map = {
            str(item["id"]): item.get("title", "")
            for item in (entry.get("articleTitles") or [])
            if isinstance(item, dict) and item.get("id") is not None
        }

        text_annotations = entry.get("textAnnotations")
        if not text_annotations:
            continue

        if isinstance(text_annotations, dict):
            iterable = text_annotations.items()
        elif isinstance(text_annotations, list):
            iterable = [(str(index), annotations) for index, annotations in enumerate(text_annotations)]
        else:
            continue

        for article_id, annotations in iterable:
            if not isinstance(annotations, list):
                continue
            title = article_title_map.get(str(article_id), "")
            for ann in annotations:
                if not isinstance(ann, dict):
                    continue
                pidx = ann.get("paragraphIndex")
                if not isinstance(pidx, int):
                    continue
                normalized = {
                    "workerId": worker_id,
                    "articleId": str(article_id),
                    "title": title,
                    "paragraphIndex": pidx,
                    "text": ann.get("text", ""),
                    "category": canonical_category(ann),
                    "subcategory": canonical_subcategory(ann),
                }
                annotations_by_worker_article[str(article_id)][worker_id].append(normalized)
                annotations_by_worker_paragraph[(worker_id, str(article_id), pidx)].append(normalized)

    return raw_data, annotations_by_worker_article, annotations_by_worker_paragraph


def build_unit_labels(
    annotations_by_worker_paragraph: dict[tuple[str, str, int], list[dict]],
    *,
    label_mode: str,
) -> dict[tuple[str, int], dict[str, str]]:
    units: dict[tuple[str, int], dict[str, str]] = defaultdict(dict)
    if label_mode == "binary":
        derive = derive_paragraph_binary_label
    elif label_mode == "category":
        derive = derive_paragraph_category_label
    else:
        derive = derive_paragraph_subcategory_label
    for (worker_id, article_id, paragraph_index), annotations in annotations_by_worker_paragraph.items():
        label = derive(annotations)
        if label is None:
            continue
        units[(article_id, paragraph_index)][worker_id] = label
    return units


def build_unit_ratings(units: dict[tuple[str, int], dict[str, str]]) -> list[list[str]]:
    return [list(worker_labels.values()) for worker_labels in units.values() if len(worker_labels) >= 2]


def build_one_vs_rest_units(
    annotations_by_worker_paragraph: dict[tuple[str, str, int], list[dict]],
    *,
    label_mode: str,
    labels: list[str],
) -> dict[str, dict[tuple[str, int], dict[str, str]]]:
    units_by_label = {label: defaultdict(dict) for label in labels}

    for (worker_id, article_id, paragraph_index), annotations in annotations_by_worker_paragraph.items():
        if label_mode == "category":
            present_labels = {ann["category"] for ann in annotations if ann.get("category")}
        else:
            present_labels = {ann["subcategory"] for ann in annotations if ann.get("subcategory")}

        for label in labels:
            units_by_label[label][(article_id, paragraph_index)][worker_id] = "present" if label in present_labels else "absent"

    return units_by_label


def summarize_one_vs_rest_agreement(
    annotations_by_worker_paragraph: dict[tuple[str, str, int], list[dict]],
    *,
    label_mode: str,
    labels: list[str],
) -> dict[str, dict]:
    units_by_label = build_one_vs_rest_units(
        annotations_by_worker_paragraph,
        label_mode=label_mode,
        labels=labels,
    )

    summaries = {}
    total_worker_paragraph_units = len(annotations_by_worker_paragraph)
    for label, units in units_by_label.items():
        ratings = build_unit_ratings(units)
        positive_ratings = sum(1 for worker_labels in units.values() for value in worker_labels.values() if value == "present")
        summaries[label] = {
            "positive_ratings": positive_ratings,
            "positive_share_of_worker_paragraph_units": round(positive_ratings / total_worker_paragraph_units, 4)
            if total_worker_paragraph_units
            else 0.0,
            "pairwise_percent_agreement": round(pairwise_percent_agreement(ratings) or 0.0, 3),
            "pairwise_cohen_kappa": pairwise_cohen_kappa(units),
            "krippendorff_alpha_nominal": round(krippendorff_alpha_nominal(ratings) or 0.0, 3),
        }
    return summaries


def density_table(counter: Counter, *, total_annotations: int, total_worker_paragraph_units: int) -> dict[str, dict[str, float | int]]:
    table = {}
    for label, count in sorted(counter.items()):
        table[label] = {
            "count": count,
            "share_of_annotations": round(count / total_annotations, 4) if total_annotations else 0.0,
            "annotations_per_worker_paragraph": round(count / total_worker_paragraph_units, 4) if total_worker_paragraph_units else 0.0,
        }
    return table


def summarize(input_path: Path) -> dict:
    raw_data, annotations_by_worker_article, annotations_by_worker_paragraph = load_raw_annotations(input_path)
    raw_annotations = [ann for anns in annotations_by_worker_paragraph.values() for ann in anns]
    total_worker_paragraph_units = len(annotations_by_worker_paragraph)

    category_counts = Counter(ann["category"] for ann in raw_annotations)
    subcategory_counts = Counter(ann["subcategory"] for ann in raw_annotations)

    units_binary = build_unit_labels(annotations_by_worker_paragraph, label_mode="binary")
    units_category = build_unit_labels(annotations_by_worker_paragraph, label_mode="category")
    units_subcategory = build_unit_labels(annotations_by_worker_paragraph, label_mode="subcategory")

    binary_ratings = build_unit_ratings(units_binary)
    category_ratings = build_unit_ratings(units_category)
    subcategory_ratings = build_unit_ratings(units_subcategory)

    article_counts = Counter()
    for entry in raw_data.values():
        for item in (entry.get("articleTitles") or []):
            if isinstance(item, dict) and item.get("id") is not None:
                article_counts[str(item["id"])] += 1

    return {
        "input_path": str(input_path),
        "dataset_summary": {
            "workers": len(raw_data),
            "articles": len(article_counts),
            "article_worker_counts": {k: article_counts[k] for k in sorted(article_counts, key=lambda x: int(x))},
            "worker_paragraph_units": total_worker_paragraph_units,
            "raw_annotations": len(raw_annotations),
        },
        "density": {
            "category": density_table(
                category_counts,
                total_annotations=len(raw_annotations),
                total_worker_paragraph_units=total_worker_paragraph_units,
            ),
            "subcategory": density_table(
                subcategory_counts,
                total_annotations=len(raw_annotations),
                total_worker_paragraph_units=total_worker_paragraph_units,
            ),
        },
        "span_overlap": {
            "including_npl": pairwise_span_overlap(annotations_by_worker_article, include_npl=True),
            "polarizing_only": pairwise_span_overlap(annotations_by_worker_article, include_npl=False),
        },
        "agreement": {
            "overall_binary": {
                "pairwise_percent_agreement": round(pairwise_percent_agreement(binary_ratings) or 0.0, 3),
                "pairwise_cohen_kappa": pairwise_cohen_kappa(units_binary),
                "krippendorff_alpha_nominal": round(krippendorff_alpha_nominal(binary_ratings) or 0.0, 3),
            },
            "category": {
                "pairwise_percent_agreement": round(pairwise_percent_agreement(category_ratings) or 0.0, 3),
                "pairwise_cohen_kappa": pairwise_cohen_kappa(units_category),
                "krippendorff_alpha_nominal": round(krippendorff_alpha_nominal(category_ratings) or 0.0, 3),
            },
            "subcategory": {
                "pairwise_percent_agreement": round(pairwise_percent_agreement(subcategory_ratings) or 0.0, 3),
                "pairwise_cohen_kappa": pairwise_cohen_kappa(units_subcategory),
                "krippendorff_alpha_nominal": round(krippendorff_alpha_nominal(subcategory_ratings) or 0.0, 3),
            },
            "category_one_vs_rest": summarize_one_vs_rest_agreement(
                annotations_by_worker_paragraph,
                label_mode="category",
                labels=[NPL_LABEL, "persuasive propaganda", "inflammatory language"],
            ),
            "subcategory_one_vs_rest": summarize_one_vs_rest_agreement(
                annotations_by_worker_paragraph,
                label_mode="subcategory",
                labels=[
                    NPL_LABEL,
                    "exaggeration",
                    "slogans",
                    "bandwagon",
                    "casual oversimplification",
                    "doubt",
                    "name-calling",
                    "demonization",
                    "scapegoating",
                ],
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=str(base_dir / "../../mturk_results/1-20/1-20-in-house.json"),
    )
    parser.add_argument(
        "--output",
        default=str(base_dir / "1-20/1-20_in_house_density_and_agreement.json"),
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary = summarize(input_path)
    output_path.write_text(json.dumps(summary, indent=2))

    print(f"Saved analysis to {output_path}")
    print(json.dumps(summary["dataset_summary"], indent=2))
    print("Span overlap (polarizing only):", summary["span_overlap"]["polarizing_only"])
    print("Overall binary agreement:", summary["agreement"]["overall_binary"])
    print("Category agreement:", summary["agreement"]["category"])
    print("Subcategory agreement:", summary["agreement"]["subcategory"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
