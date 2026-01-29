import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ------------------------
# Configure Matplotlib cache directory
# ------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # .../src
OUTPUT_DIR = BASE_DIR / "data_visualizations"
MPLCONFIGDIR = OUTPUT_DIR / ".mplconfig"
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))

import matplotlib.pyplot as plt  # noqa: E402


# ------------------------
# Inputs / Outputs
# ------------------------
MTURK_RAW_PATH = BASE_DIR / "mturk_results/archived_mturk_results/1-8/1-8HIT.json"
LLM_PATH = BASE_DIR / "llm_annotation_results/per_model_annotations/per_model_annotations_3models.json"
## LLM_PATH = BASE_DIR / "llm_annotation_results/per_model_annotations/per_model_annotations_3models.json"
OUTPUT_IMG = OUTPUT_DIR / "confusion_matrix_llm_vs_raw_mturk_subcategory_pooled.png"

# If LLM_PATH points at a per-model output (from
# src/dataset_comparison_scripts/per_model_annotations/run_wrapper_multiple_llm_annotations_per_model.py),
# select which model to compare.
#
# Valid options: "annotator_A", "annotator_B", "annotator_C"
PER_MODEL_ANNOTATOR_KEY = "annotator_A"


# ------------------------
# Ordering (least -> most severe)
# ------------------------
# Requested: exaggeration, casual oversimplification, doubt, slogans, bandwagon,
#           scapegoating, name-calling, demonization.
INCLUDE_NPL_IN_MATRIX = False

SEVERITY_ORDER = [
    "exaggeration",
    "casual oversimplification",
    "bandwagon",
    "doubt",
    "slogans",
    "scapegoating",
    "name-calling",
    "demonization",
]

NPL_NORMALIZED = "no polarizing language"
NPL_DISPLAY = "NPL"

SUBCATEGORY_ALIASES = {
    "exaggeration": "exaggeration",
    "casual oversimplification": "casual oversimplification",
    "casual-oversimplification": "casual oversimplification",
    # Common typo from model outputs
    "causal oversimplification": "casual oversimplification",
    "doubt": "doubt",
    "slogans": "slogans",
    "slogan": "slogans",
    "bandwagon": "bandwagon",
    "scapegoating": "scapegoating",
    "name calling": "name-calling",
    "name-calling": "name-calling",
    "namecalling": "name-calling",
    "demonization": "demonization",
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
    """
    Condense a list of span annotations (for a single worker-paragraph or a single LLM-paragraph)
    into a single subcategory label:
    - Use the most frequent polarizing subcategory (ignore NPL if any polarizing exists).
    - If tied, choose the most severe among tied.
    - If no polarizing spans exist, return NPL.
    """
    polarizing_subcats = []
    saw_npl = False

    for ann in annotations:
        if not isinstance(ann, dict):
            continue
        if is_no_polarizing(ann):
            saw_npl = True
            continue
        polarizing_subcats.append(
            canonicalize_subcategory(ann.get("subcategory"), is_npl=False)
        )

    if not polarizing_subcats:
        return NPL_NORMALIZED if saw_npl else NPL_NORMALIZED

    counts = Counter(polarizing_subcats)
    max_count = max(counts.values())
    tied = [label for label, c in counts.items() if c == max_count]
    if len(tied) == 1:
        return tied[0]

    # Tie: choose the most severe.
    tied.sort(key=lambda lab: (severity_score(lab), lab))
    return tied[-1]


def build_llm_paragraph_labels(llm_payload) -> Dict[Tuple[str, int], str]:
    """
    Return {(normalized_title, paragraphIndex): condensed_subcategory}
    """
    labels: Dict[Tuple[str, int], str] = {}

    for article in llm_payload:
        # Supported shapes:
        # 1) Adjudicated/standard: {"title": ..., "annotations": [...]}
        # 2) Per-model: {"title": ..., "annotator_A": {...}, "annotator_B": {...}, "annotator_C": {...}}
        if not isinstance(article, dict):
            continue

        title_norm = normalize_title(article.get("title", ""))
        if "annotations" in article:
            annotations = article.get("annotations", [])
        elif PER_MODEL_ANNOTATOR_KEY in article:
            model_obj = article.get(PER_MODEL_ANNOTATOR_KEY) or {}
            annotations = model_obj.get("annotations", [])
        else:
            continue

        by_para: Dict[int, List[dict]] = defaultdict(list)
        for ann in annotations:
            pidx = ann.get("paragraphIndex")
            if isinstance(pidx, int):
                by_para[pidx].append(ann)

        for pidx, anns in by_para.items():
            labels[(title_norm, pidx)] = condense_subcategory_most_frequent_tiebreak_severity(anns)

    return labels


def build_worker_paragraph_groups(mturk_payload) -> Dict[Tuple[str, str, int], List[dict]]:
    """
    Return {(worker_id, normalized_title, paragraphIndex): [raw annotations...]}

    NOTE: This includes only paragraphs that workers explicitly annotated and that have a
    paragraphIndex, since the raw HIT file does not reliably contain \"blank\" paragraphs.
    """
    groups: Dict[Tuple[str, str, int], List[dict]] = defaultdict(list)

    if not isinstance(mturk_payload, dict):
        return groups

    for worker_id, entry in mturk_payload.items():
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

        for article_id, annotations in ta.items():
            if not isinstance(annotations, list):
                continue
            for ann in annotations:
                if not isinstance(ann, dict):
                    continue
                pidx = ann.get("paragraphIndex")
                if not isinstance(pidx, int):
                    continue
                title = ann.get("title") or title_map.get(str(article_id))
                if not title:
                    continue
                groups[(str(worker_id), normalize_title(title), pidx)].append(ann)

    return groups


def display_label(label: str) -> str:
    if label == NPL_NORMALIZED:
        return NPL_DISPLAY

    # Title-case, but preserve hyphenated forms (e.g., name-calling -> Name-Calling).
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

    subtitle = f"Pooled worker-paragraph units (n={unit_count})"
    if not INCLUDE_NPL_IN_MATRIX:
        subtitle += " (excluding NPL)"
    ax.set_title(f"LLM vs Raw MTurk Confusion Matrix (Subcategory)\n{subtitle}", pad=18)

    tick_labels = [display_label(l) for l in labels]
    ax.set_xticks(range(n), tick_labels, rotation=45, ha="right")
    ax.set_yticks(range(n), tick_labels)
    ax.set_xlabel("LLM (predicted subcategory)", fontweight="bold")
    ax.set_ylabel("Raw MTurk worker (true subcategory)", fontweight="bold")

    # Annotate counts.
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
    mturk_payload = load_json(MTURK_RAW_PATH)
    llm_payload = load_json(LLM_PATH)

    llm_labels = build_llm_paragraph_labels(llm_payload)
    worker_groups = build_worker_paragraph_groups(mturk_payload)

    confusion: Dict[str, Counter] = defaultdict(Counter)  # true -> pred -> count
    true_counts = Counter()
    pred_counts = Counter()
    used_units = 0
    skipped_missing_llm = 0

    for (_, title_norm, pidx), anns in worker_groups.items():
        true = condense_subcategory_most_frequent_tiebreak_severity(anns)
        pred = llm_labels.get((title_norm, pidx))
        if pred is None:
            skipped_missing_llm += 1
            continue
        confusion[true][pred] += 1
        true_counts[true] += 1
        pred_counts[pred] += 1
        used_units += 1

    base_labels: List[str] = []
    if INCLUDE_NPL_IN_MATRIX:
        base_labels.append(NPL_NORMALIZED)
    base_labels.extend(SEVERITY_ORDER)

    observed_labels = sorted(set(true_counts.keys()) | set(pred_counts.keys()))
    if not INCLUDE_NPL_IN_MATRIX:
        observed_labels = [l for l in observed_labels if l != NPL_NORMALIZED]
    extras = [l for l in observed_labels if l not in base_labels]
    labels = base_labels + extras

    print("Raw MTurk vs LLM (pooled worker-paragraphs)")
    print("------------------------------------------")
    print(f"MTURK_RAW_PATH: {MTURK_RAW_PATH}")
    print(f"LLM_PATH:       {LLM_PATH}")
    if isinstance(llm_payload, list) and llm_payload and isinstance(llm_payload[0], dict) and PER_MODEL_ANNOTATOR_KEY in llm_payload[0]:
        print(f"Per-model LLM file detected; using: {PER_MODEL_ANNOTATOR_KEY}")
    print(f"Worker-paragraph groups (with paragraphIndex): {len(worker_groups)}")
    print(f"LLM title-paragraph keys: {len(llm_labels)}")
    print(f"Aligned units used: {used_units}")
    print(f"Skipped (no matching LLM paragraphIndex for title): {skipped_missing_llm}")
    print(f"Raw worker label counts: {dict(true_counts)}")
    print(f"LLM label counts (for aligned units): {dict(pred_counts)}")
    if extras:
        print(f"Extra labels (appended at end): {extras}")

    plot_confusion_matrix(confusion, labels, used_units)


if __name__ == "__main__":
    main()
