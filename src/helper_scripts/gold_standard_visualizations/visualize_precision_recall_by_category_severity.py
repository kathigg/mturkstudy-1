import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


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
LLM_PATH = BASE_DIR / "llm_annotation_results/multi_llm_annotations/multi_final_annotations_3annotators.json"
GOLD_PATH = BASE_DIR / "mturk_results/1-20_hit_gold_standard_output.json"
OUTPUT_IMG = OUTPUT_DIR / "precision_recall_by_category_severity.png"


# ------------------------
# Severity ordering (least -> most severe)
# ------------------------
GLOBAL_SEVERITY_ORDER = [
    "exaggeration",
    "casual oversimplification",
    "doubt",
    "slogans",
    "bandwagon",
    "scapegoating",
    "name-calling",
    "demonization",
]

# We sweep thresholds from most severe -> least severe within each category.
PERSUASIVE_SUBCATEGORIES = [
    "exaggeration",
    "casual oversimplification",
    "doubt",
    "slogans",
    "bandwagon",
]
INFLAMMATORY_SUBCATEGORIES = [
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


def canonicalize_category(raw: Optional[str], *, is_npl: bool) -> str:
    if is_npl:
        return "No Polarizing Language"
    s = normalize_label(raw or "")
    if not s:
        return "unknown"
    return " ".join([part.capitalize() for part in s.split(" ")])


def group_by_paragraph_index(annotations: List[dict]) -> Dict[int, List[dict]]:
    by_para: Dict[int, List[dict]] = defaultdict(list)
    for ann in annotations:
        pidx = ann.get("paragraphIndex")
        if isinstance(pidx, int):
            by_para[pidx].append(ann)
    return by_para


def pick_best_llm_annotation(items: List[dict]) -> dict:
    # Prefer a polarizing annotation if present; otherwise keep an NPL placeholder.
    polarizing = [a for a in items if not is_no_polarizing(a)]
    candidates = polarizing if polarizing else items
    # Prefer longer spans as a proxy for specificity; keep stable ordering on ties.
    return max(enumerate(candidates), key=lambda item: (len(str(item[1].get("text", ""))), -item[0]))[1]


def pick_best_gold_annotation(items: List[dict]) -> dict:
    # Mirror paragraph_llm_human_comparison.py tie-breaking:
    # max supporters, then prefer NPL if tied, then confidence, then longer span.
    max_support = max(int(a.get("num_supporters") or 0) for a in items)
    tied = [a for a in items if int(a.get("num_supporters") or 0) == max_support]
    npl = [a for a in tied if is_no_polarizing(a)]
    candidates = npl if npl else tied
    return max(
        enumerate(candidates),
        key=lambda item: (
            float(item[1].get("confidence") or 0.0),
            len(str(item[1].get("text", ""))),
            -item[0],
        ),
    )[1]


@dataclass(frozen=True)
class UnitLabel:
    category: str
    subcategory: str


def load_aligned_paragraph_labels() -> List[Tuple[UnitLabel, UnitLabel]]:
    """
    Return a list of (gold_label, llm_label) pairs at the paragraph level.

    This mirrors the paragraph comparison assumptions:
    - Choose a single \"best\" annotation per paragraph on each side.
    - Skip paragraphs that don't exist in both datasets for a shared title.
    """
    llm_payload = load_json(LLM_PATH)
    gold_payload = load_json(GOLD_PATH)

    llm_map: Dict[str, List[dict]] = defaultdict(list)
    for article in llm_payload:
        title = article.get("title", "UNKNOWN_TITLE")
        for ann in article.get("annotations", []):
            llm_map[title].append(ann)

    gold_map: Dict[str, List[dict]] = defaultdict(list)
    for article in gold_payload:
        title = article.get("title", "UNKNOWN_TITLE")
        for ann in article.get("annotations", []):
            gold_map[title].append(ann)

    llm_norm_to_title = {normalize_title(t): t for t in llm_map.keys()}
    gold_norm_to_title = {normalize_title(t): t for t in gold_map.keys()}
    shared_norm_titles = sorted(set(llm_norm_to_title.keys()) & set(gold_norm_to_title.keys()))

    pairs: List[Tuple[UnitLabel, UnitLabel]] = []
    for norm_title in shared_norm_titles:
        llm_title = llm_norm_to_title[norm_title]
        gold_title = gold_norm_to_title[norm_title]

        llm_by_p = group_by_paragraph_index(llm_map[llm_title])
        gold_by_p = group_by_paragraph_index(gold_map[gold_title])

        for pidx in sorted(set(llm_by_p.keys()) | set(gold_by_p.keys())):
            if pidx not in llm_by_p or pidx not in gold_by_p:
                continue

            llm_ann = pick_best_llm_annotation(llm_by_p[pidx])
            gold_ann = pick_best_gold_annotation(gold_by_p[pidx])

            llm_is_npl = is_no_polarizing(llm_ann)
            gold_is_npl = is_no_polarizing(gold_ann)

            llm_label = UnitLabel(
                category=canonicalize_category(llm_ann.get("category"), is_npl=llm_is_npl),
                subcategory=canonicalize_subcategory(llm_ann.get("subcategory"), is_npl=llm_is_npl),
            )
            gold_label = UnitLabel(
                category=canonicalize_category(gold_ann.get("category"), is_npl=gold_is_npl),
                subcategory=canonicalize_subcategory(gold_ann.get("subcategory"), is_npl=gold_is_npl),
            )
            pairs.append((gold_label, llm_label))

    return pairs


def display_subcategory(label: str) -> str:
    if label == NPL_NORMALIZED:
        return NPL_DISPLAY
    return " ".join([part.capitalize() for part in label.split(" ")])


def precision_recall_for_threshold(
    pairs: List[Tuple[UnitLabel, UnitLabel]],
    *,
    target_category: str,
    included_subcategories: Set[str],
) -> Tuple[float, float, int, int, int]:
    tp = fp = fn = 0

    for gold, pred in pairs:
        gold_pos = (gold.category == target_category) and (gold.subcategory in included_subcategories)
        pred_pos = (pred.category == target_category) and (pred.subcategory in included_subcategories)

        if pred_pos and gold_pos:
            tp += 1
        elif pred_pos and not gold_pos:
            fp += 1
        elif not pred_pos and gold_pos:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return precision, recall, tp, fp, fn


def plot_precision_recall_curves(pairs: List[Tuple[UnitLabel, UnitLabel]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)

    plt.style.use("seaborn-v0_8-colorblind")
    fig, ax = plt.subplots(figsize=(10, 7))

    curves = [
        ("Persuasive Propaganda", PERSUASIVE_SUBCATEGORIES, "tab:blue"),
        ("Inflammatory Language", INFLAMMATORY_SUBCATEGORIES, "tab:red"),
    ]

    for category_name, ordered_subcats, color in curves:
        # Sweep from most severe -> least severe within this category.
        point_rows: List[Tuple[float, float, str]] = []
        for i in range(len(ordered_subcats) - 1, -1, -1):
            threshold = ordered_subcats[i]
            included = set(ordered_subcats[i:])

            precision, recall, tp, fp, fn = precision_recall_for_threshold(
                pairs,
                target_category=category_name,
                included_subcategories=included,
            )

            # If there are zero positives in gold at this threshold, recall is ill-defined (0/0).
            # Skip those points so the plotted curve reflects actual evaluable settings.
            gold_positive = tp + fn
            if gold_positive == 0:
                continue

            point_rows.append(
                (
                    recall,
                    precision,
                    f">= {display_subcategory(threshold)}\nTP={tp} FP={fp} FN={fn}",
                )
            )

        if not point_rows:
            continue

        # Sort by recall so it looks like a standard PR curve.
        point_rows.sort(key=lambda item: item[0])
        recalls = [r for r, _, _ in point_rows]
        precisions = [p for _, p, _ in point_rows]

        ax.plot(recalls, precisions, marker="o", linewidth=2, color=color, label=category_name)

        # Annotate points (sparse, but this dataset is small).
        for r, p, text in point_rows:
            ax.annotate(text, (r, p), textcoords="offset points", xytext=(6, 6), fontsize=8, color=color)

    ax.set_title("Precision-Recall by Category (Severity Threshold Sweep)", pad=16)
    ax.set_xlabel("Recall", fontweight="bold")
    ax.set_ylabel("Precision", fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(True, linewidth=0.5, alpha=0.4)
    ax.legend(loc="lower left")

    fig.tight_layout()
    fig.savefig(OUTPUT_IMG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved precision-recall curves to {OUTPUT_IMG}")


def main() -> None:
    pairs = load_aligned_paragraph_labels()
    if not pairs:
        raise RuntimeError("No aligned paragraph units found between LLM and gold files.")

    gold_subcats = Counter(g.subcategory for g, _ in pairs)
    pred_subcats = Counter(p.subcategory for _, p in pairs)

    print("Precision-recall curve inputs")
    print("-----------------------------")
    print(f"LLM_PATH:  {LLM_PATH}")
    print(f"GOLD_PATH: {GOLD_PATH}")
    print(f"Aligned paragraph units used: {len(pairs)}")
    print(f"Gold subcategory counts: {dict(gold_subcats)}")
    print(f"LLM subcategory counts:  {dict(pred_subcats)}")

    plot_precision_recall_curves(pairs)


if __name__ == "__main__":
    main()
