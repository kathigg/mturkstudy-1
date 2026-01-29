import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


# ------------------------
# Configure Matplotlib cache directory
# ------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # .../src
OUTPUT_DIR = BASE_DIR / "data_visualizations"
MPLCONFIGDIR = OUTPUT_DIR / ".mplconfig"
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))

import matplotlib.pyplot as plt  # noqa: E402


# ------------------------
# Inputs
# ------------------------
TWELVE_ARTICLE_CSV = BASE_DIR / "dataset_comparison_scripts/twelve_article_set.csv"
MTURK_FULL_OVERALL_PATH = BASE_DIR / "mturk_results/1-20/1-20_FULL_OVERALL.json"
PER_MODEL_LLM_PATH = BASE_DIR / "llm_annotation_results/per_model_annotations/per_model_annotations_3models.json"


# ------------------------
# Output
# ------------------------
OUTPUT_IMG = OUTPUT_DIR / "confusion_matrix_llm_vs_mturk_full_overall_subcategory_aggregate.png"


# ------------------------
# Matrix configuration
# ------------------------
# If False, NPL is excluded from the plotted labels (matching the style of
# confusion_matrix_llm_vs_raw_mturk_subcategory_pooled.png).
INCLUDE_NPL_IN_MATRIX = False

# Order of subcategories on both axes (least -> most severe).
SEVERITY_ORDER = [
    "doubt",
    "exaggeration",
    "casual oversimplification",
    "slogans",
    "bandwagon",
    "scapegoating",
    "name-calling",
    "demonization",
]

NPL_NORMALIZED = "no polarizing language"
NPL_DISPLAY = "NPL"

SUBCATEGORY_ALIASES = {
    "exaggeration": "exaggeration",
    "doubt": "doubt",
    "slogans": "slogans",
    "slogan": "slogans",
    "bandwagon": "bandwagon",
    "scapegoating": "scapegoating",
    "demonization": "demonization",
    "casual oversimplification": "casual oversimplification",
    "casual-oversimplification": "casual oversimplification",
    # common typo(s)
    "causal oversimplification": "casual oversimplification",
    "causal-oversimplification": "casual oversimplification",
    "name calling": "name-calling",
    "name-calling": "name-calling",
    "namecalling": "name-calling",
    # NPL variants
    "no polarizing language": "no polarizing language",
    "no polarizing": "no polarizing language",
    "no_polarizing_language": "no polarizing language",
}

SEVERITY_RANK = {label: idx for idx, label in enumerate(SEVERITY_ORDER)}


def load_json(path: Path):
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"{path} is empty.")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def normalize_title(title: str) -> str:
    return re.sub(r"[^\w\s]", "", title or "").strip().lower()


def normalize_label(label: str) -> str:
    s = (label or "").replace("_", " ").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def is_no_polarizing(ann: dict) -> bool:
    cat = normalize_label(ann.get("category", ""))
    sub = normalize_label(ann.get("subcategory", ""))
    text = normalize_label(ann.get("text", ""))
    return NPL_NORMALIZED in cat or NPL_NORMALIZED in sub or NPL_NORMALIZED in text


def canonicalize_subcategory(raw: Optional[str], *, is_npl: bool) -> str:
    if is_npl:
        return NPL_NORMALIZED
    s = normalize_label(raw or "")
    if not s:
        return "unspecified"
    return SUBCATEGORY_ALIASES.get(s, s)


def severity_score(label: str) -> int:
    if label == NPL_NORMALIZED:
        return -1
    return SEVERITY_RANK.get(label, -1)


def condense_subcategory_most_frequent_tiebreak_severity(annotations: List[dict]) -> str:
    polarizing_subcats = []
    saw_npl = False

    for ann in annotations:
        if not isinstance(ann, dict):
            continue
        if is_no_polarizing(ann):
            saw_npl = True
            continue
        polarizing_subcats.append(canonicalize_subcategory(ann.get("subcategory"), is_npl=False))

    if not polarizing_subcats:
        return NPL_NORMALIZED if saw_npl else NPL_NORMALIZED

    counts = Counter(polarizing_subcats)
    max_count = max(counts.values())
    tied = [label for label, c in counts.items() if c == max_count]
    if len(tied) == 1:
        return tied[0]

    tied.sort(key=lambda lab: (severity_score(lab), lab))
    return tied[-1]


def load_target_titles() -> set[str]:
    df = pd.read_csv(TWELVE_ARTICLE_CSV)
    return {normalize_title(t) for t in df["Headline"].tolist()}


def iter_mturk_full_overall_annotations(payload: dict) -> Iterable[dict]:
    if not isinstance(payload, dict):
        return

    for entry in payload.values():
        if not isinstance(entry, dict):
            continue

        title_map = {}
        for item in entry.get("articleTitles", []) or []:
            if not isinstance(item, dict):
                continue
            if item.get("id") is None:
                continue
            title_map[str(item.get("id"))] = item.get("title")

        ta = entry.get("textAnnotations")
        if not isinstance(ta, dict):
            continue

        for article_id, anns in ta.items():
            if not isinstance(anns, list):
                continue
            for ann in anns:
                if not isinstance(ann, dict):
                    continue
                if not ann.get("title"):
                    ann = dict(ann)
                    ann["title"] = title_map.get(str(article_id))
                yield ann


def build_llm_paragraph_prediction_map(per_model_payload: list) -> Dict[Tuple[str, int], str]:
    """
    Aggregate ALL model annotations (A+B+C) into a single per-paragraph prediction.
    """
    by_unit: Dict[Tuple[str, int], List[dict]] = defaultdict(list)
    for row in per_model_payload:
        if not isinstance(row, dict):
            continue
        title_norm = normalize_title(row.get("title", ""))
        for model_key in ("annotator_A", "annotator_B", "annotator_C"):
            model_obj = row.get(model_key) or {}
            for ann in model_obj.get("annotations", []) or []:
                if not isinstance(ann, dict):
                    continue
                pidx = ann.get("paragraphIndex")
                if not isinstance(pidx, int):
                    continue
                by_unit[(title_norm, pidx)].append(ann)

    pred: Dict[Tuple[str, int], str] = {}
    for unit, anns in by_unit.items():
        pred[unit] = condense_subcategory_most_frequent_tiebreak_severity(anns)
    return pred


def display_label(label: str) -> str:
    if label == NPL_NORMALIZED:
        return NPL_DISPLAY
    out = []
    for token in label.split(" "):
        if "-" in token:
            out.append("-".join([part.capitalize() for part in token.split("-")]))
        else:
            out.append(token.capitalize())
    return " ".join(out)


def plot_confusion_matrix(confusion: Dict[str, Counter], labels: List[str], unit_count: int) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)

    n = len(labels)
    matrix = [[confusion[true].get(pred, 0) for pred in labels] for true in labels]

    plt.style.use("seaborn-v0_8-colorblind")
    fig_w = max(10, 1.05 * n)
    fig_h = max(8, 0.95 * n)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    im = ax.imshow(matrix, cmap="Blues")
    ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    subtitle = f"Pooled MTurk span annotations (n={unit_count})"
    if not INCLUDE_NPL_IN_MATRIX:
        subtitle += " (excluding NPL)"
    ax.set_title(f"LLM vs MTurk FULL OVERALL Confusion Matrix (Subcategory)\n{subtitle}", pad=18)

    tick_labels = [display_label(l) for l in labels]
    ax.set_xticks(range(n), tick_labels, rotation=45, ha="right")
    ax.set_yticks(range(n), tick_labels)
    ax.set_xlabel("LLM (predicted subcategory)", fontweight="bold")
    ax.set_ylabel("MTurk (true subcategory)", fontweight="bold")

    vmax = max(max(row) for row in matrix) if matrix else 0
    threshold = vmax * 0.55
    for i in range(n):
        for j in range(n):
            val = matrix[i][j]
            color = "white" if val > threshold else "black"
            ax.text(j, i, str(val), ha="center", va="center", color=color, fontsize=10)

    fig.tight_layout()
    fig.savefig(OUTPUT_IMG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved confusion matrix to {OUTPUT_IMG}")


def main() -> None:
    target_titles = load_target_titles()
    mturk_payload = load_json(MTURK_FULL_OVERALL_PATH)
    llm_payload = load_json(PER_MODEL_LLM_PATH)

    llm_pred = build_llm_paragraph_prediction_map(llm_payload)

    confusion: Dict[str, Counter] = defaultdict(Counter)
    true_counts = Counter()
    pred_counts = Counter()

    used = 0
    skipped_missing_llm = 0
    skipped_title = 0
    skipped_missing_para = 0

    for ann in iter_mturk_full_overall_annotations(mturk_payload):
        title = ann.get("title")
        pidx = ann.get("paragraphIndex")
        if not title or not isinstance(pidx, int):
            skipped_missing_para += 1
            continue
        if normalize_title(title) not in target_titles:
            skipped_title += 1
            continue

        true = canonicalize_subcategory(ann.get("subcategory"), is_npl=is_no_polarizing(ann))
        pred = llm_pred.get((normalize_title(title), pidx))
        if pred is None:
            skipped_missing_llm += 1
            continue

        if not INCLUDE_NPL_IN_MATRIX:
            if true == NPL_NORMALIZED or pred == NPL_NORMALIZED:
                # Match the earlier \"exclude NPL\" behavior: do not plot NPL.
                # (This also drops these instances from the confusion counts.)
                continue

        confusion[true][pred] += 1
        true_counts[true] += 1
        pred_counts[pred] += 1
        used += 1

    base_labels: List[str] = []
    if INCLUDE_NPL_IN_MATRIX:
        base_labels.append(NPL_NORMALIZED)
    base_labels.extend(SEVERITY_ORDER)

    observed_labels = sorted(set(true_counts.keys()) | set(pred_counts.keys()))
    extras = [l for l in observed_labels if l not in base_labels]
    labels = base_labels + extras

    print("Full overall confusion matrix inputs")
    print("-----------------------------------")
    print(f"MTURK_FULL_OVERALL_PATH: {MTURK_FULL_OVERALL_PATH}")
    print(f"PER_MODEL_LLM_PATH:      {PER_MODEL_LLM_PATH}")
    print(f"Target titles (12-article set): {len(target_titles)}")
    print(f"LLM paragraph prediction keys: {len(llm_pred)}")
    print(f"Used MTurk span annotations: {used}")
    print(f"Skipped (missing paragraphIndex/title): {skipped_missing_para}")
    print(f"Skipped (title not in 12-article set): {skipped_title}")
    print(f"Skipped (no matching LLM paragraph): {skipped_missing_llm}")
    print(f"True label counts: {dict(true_counts)}")
    print(f"Pred label counts: {dict(pred_counts)}")
    if extras:
        print(f"Extra labels (appended at end): {extras}")

    plot_confusion_matrix(confusion, labels, used)


if __name__ == "__main__":
    main()

