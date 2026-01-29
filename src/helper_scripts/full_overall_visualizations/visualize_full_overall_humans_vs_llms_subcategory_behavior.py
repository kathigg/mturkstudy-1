import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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

# Raw MTurk export containing *all* annotations (not gold-standard aggregated)
# for the 1-20 HIT run.
MTURK_FULL_OVERALL_PATH = BASE_DIR / "mturk_results/1-20/1-20_FULL_OVERALL.json"

# Per-model LLM outputs (A/B/C, no adjudication).
PER_MODEL_LLM_PATH = BASE_DIR / "llm_annotation_results/per_model_annotations/per_model_annotations_3models.json"


# ------------------------
# Outputs
# ------------------------
OUTPUT_PNG = OUTPUT_DIR / "full_overall_humans_vs_llms_subcategory_behavior_heatmap.png"
OUTPUT_CSV = OUTPUT_DIR / "full_overall_humans_vs_llms_subcategory_behavior_counts.csv"


# ------------------------
# Visualization configuration
# ------------------------
# If True, plot per-source proportions (each column sums to 1).
# If False, plot raw counts.
NORMALIZE_PER_SOURCE = False

# If True, include NPL rows in the plot.
INCLUDE_NPL = True

# Order of subcategories on the y-axis (top -> bottom).
# (Matches the severity ordering you requested elsewhere.)
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
    Yield annotation dicts from the raw MTurk export.
    The payload is a dict of submission_id -> entry, where entry has:
      - articleTitles: [{id, title}, ...]
      - textAnnotations: {article_id: [annotation, ...], ...}
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
                # Repair title if missing
                if not ann.get("title"):
                    ann = dict(ann)
                    ann["title"] = title_map.get(str(article_id))
                yield ann


def collect_human_counts(mturk_payload: dict, *, target_titles: set[str]) -> Counter:
    counts = Counter()
    for ann in iter_mturk_full_overall_annotations(mturk_payload):
        title = ann.get("title")
        pidx = ann.get("paragraphIndex")
        if not title or not isinstance(pidx, int):
            continue
        if normalize_title(title) not in target_titles:
            continue
        label = canonicalize_subcategory(ann.get("subcategory"), is_npl=is_no_polarizing(ann))
        counts[label] += 1
    return counts


def collect_llm_counts(per_model_payload: list) -> Dict[str, Counter]:
    counts_by_model: Dict[str, Counter] = {
        "annotator_A": Counter(),
        "annotator_B": Counter(),
        "annotator_C": Counter(),
    }
    for row in per_model_payload:
        if not isinstance(row, dict):
            continue
        for model_key in list(counts_by_model.keys()):
            model_obj = row.get(model_key) or {}
            for ann in model_obj.get("annotations", []) or []:
                if not isinstance(ann, dict):
                    continue
                if not isinstance(ann.get("paragraphIndex"), int):
                    continue
                label = canonicalize_subcategory(ann.get("subcategory"), is_npl=is_no_polarizing(ann))
                counts_by_model[model_key][label] += 1
    return counts_by_model


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


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)

    target_titles = load_target_titles()
    mturk_payload = load_json(MTURK_FULL_OVERALL_PATH)
    llm_payload = load_json(PER_MODEL_LLM_PATH)

    human_counts = collect_human_counts(mturk_payload, target_titles=target_titles)
    llm_counts_by_model = collect_llm_counts(llm_payload)

    ordered_rows: List[str] = []
    if INCLUDE_NPL:
        ordered_rows.append(NPL_NORMALIZED)
    ordered_rows.extend(SEVERITY_ORDER)

    # Add any extras we observed in either dataset (e.g., "unspecified").
    observed = set(human_counts.keys())
    for c in llm_counts_by_model.values():
        observed |= set(c.keys())
    extras = sorted(observed - set(ordered_rows))
    rows = ordered_rows + extras

    columns = [
        "Human (MTurk 1-20 FULL)",
        "LLM Annotator A",
        "LLM Annotator B",
        "LLM Annotator C",
    ]

    df = pd.DataFrame(index=rows, columns=columns, data=0.0)
    df.loc[:, "Human (MTurk 1-20 FULL)"] = [human_counts.get(r, 0) for r in rows]
    df.loc[:, "LLM Annotator A"] = [llm_counts_by_model["annotator_A"].get(r, 0) for r in rows]
    df.loc[:, "LLM Annotator B"] = [llm_counts_by_model["annotator_B"].get(r, 0) for r in rows]
    df.loc[:, "LLM Annotator C"] = [llm_counts_by_model["annotator_C"].get(r, 0) for r in rows]

    # Save raw counts for analysis.
    df_out = df.copy()
    df_out.index = [display_label(i) for i in df_out.index]
    df_out.to_csv(OUTPUT_CSV, index=True)

    # Prepare plot values.
    plot_df = df.copy()
    if not INCLUDE_NPL:
        plot_df = plot_df.drop(index=[NPL_NORMALIZED], errors="ignore")
    if NORMALIZE_PER_SOURCE:
        col_sums = plot_df.sum(axis=0).replace(0, 1)
        plot_df = plot_df.div(col_sums, axis=1)

    plt.style.use("seaborn-v0_8-colorblind")

    n_rows = len(plot_df.index)
    n_cols = len(plot_df.columns)
    fig_w = max(10, 1.05 * n_cols + 6)
    fig_h = max(8, 0.65 * n_rows + 2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    im = ax.imshow(plot_df.values, cmap="Blues", aspect="auto")
    cbar = ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Proportion" if NORMALIZE_PER_SOURCE else "Count")

    ax.set_xticks(range(n_cols), plot_df.columns, rotation=45, ha="right")
    ax.set_yticks(range(n_rows), [display_label(i) for i in plot_df.index])

    subtitle_bits = [
        "12-article set",
        "paragraph-indexed spans",
        ("normalized per source" if NORMALIZE_PER_SOURCE else "raw counts"),
        ("including NPL" if INCLUDE_NPL else "excluding NPL"),
    ]
    ax.set_title(
        "Humans vs LLMs Subcategory Matrix\n(" + ", ".join(subtitle_bits) + ")",
        pad=18,
    )

    ax.set_xlabel("Source", fontweight="bold")
    ax.set_ylabel("Subcategory", fontweight="bold")

    # Annotate cells with values (match confusion-matrix style).
    vmax = float(plot_df.values.max()) if plot_df.size else 0.0
    threshold = vmax * 0.55
    for i in range(n_rows):
        for j in range(n_cols):
            val = float(plot_df.iat[i, j])
            if NORMALIZE_PER_SOURCE:
                txt = f"{val:.2f}"
            else:
                txt = str(int(val))
            color = "white" if val > threshold else "black"
            ax.text(j, i, txt, ha="center", va="center", fontsize=9, color=color)

    fig.tight_layout()
    fig.savefig(OUTPUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote heatmap: {OUTPUT_PNG}")
    print(f"Wrote counts CSV: {OUTPUT_CSV}")
    print("Counts summary:")
    print(f"  Human total (paragraph-indexed spans): {sum(human_counts.values())}")
    for k, c in llm_counts_by_model.items():
        print(f"  {k} total (paragraph-indexed annotations): {sum(c.values())}")


if __name__ == "__main__":
    main()
