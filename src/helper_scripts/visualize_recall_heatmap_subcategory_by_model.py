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
PER_MODEL_LLM_PATH = BASE_DIR / "llm_annotation_results/per_model_annotations/per_model_annotations_3models.json"
GOLD_PATH = BASE_DIR / "mturk_results/1-20_hit_gold_standard_output.json"
OUTPUT_IMG = OUTPUT_DIR / "recall_heatmap_subcategory_by_model.png"


# ------------------------
# Metric configuration
# ------------------------
# Use subcategory-level recall by default.
LABEL_LEVEL = "subcategory"  # "subcategory" | "category"

# Requested severity ordering (least -> most severe).
LABEL_ORDER = [
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


def label_for_annotation(ann: dict) -> str:
    npl = is_no_polarizing(ann)
    if LABEL_LEVEL == "category":
        return canonicalize_category(ann.get("category"), is_npl=npl)
    return canonicalize_subcategory(ann.get("subcategory"), is_npl=npl)


def collect_gold_labels_by_paragraph(gold_payload) -> Dict[Tuple[str, int], Set[str]]:
    """
    Return {(normalized_title, paragraphIndex): set(true_labels)}.

    If the gold file has multiple annotations for a paragraph, we keep all labels (excluding NPL).
    """
    gold: Dict[Tuple[str, int], Set[str]] = defaultdict(set)
    for article in gold_payload:
        if not isinstance(article, dict):
            continue
        title_norm = normalize_title(article.get("title", ""))
        for ann in article.get("annotations", []) or []:
            if not isinstance(ann, dict):
                continue
            pidx = ann.get("paragraphIndex")
            if not isinstance(pidx, int):
                continue
            label = label_for_annotation(ann)
            if label == NPL_NORMALIZED:
                continue
            gold[(title_norm, pidx)].add(label)
    return gold


def collect_model_labels_by_paragraph(per_model_payload) -> Dict[str, Dict[Tuple[str, int], Set[str]]]:
    """
    Return {model_key: {(normalized_title, paragraphIndex): set(pred_labels)}}.

    model_key in {"annotator_A", "annotator_B", "annotator_C"}.
    """
    per_model: Dict[str, Dict[Tuple[str, int], Set[str]]] = {
        "annotator_A": defaultdict(set),
        "annotator_B": defaultdict(set),
        "annotator_C": defaultdict(set),
    }

    for row in per_model_payload:
        if not isinstance(row, dict):
            continue
        title_norm = normalize_title(row.get("title", ""))
        for model_key in list(per_model.keys()):
            model_obj = row.get(model_key) or {}
            for ann in model_obj.get("annotations", []) or []:
                if not isinstance(ann, dict):
                    continue
                pidx = ann.get("paragraphIndex")
                if not isinstance(pidx, int):
                    continue
                label = label_for_annotation(ann)
                if label == NPL_NORMALIZED:
                    continue
                per_model[model_key][(title_norm, pidx)].add(label)
    return per_model


def compute_recall_matrix(
    gold: Dict[Tuple[str, int], Set[str]],
    preds: Dict[str, Dict[Tuple[str, int], Set[str]]],
    *,
    labels: List[str],
    model_keys: List[str],
) -> Tuple[List[List[float]], Dict[str, int], Dict[str, Dict[str, Tuple[int, int]]]]:
    """
    Recall(label, model) = TP / (TP + FN) over (paragraph, label) instances.

    Returns:
    - matrix[row_label][col_model] -> recall in [0,1]
    - support[label] -> number of gold-positive instances for that label
    - details[label][model] -> (tp, fn)
    """
    support = Counter()
    details: Dict[str, Dict[str, Tuple[int, int]]] = {lab: {} for lab in labels}

    # Count gold positives per label (paragraph-label instances).
    for true_labels in gold.values():
        for lab in true_labels:
            if lab in labels:
                support[lab] += 1

    matrix: List[List[float]] = []
    for lab in labels:
        row: List[float] = []
        for model in model_keys:
            tp = 0
            fn = 0
            pred_map = preds[model]

            for unit, true_labels in gold.items():
                if lab not in true_labels:
                    continue
                pred_labels = pred_map.get(unit, set())
                if lab in pred_labels:
                    tp += 1
                else:
                    fn += 1

            recall = tp / (tp + fn) if (tp + fn) else 0.0
            details[lab][model] = (tp, fn)
            row.append(recall)
        matrix.append(row)

    return matrix, dict(support), details


def display_label(label: str) -> str:
    if label == NPL_NORMALIZED:
        return "NPL"
    parts = []
    for token in label.split(" "):
        if "-" in token:
            parts.append("-".join([p.capitalize() for p in token.split("-")]))
        else:
            parts.append(token.capitalize())
    return " ".join(parts)


def plot_heatmap(matrix: List[List[float]], row_labels: List[str], col_labels: List[str], support: Dict[str, int]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)

    n_rows = len(row_labels)
    n_cols = len(col_labels)

    plt.style.use("seaborn-v0_8-colorblind")
    fig_w = max(8.5, 1.4 * n_cols + 3)
    fig_h = max(6.0, 0.6 * n_rows + 2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    im = ax.imshow(matrix, cmap="Blues", vmin=0.0, vmax=1.0, aspect="auto")
    ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Recall")

    ytick = [f"{display_label(lab)} (n={support.get(lab, 0)})" for lab in row_labels]
    ax.set_yticks(range(n_rows), ytick)
    ax.set_xticks(range(n_cols), col_labels, rotation=0)

    ax.set_title("Category x Model Recall (Gold vs Per-Model LLM)", pad=16)
    ax.set_xlabel("Model", fontweight="bold")
    ax.set_ylabel("Gold label (support)", fontweight="bold")

    for i in range(n_rows):
        for j in range(n_cols):
            val = matrix[i][j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=10, color="black")

    fig.tight_layout()
    fig.savefig(OUTPUT_IMG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved recall heatmap to {OUTPUT_IMG}")


def main() -> None:
    gold_payload = load_json(GOLD_PATH)
    per_model_payload = load_json(PER_MODEL_LLM_PATH)

    gold = collect_gold_labels_by_paragraph(gold_payload)
    preds = collect_model_labels_by_paragraph(per_model_payload)

    # Only keep labels with support > 0, unless you want to see 0-support rows.
    ordered = [lab for lab in LABEL_ORDER if lab in {l for s in gold.values() for l in s}]
    extras = sorted({l for s in gold.values() for l in s} - set(ordered))
    labels = ordered + extras

    model_keys = ["annotator_A", "annotator_B", "annotator_C"]
    model_labels = ["Annotator A", "Annotator B", "Annotator C"]

    matrix, support, _details = compute_recall_matrix(gold, preds, labels=labels, model_keys=model_keys)

    aligned_units = len({k for k in gold.keys() if k in set().union(*[set(m.keys()) for m in preds.values()])})
    print("Recall heatmap inputs")
    print("---------------------")
    print(f"PER_MODEL_LLM_PATH: {PER_MODEL_LLM_PATH}")
    print(f"GOLD_PATH:          {GOLD_PATH}")
    print(f"Gold paragraph units with any polarizing label: {len(gold)}")
    print(f"Gold labels (rows): {labels}")
    print(f"Aligned units (gold unit present in at least one model map): {aligned_units}")

    plot_heatmap(matrix, labels, model_labels, support)


if __name__ == "__main__":
    main()

