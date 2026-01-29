import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ------------------------
# Configure Matplotlib cache directory
# ------------------------
# On some systems (including restricted build environments), ~/.matplotlib may not be
# writable. Setting MPLCONFIGDIR avoids runtime warnings and speeds up imports.
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
OUTPUT_IMG = OUTPUT_DIR / "confusion_matrix_llm_vs_gold_subcategory.png"


# ------------------------
# Label ordering (least -> most severe)
# ------------------------
INCLUDE_NPL_IN_MATRIX = True

SEVERITY_ORDER = [
    "exaggeration",
    "casual oversimplification",
    "doubt",
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


def build_confusion_counts() -> Tuple[Dict[str, Counter], Counter, Counter, int]:
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

    confusion: Dict[str, Counter] = defaultdict(Counter)  # true -> pred -> count
    true_counts = Counter()
    pred_counts = Counter()
    unit_count = 0

    for norm_title in shared_norm_titles:
        llm_title = llm_norm_to_title[norm_title]
        gold_title = gold_norm_to_title[norm_title]

        llm_by_p = group_by_paragraph_index(llm_map[llm_title])
        gold_by_p = group_by_paragraph_index(gold_map[gold_title])

        for pidx in sorted(set(llm_by_p.keys()) | set(gold_by_p.keys())):
            if pidx not in llm_by_p or pidx not in gold_by_p:
                # Confusion matrices require aligned units; skip mismatched paragraphs.
                continue

            llm_ann = pick_best_llm_annotation(llm_by_p[pidx])
            gold_ann = pick_best_gold_annotation(gold_by_p[pidx])

            pred = canonicalize_subcategory(llm_ann.get("subcategory"), is_npl=is_no_polarizing(llm_ann))
            true = canonicalize_subcategory(gold_ann.get("subcategory"), is_npl=is_no_polarizing(gold_ann))

            confusion[true][pred] += 1
            true_counts[true] += 1
            pred_counts[pred] += 1
            unit_count += 1

    return confusion, true_counts, pred_counts, unit_count


def display_label(label: str) -> str:
    if label == NPL_NORMALIZED:
        return NPL_DISPLAY
    # Title-case but preserve hyphenated forms.
    return " ".join([part.capitalize() for part in label.split(" ")])


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

    ax.set_title(f"LLM vs Gold Confusion Matrix (Subcategory)\n(n={unit_count} paragraphs)", pad=18)

    tick_labels = [display_label(l) for l in labels]
    ax.set_xticks(range(n), tick_labels, rotation=45, ha="right")
    ax.set_yticks(range(n), tick_labels)
    ax.set_xlabel("LLM (predicted subcategory)", fontweight="bold")
    ax.set_ylabel("Gold (true subcategory)", fontweight="bold")

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
    confusion, true_counts, pred_counts, unit_count = build_confusion_counts()

    base_labels: List[str] = []
    if INCLUDE_NPL_IN_MATRIX:
        base_labels.append(NPL_NORMALIZED)
    base_labels.extend(SEVERITY_ORDER)

    observed_labels = sorted(set(true_counts.keys()) | set(pred_counts.keys()))
    extras = [l for l in observed_labels if l not in base_labels]
    labels = base_labels + extras

    print("Subcategory confusion matrix inputs")
    print("----------------------------------")
    print(f"LLM_PATH:  {LLM_PATH}")
    print(f"GOLD_PATH: {GOLD_PATH}")
    print(f"Shared paragraph units used: {unit_count}")
    print(f"Gold label counts: {dict(true_counts)}")
    print(f"LLM label counts:  {dict(pred_counts)}")
    if extras:
        print(f"Extra labels (appended at end): {extras}")

    plot_confusion_matrix(confusion, labels, unit_count)


if __name__ == "__main__":
    main()
