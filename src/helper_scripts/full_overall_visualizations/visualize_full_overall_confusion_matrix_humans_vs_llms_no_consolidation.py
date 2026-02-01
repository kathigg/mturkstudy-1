'''
What this script does that makes it different from the six billion other heatmap scripts:
It uses THE ENTIRETY of the LLM annotations (models A, B, and C) without any consolidation whatsoever.
It consists of the largest un-aggregated version of the confusion map. 

'''
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
import numpy as np  # noqa: E402
from matplotlib import colors  # noqa: E402


# ------------------------
# Inputs
# ------------------------
TWELVE_ARTICLE_CSV = BASE_DIR / "dataset_comparison_scripts/twelve_article_set.csv"
MTURK_FULL_OVERALL_PATH = BASE_DIR / "mturk_results/1-20/1-20_FULL_OVERALL.json"
PER_MODEL_LLM_PATH = BASE_DIR / "llm_annotation_results/per_model_annotations/per_model_annotations_3models.json"


# ------------------------
# Output
# ------------------------
OUTPUT_IMG = OUTPUT_DIR / "confusion_matrix_llm_vs_mturk_full_overall_subcategory_no_consolidation.png"


# ------------------------
# Matrix configuration
# ------------------------
# If True, include NPL on both axes. If False, skip any pairs where either side is NPL.
INCLUDE_NPL_IN_MATRIX = False

# Make low-count cells more visible by compressing the color scale.
USE_ENHANCED_CONTRAST = True
# Options (only used when USE_ENHANCED_CONTRAST is True): "power", "log"
COLOR_SCALE = "power"
# Only used when COLOR_SCALE == "power". Lower gamma -> darker low counts.
POWER_GAMMA = 0.5

# Order of subcategories on both axes (least -> most severe).
SEVERITY_ORDER = [
    "exaggeration",
    "casual oversimplification",
    "doubt",
    "bandwagon",
    "slogans",
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


def load_target_titles() -> set[str]:
    df = pd.read_csv(TWELVE_ARTICLE_CSV)
    return {normalize_title(t) for t in df["Headline"].tolist()}


def iter_mturk_full_overall_annotations(payload: dict) -> Iterable[dict]:
    """
    Yield raw span annotations from the MTurk FULL OVERALL export.
    """
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


def build_human_annotations_by_unit(
    mturk_payload: dict,
    *,
    target_titles: set[str],
) -> Dict[Tuple[str, int], List[dict]]:
    by_unit: Dict[Tuple[str, int], List[dict]] = defaultdict(list)
    for ann in iter_mturk_full_overall_annotations(mturk_payload):
        title = ann.get("title")
        pidx = ann.get("paragraphIndex")
        if not title or not isinstance(pidx, int):
            continue
        if normalize_title(title) not in target_titles:
            continue
        by_unit[(normalize_title(title), pidx)].append(ann)
    return by_unit


def build_llm_annotations_by_unit(per_model_payload: list) -> Dict[Tuple[str, int], List[dict]]:
    """
    Keep ALL annotations from A, B, and C (no consolidation).
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
    return by_unit


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
    matrix = np.array([[confusion[true].get(pred, 0) for pred in labels] for true in labels], dtype=float)

    plt.style.use("seaborn-v0_8-colorblind")
    fig_w = max(10, 1.05 * n)
    fig_h = max(8, 0.95 * n)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    cmap = plt.get_cmap("Blues").copy()
    vmax = float(matrix.max()) if matrix.size else 0.0

    if not USE_ENHANCED_CONTRAST:
        im = ax.imshow(matrix, cmap=cmap)
        cbar_label = "Count"
    elif COLOR_SCALE == "log":
        # Log scaling improves visibility of small counts, but cannot handle zeros.
        # Mask zeros so they remain white.
        masked = np.ma.masked_where(matrix <= 0, matrix)
        cmap.set_bad(color="white")
        norm = colors.LogNorm(vmin=1, vmax=max(1.0, float(masked.max()) if masked.count() else 1.0))
        im = ax.imshow(masked, cmap=cmap, norm=norm)
        cbar_label = "Count (log scale)"
    else:
        # Default enhanced contrast mode: power-law scaling that still renders zeros.
        norm = colors.PowerNorm(gamma=POWER_GAMMA, vmin=0.0, vmax=max(1.0, vmax))
        im = ax.imshow(matrix, cmap=cmap, norm=norm)
        cbar_label = f"Count (power, gamma={POWER_GAMMA})"

    cbar = ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(cbar_label)

    # subtitle = f"Paragraph-indexed spans n={unit_count}"
    '''
    if not INCLUDE_NPL_IN_MATRIX:
        subtitle += " (excluding NPL)"
    '''
    ax.set_title(
        "LLM vs MTurk Full Subcategory Confusion Matrix\n",
        pad=18, weight = 'bold'
    )

    tick_labels = [display_label(l) for l in labels]
    ax.set_xticks(range(n), tick_labels, rotation=45, ha="right")
    ax.set_yticks(range(n), tick_labels)
    ax.set_xlabel("LLM (predicted subcategory)", fontweight="bold")
    ax.set_ylabel("MTurk (true subcategory)", fontweight="bold")

    threshold = 0.55
    for i in range(n):
        for j in range(n):
            val = float(matrix[i, j])
            if USE_ENHANCED_CONTRAST and COLOR_SCALE == "log" and val <= 0:
                intensity = 0.0
            else:
                intensity = float(im.norm(val)) if getattr(im, "norm", None) is not None else (val / vmax if vmax else 0.0)
            color = "white" if intensity > threshold else "black"
            ax.text(j, i, str(int(val)), ha="center", va="center", color=color, fontsize=10)

    fig.tight_layout()
    fig.savefig(OUTPUT_IMG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved confusion matrix to {OUTPUT_IMG}")


def main() -> None:
    target_titles = load_target_titles()
    mturk_payload = load_json(MTURK_FULL_OVERALL_PATH)
    llm_payload = load_json(PER_MODEL_LLM_PATH)

    human_by_unit = build_human_annotations_by_unit(mturk_payload, target_titles=target_titles)
    llm_by_unit = build_llm_annotations_by_unit(llm_payload)

    confusion: Dict[str, Counter] = defaultdict(Counter)
    true_counts = Counter()
    pred_counts = Counter()

    used_paragraphs = 0
    used_pairs = 0
    skipped_no_llm = 0

    for unit, human_anns in human_by_unit.items():
        llm_anns = llm_by_unit.get(unit)
        if not llm_anns:
            skipped_no_llm += 1
            continue

        human_labels = [
            canonicalize_subcategory(a.get("subcategory"), is_npl=is_no_polarizing(a))
            for a in human_anns
            if isinstance(a, dict)
        ]
        llm_labels = [
            canonicalize_subcategory(a.get("subcategory"), is_npl=is_no_polarizing(a))
            for a in llm_anns
            if isinstance(a, dict)
        ]

        if not INCLUDE_NPL_IN_MATRIX:
            human_labels = [l for l in human_labels if l != NPL_NORMALIZED]
            llm_labels = [l for l in llm_labels if l != NPL_NORMALIZED]

        if not human_labels or not llm_labels:
            continue

        used_paragraphs += 1
        for t in human_labels:
            for p in llm_labels:
                confusion[t][p] += 1
                true_counts[t] += 1
                pred_counts[p] += 1
                used_pairs += 1

    base_labels: List[str] = []
    if INCLUDE_NPL_IN_MATRIX:
        base_labels.append(NPL_NORMALIZED)
    base_labels.extend(SEVERITY_ORDER)

    observed_labels = sorted(set(true_counts.keys()) | set(pred_counts.keys()))
    extras = [l for l in observed_labels if l not in base_labels]
    labels = base_labels + extras

    print("Full overall (no consolidation) confusion matrix inputs")
    print("-------------------------------------------------------")
    print(f"MTURK_FULL_OVERALL_PATH: {MTURK_FULL_OVERALL_PATH}")
    print(f"PER_MODEL_LLM_PATH:      {PER_MODEL_LLM_PATH}")
    print(f"Target titles (12-article set): {len(target_titles)}")
    print(f"Human paragraph keys: {len(human_by_unit)}")
    print(f"LLM paragraph keys:   {len(llm_by_unit)}")
    print(f"Paragraphs used (after filtering): {used_paragraphs}")
    print(f"Annotation pairs counted: {used_pairs}")
    print(f"Skipped (no LLM paragraph): {skipped_no_llm}")
    print(f"True label counts (pairs): {dict(true_counts)}")
    print(f"Pred label counts (pairs): {dict(pred_counts)}")
    if extras:
        print(f"Extra labels (appended at end): {extras}")

    plot_confusion_matrix(confusion, labels, used_pairs)


if __name__ == "__main__":
    main()
