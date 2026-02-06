import json
import os
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(
    BASE_DIR,"../../mturk_results/archived_mturk_results/1-8/1-8HIT_2026_01.json",
)
# BASE_DIR,"../../mturk_results/1-20/1-20-in-house.json"

NPL_LABEL = "No Polarizing Language"
POLARIZING_LABEL = "Polarizing Language"
MULTI_CATEGORY_LABEL = "Multiple Polarizing Categories"
# Majority vote tie handling for binary labels: "npl", "polarizing", or "exclude".
MAJORITY_TIE_BREAKER = "npl"


def is_no_polarizing_annotation(ann: dict) -> bool:
    cat = (ann.get("category") or "").strip().lower()
    sub = (ann.get("subcategory") or "").strip().lower()
    return cat == "no_polarizing_language" or sub == "no polarizing language"


def normalize_category(category: Optional[str]) -> Optional[str]:
    if not category:
        return None
    normalized = category.replace("_", " ").strip().lower()
    if normalized == "no polarizing language":
        return NPL_LABEL
    if normalized == "persuasive propaganda":
        return "Persuasive Propaganda"
    if normalized == "inflammatory language":
        return "Inflammatory Language"
    return normalized.title()


def collect_annotations_by_worker_paragraph(
    raw_data: dict,
) -> Dict[Tuple[str, str, int], List[dict]]:
    annotations_by_key: Dict[Tuple[str, str, int], List[dict]] = defaultdict(list)

    for worker_id, entry in raw_data.items():
        ta = entry.get("textAnnotations")
        if not ta:
            continue

        # Case 1: textAnnotations is a dict keyed by article id
        if isinstance(ta, dict):
            for article_id, annotations in ta.items():
                if not isinstance(annotations, list):
                    continue
                for ann in annotations:
                    if not isinstance(ann, dict):
                        continue
                    pidx = ann.get("paragraphIndex")
                    if isinstance(pidx, int):
                        annotations_by_key[(worker_id, str(article_id), pidx)].append(ann)

        # Case 2: textAnnotations is a list; use index as fallback article id
        elif isinstance(ta, list):
            for article_index, annotations in enumerate(ta):
                if not annotations or not isinstance(annotations, list):
                    continue
                for ann in annotations:
                    if not isinstance(ann, dict):
                        continue
                    pidx = ann.get("paragraphIndex")
                    if isinstance(pidx, int):
                        annotations_by_key[(worker_id, str(article_index), pidx)].append(ann)

    return annotations_by_key


def derive_labels(annotations: Iterable[dict]) -> Optional[dict]:
    has_npl = False
    polarizing_categories = []

    for ann in annotations:
        if is_no_polarizing_annotation(ann):
            has_npl = True
            continue
        category = normalize_category(ann.get("category"))
        if category:
            polarizing_categories.append(category)

    if polarizing_categories:
        unique_categories = sorted(set(polarizing_categories))
        if len(unique_categories) == 1:
            category_label = unique_categories[0]
            multi_category = False
        else:
            category_label = MULTI_CATEGORY_LABEL
            multi_category = True
        binary_label = POLARIZING_LABEL
    elif has_npl:
        category_label = NPL_LABEL
        binary_label = NPL_LABEL
        multi_category = False
    else:
        return None

    return {
        "binary": binary_label,
        "category": category_label,
        "has_npl": has_npl,
        "multi_category": multi_category,
        "has_polarizing": bool(polarizing_categories),
    }


def build_unit_ratings(units: Dict[Tuple[str, int], Dict[str, dict]], label_key: str) -> List[List[str]]:
    ratings = []
    for worker_labels in units.values():
        labels = [info[label_key] for info in worker_labels.values() if info.get(label_key) is not None]
        if len(labels) >= 2:
            ratings.append(labels)
    return ratings


def majority_vote_binary(worker_labels: Dict[str, dict]) -> Optional[str]:
    counts = Counter(
        info["binary"] for info in worker_labels.values() if info.get("binary") is not None
    )
    npl_count = counts.get(NPL_LABEL, 0)
    polarizing_count = counts.get(POLARIZING_LABEL, 0)

    if npl_count > polarizing_count:
        return NPL_LABEL
    if polarizing_count > npl_count:
        return POLARIZING_LABEL
    if npl_count == 0 and polarizing_count == 0:
        return None

    if MAJORITY_TIE_BREAKER == "npl":
        return NPL_LABEL
    if MAJORITY_TIE_BREAKER == "polarizing":
        return POLARIZING_LABEL
    return None


def pairwise_agreement(unit_ratings: List[List[str]]) -> Optional[float]:
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


def krippendorff_alpha_nominal(unit_ratings: List[List[str]]) -> Optional[float]:
    labels = sorted({label for ratings in unit_ratings for label in ratings})
    if len(labels) < 2:
        return None

    label_index = {label: idx for idx, label in enumerate(labels)}
    k = len(labels)
    coincidence = [[0] * k for _ in range(k)]

    for ratings in unit_ratings:
        counts = Counter(ratings)
        n = sum(counts.values())
        if n < 2:
            continue
        # Diagonal
        for label, count in counts.items():
            i = label_index[label]
            coincidence[i][i] += count * (count - 1)
        # Off-diagonal
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
    for i in range(k):
        for j in range(k):
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


def format_percent(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def main() -> None:
    with open(INPUT_FILE, "r") as f:
        raw_data = json.load(f)

    annotations_by_key = collect_annotations_by_worker_paragraph(raw_data)

    units: Dict[Tuple[str, int], Dict[str, dict]] = defaultdict(dict)
    worker_ids = set()
    mixed_npl_and_polarizing = 0
    multi_category = 0

    for (worker_id, article_id, paragraph_index), annotations in annotations_by_key.items():
        label_info = derive_labels(annotations)
        if not label_info:
            continue
        units[(article_id, paragraph_index)][worker_id] = label_info
        worker_ids.add(worker_id)
        if label_info["has_npl"] and label_info["has_polarizing"]:
            mixed_npl_and_polarizing += 1
        if label_info["multi_category"]:
            multi_category += 1

    ratings_per_unit = Counter(len(worker_labels) for worker_labels in units.values())
    total_labels = sum(len(worker_labels) for worker_labels in units.values())
    majority_labels = {}
    tie_count = 0
    for unit_key, worker_labels in units.items():
        counts = Counter(
            info["binary"] for info in worker_labels.values() if info.get("binary") is not None
        )
        npl_count = counts.get(NPL_LABEL, 0)
        polarizing_count = counts.get(POLARIZING_LABEL, 0)
        if npl_count == polarizing_count and npl_count > 0:
            tie_count += 1
        majority_label = majority_vote_binary(worker_labels)
        if majority_label is not None:
            majority_labels[unit_key] = majority_label

    binary_ratings = build_unit_ratings(units, "binary")
    category_ratings = build_unit_ratings(units, "category")

    binary_label_counts = Counter(label for ratings in binary_ratings for label in ratings)
    category_label_counts = Counter(label for ratings in category_ratings for label in ratings)

    print(f"Inter-Annotator Agreement (HIT)")
    print("=================================")
    print(f"Input file: {INPUT_FILE}")
    print(f"Annotators: {len(worker_ids)}")
    print(f"Units (article, paragraph): {len(units)}")
    print(f"Units by # annotators: {dict(sorted(ratings_per_unit.items()))}")
    print(f"Worker-paragraph labels: {total_labels}")
    print(f"Mixed NPL+polarizing labels: {mixed_npl_and_polarizing}")
    print(f"Multi-category polarizing labels: {multi_category}")

    print("\nBinary Labels (NPL vs Polarizing)")
    print("---------------------------------")
    print(f"Label counts: {dict(binary_label_counts)}")
    print(f"Pairwise agreement: {format_percent(pairwise_agreement(binary_ratings))}")
    alpha_binary = krippendorff_alpha_nominal(binary_ratings)
    print(f"Krippendorff's alpha (nominal): {alpha_binary:.4f}" if alpha_binary is not None else "Krippendorff's alpha (nominal): n/a")
    majority_counts = Counter(majority_labels.values())
    print(f"Majority labels: {dict(majority_counts)}")
    print(f"Tied majorities: {tie_count} (tie breaker: {MAJORITY_TIE_BREAKER})")

    print("\nCategory Labels (NPL vs Category)")
    print("---------------------------------")
    print(f"Label counts: {dict(category_label_counts)}")
    print(f"Pairwise agreement: {format_percent(pairwise_agreement(category_ratings))}")
    alpha_category = krippendorff_alpha_nominal(category_ratings)
    print(f"Krippendorff's alpha (nominal): {alpha_category:.4f}" if alpha_category is not None else "Krippendorff's alpha (nominal): n/a")


if __name__ == "__main__":
    main()
