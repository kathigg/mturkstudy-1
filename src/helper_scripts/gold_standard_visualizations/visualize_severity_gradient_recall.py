import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ------------------------
# Configure Matplotlib cache directory
# ------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # .../src
OUTPUT_DIR = BASE_DIR / "data_visualizations"
MPLCONFIGDIR = OUTPUT_DIR / ".mplconfig"
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))

import matplotlib.pyplot as plt  # noqa: E402


# ------------------------
# Inputs / Outputs
# ------------------------
PER_MODEL_LLM_PATH = BASE_DIR / "llm_annotation_results/per_model_annotations/per_model_annotations_3models.json"
GOLD_PATH = BASE_DIR / "mturk_results/1-20_hit_gold_standard_output.json"

OUTPUT_IMG = OUTPUT_DIR / "severity_gradient_recall.png"


# ------------------------
# Plot configuration
# ------------------------
# Which model from the per-model file to visualize.
# Valid: "annotator_A", "annotator_B", "annotator_C"
MODEL_KEY = "annotator_A"

# Order on x-axis (left -> right). Use the exact order you want shown.
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


def label_for_annotation(ann: dict) -> str:
    return canonicalize_subcategory(ann.get("subcategory"), is_npl=is_no_polarizing(ann))


def collect_gold_labels_by_paragraph(gold_payload) -> Dict[Tuple[str, int], Set[str]]:
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


def collect_model_labels_by_paragraph(per_model_payload, model_key: str) -> Dict[Tuple[str, int], Set[str]]:
    preds: Dict[Tuple[str, int], Set[str]] = defaultdict(set)
    for row in per_model_payload:
        if not isinstance(row, dict):
            continue
        title_norm = normalize_title(row.get("title", ""))
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
            preds[(title_norm, pidx)].add(label)
    return preds


def compute_recall_by_label(
    gold: Dict[Tuple[str, int], Set[str]],
    preds: Dict[Tuple[str, int], Set[str]],
    *,
    labels: List[str],
) -> Tuple[Dict[str, float], Dict[str, int], Dict[str, Tuple[int, int]]]:
    """
    Recall(label) = TP / (TP + FN) over (paragraph, label) instances.
    """
    recall: Dict[str, float] = {}
    support: Dict[str, int] = {}
    details: Dict[str, Tuple[int, int]] = {}

    for lab in labels:
        tp = 0
        fn = 0
        for unit, true_labels in gold.items():
            if lab not in true_labels:
                continue
            pred_labels = preds.get(unit, set())
            if lab in pred_labels:
                tp += 1
            else:
                fn += 1
        total = tp + fn
        recall[lab] = (tp / total) if total else 0.0
        support[lab] = total
        details[lab] = (tp, fn)

    return recall, support, details


def short_label(label: str) -> str:
    # Compact x-axis labels (similar spirit to the example figure).
    mapping = {
        "doubt": "Doubt",
        "exaggeration": "Exag",
        "casual oversimplification": "Casual",
        "slogans": "Slog",
        "bandwagon": "Band",
        "scapegoating": "Scap",
        "name-calling": "Name",
        "demonization": "Demon",
    }
    return mapping.get(label, label[:6].title())


def plot_severity_gradient(
    recall_by_label: Dict[str, float],
    support: Dict[str, int],
    *,
    labels: List[str],
    model_key: str,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)

    xs = list(range(len(labels)))
    ys = [recall_by_label.get(lab, 0.0) for lab in labels]

    plt.style.use("seaborn-v0_8-colorblind")
    fig, ax = plt.subplots(figsize=(11, 5.5))

    # Step-like line with points (matches the \"severity gradient\" feel).
    ax.step(xs, ys, where="mid", linewidth=2, color="#2f2f2f")
    ax.scatter(xs, ys, s=90, color="#2f2f2f", zorder=3)

    # Support annotations above points (small dataset; helps interpret recall).
    for x, lab, y in zip(xs, labels, ys):
        n = support.get(lab, 0)
        ax.annotate(f"n={n}", (x, y), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=9)

    ax.set_xticks(xs, [short_label(l) for l in labels])
    ax.set_ylim(-0.05, 1.05)
    ax.set_yticks([i / 10 for i in range(0, 11, 2)])

    ax.set_title(f"Recall by Category Severity ({model_key})", pad=14)
    ax.set_xlabel("Subcategory (ordered by severity)", fontweight="bold")
    ax.set_ylabel("Recall", fontweight="bold")

    # Visual guide arrow (left -> right).
    ax.annotate(
        "Lower severity  →  Higher severity",
        xy=(0.5, -0.18),
        xycoords="axes fraction",
        ha="center",
        va="center",
        fontsize=10,
    )

    ax.grid(True, axis="y", linewidth=0.6, alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUTPUT_IMG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved severity gradient plot to {OUTPUT_IMG}")


def main() -> None:
    gold_payload = load_json(GOLD_PATH)
    per_model_payload = load_json(PER_MODEL_LLM_PATH)

    gold = collect_gold_labels_by_paragraph(gold_payload)
    preds = collect_model_labels_by_paragraph(per_model_payload, MODEL_KEY)

    recall_by_label, support, _details = compute_recall_by_label(gold, preds, labels=SEVERITY_ORDER)

    print("Severity gradient inputs")
    print("------------------------")
    print(f"PER_MODEL_LLM_PATH: {PER_MODEL_LLM_PATH}")
    print(f"GOLD_PATH:          {GOLD_PATH}")
    print(f"MODEL_KEY:          {MODEL_KEY}")
    print(f"Gold paragraph units with any polarizing label: {len(gold)}")
    print(f"Labels (x-axis): {SEVERITY_ORDER}")
    print("Recall by label:")
    for lab in SEVERITY_ORDER:
        print(f"  {lab}: recall={recall_by_label.get(lab, 0.0):.3f} (n={support.get(lab, 0)})")

    plot_severity_gradient(recall_by_label, support, labels=SEVERITY_ORDER, model_key=MODEL_KEY)


if __name__ == "__main__":
    main()

