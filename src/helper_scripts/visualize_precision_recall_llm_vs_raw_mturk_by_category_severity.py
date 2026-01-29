import json
import os
import re
from collections import Counter, defaultdict
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
MTURK_RAW_PATH = BASE_DIR / "mturk_results/archived_mturk_results/1-8/1-8HIT.json"
LLM_PATH = BASE_DIR / "llm_annotation_results/archived_llm_annotations/paragraph_final_annotations_3annotators.json"
OUTPUT_IMG = OUTPUT_DIR / "precision_recall_llm_vs_raw_mturk_by_category_severity.png"


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

# Within-category severity ordering (least -> most severe).
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

SEVERITY_RANK = {label: idx for idx, label in enumerate(GLOBAL_SEVERITY_ORDER)}


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


def build_llm_paragraph_labels(llm_payload) -> Dict[Tuple[str, int], str]:
    labels: Dict[Tuple[str, int], str] = {}

    for article in llm_payload:
        title_norm = normalize_title(article.get("title", ""))
        by_para: Dict[int, List[dict]] = defaultdict(list)
        for ann in article.get("annotations", []):
            pidx = ann.get("paragraphIndex")
            if isinstance(pidx, int):
                by_para[pidx].append(ann)

        for pidx, anns in by_para.items():
            labels[(title_norm, pidx)] = condense_subcategory_most_frequent_tiebreak_severity(anns)

    return labels


def build_worker_paragraph_groups(mturk_payload) -> Dict[Tuple[str, str, int], List[dict]]:
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


def derive_category_from_subcategory(subcategory: str) -> str:
    if subcategory == NPL_NORMALIZED:
        return "No Polarizing Language"
    if subcategory in PERSUASIVE_SUBCATEGORIES:
        return "Persuasive Propaganda"
    if subcategory in INFLAMMATORY_SUBCATEGORIES:
        return "Inflammatory Language"
    return "unknown"


def precision_recall_for_threshold(
    pairs: List[Tuple[str, str]],
    *,
    target_category: str,
    included_subcategories: Set[str],
) -> Tuple[float, float, int, int, int]:
    tp = fp = fn = 0

    for true_subcat, pred_subcat in pairs:
        true_cat = derive_category_from_subcategory(true_subcat)
        pred_cat = derive_category_from_subcategory(pred_subcat)

        gold_pos = (true_cat == target_category) and (true_subcat in included_subcategories)
        pred_pos = (pred_cat == target_category) and (pred_subcat in included_subcategories)

        if pred_pos and gold_pos:
            tp += 1
        elif pred_pos and not gold_pos:
            fp += 1
        elif not pred_pos and gold_pos:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return precision, recall, tp, fp, fn


def display_subcategory(label: str) -> str:
    if label == NPL_NORMALIZED:
        return NPL_DISPLAY
    out = []
    for token in label.split(" "):
        if "-" in token:
            out.append("-".join([part.capitalize() for part in token.split("-")]))
        else:
            out.append(token.capitalize())
    return " ".join(out)


def plot_precision_recall_curves(pairs: List[Tuple[str, str]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)

    plt.style.use("seaborn-v0_8-colorblind")
    fig, ax = plt.subplots(figsize=(10, 7))

    curves = [
        ("Persuasive Propaganda", PERSUASIVE_SUBCATEGORIES, "tab:blue"),
        ("Inflammatory Language", INFLAMMATORY_SUBCATEGORIES, "tab:red"),
    ]

    for category_name, ordered_subcats, color in curves:
        point_rows: List[Tuple[float, float, str]] = []

        # Sweep from most severe -> least severe within this category.
        for i in range(len(ordered_subcats) - 1, -1, -1):
            threshold = ordered_subcats[i]
            included = set(ordered_subcats[i:])

            precision, recall, tp, fp, fn = precision_recall_for_threshold(
                pairs,
                target_category=category_name,
                included_subcategories=included,
            )

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

        point_rows.sort(key=lambda item: item[0])
        recalls = [r for r, _, _ in point_rows]
        precisions = [p for _, p, _ in point_rows]

        ax.plot(recalls, precisions, marker="o", linewidth=2, color=color, label=category_name)

        for r, p, text in point_rows:
            ax.annotate(text, (r, p), textcoords="offset points", xytext=(6, 6), fontsize=8, color=color)

    ax.set_title("Precision-Recall by Category (Raw MTurk vs LLM)\nSeverity Threshold Sweep", pad=16)
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
    mturk_payload = load_json(MTURK_RAW_PATH)
    llm_payload = load_json(LLM_PATH)

    llm_labels = build_llm_paragraph_labels(llm_payload)
    worker_groups = build_worker_paragraph_groups(mturk_payload)

    pairs: List[Tuple[str, str]] = []
    skipped_missing_llm = 0

    for (_, title_norm, pidx), anns in worker_groups.items():
        true_subcat = condense_subcategory_most_frequent_tiebreak_severity(anns)
        pred_subcat = llm_labels.get((title_norm, pidx))
        if pred_subcat is None:
            skipped_missing_llm += 1
            continue
        pairs.append((true_subcat, pred_subcat))

    if not pairs:
        raise RuntimeError("No aligned worker-paragraph units found between raw MTurk and LLM files.")

    true_counts = Counter(true for true, _ in pairs)
    pred_counts = Counter(pred for _, pred in pairs)

    print("Precision-recall (raw MTurk pooled worker-paragraphs)")
    print("-----------------------------------------------------")
    print(f"MTURK_RAW_PATH: {MTURK_RAW_PATH}")
    print(f"LLM_PATH:       {LLM_PATH}")
    print(f"Worker-paragraph groups (with paragraphIndex): {len(worker_groups)}")
    print(f"Aligned units used: {len(pairs)}")
    print(f"Skipped (no matching LLM paragraphIndex for title): {skipped_missing_llm}")
    print(f"Raw worker label counts (aligned units): {dict(true_counts)}")
    print(f"LLM label counts (aligned units): {dict(pred_counts)}")

    plot_precision_recall_curves(pairs)


if __name__ == "__main__":
    main()
