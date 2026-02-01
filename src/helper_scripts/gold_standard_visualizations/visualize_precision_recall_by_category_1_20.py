"""
Per-category precision/recall figure (1–20 HIT gold standard).

Goal
----
Paper-ready visualization of end-to-end extraction performance by *category*.

Why this figure?
---------------
Overall F1 can be dominated by "No Polarizing Language" (NPL). This grouped
bar chart makes per-category precision/recall explicit, while still showing
support (gold frequency) per category.

Metric definition (end-to-end)
------------------------------
We treat each annotation span as an item in a span-matching evaluation:
- A predicted span is a true positive for category C iff it matches a gold span
  (same title + paragraphIndex + overlap) and the gold category is also C.
- Predicted spans of category C that do not match a gold span, or match a gold
  span of a different category, are false positives for C.
- Gold spans of category C that are unmatched, or matched to a prediction of a
  different category, are false negatives for C.

This matches the intended "did we find the gold polarizing label?" notion of
recall and avoids the conditional-on-span-match inflation seen in some per-class
reports.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# ------------------------
# Configure Matplotlib cache directory
# ------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # .../src
OUTPUT_DIR = BASE_DIR / "data_visualizations"
MPLCONFIGDIR = OUTPUT_DIR / ".mplconfig"
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


# ------------------------
# Inputs (1–20 gold standard)
# ------------------------
LLM_PATH = BASE_DIR / "llm_annotation_results/multi_llm_annotations/multi_final_annotations_3annotators.json"
GOLD_PATH = BASE_DIR / "mturk_results/1-20_hit_gold_standard_output.json"


# ------------------------
# Output
# ------------------------
OUTPUT_IMG = OUTPUT_DIR / "precision_recall_by_category_1_20_gold_standard.png"
OUTPUT_CSV = OUTPUT_DIR / "precision_recall_by_category_1_20_gold_standard.csv"


# ------------------------
# Plot configuration
# ------------------------
INCLUDE_NPL = True
CATEGORY_ORDER = [
    "persuasive propaganda",
    "inflammatory language",
    "no polarizing language",
]


# ------------------------
# Span matching (mirror paragraph_llm_human_comparison.py)
# ------------------------
STOP_WORDS = {
    "i",
    "me",
    "my",
    "myself",
    "we",
    "our",
    "ours",
    "ourselves",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "he",
    "him",
    "his",
    "himself",
    "she",
    "her",
    "hers",
    "herself",
    "it",
    "its",
    "itself",
    "they",
    "them",
    "their",
    "theirs",
    "themselves",
    "what",
    "which",
    "who",
    "whom",
    "this",
    "that",
    "these",
    "those",
    "am",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    "a",
    "an",
    "the",
    "and",
    "but",
    "if",
    "or",
    "because",
    "as",
    "until",
    "while",
    "of",
    "at",
    "by",
    "for",
    "with",
    "about",
    "against",
    "between",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "to",
    "from",
    "up",
    "down",
    "in",
    "out",
    "on",
    "off",
    "over",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "any",
    "both",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "can",
    "will",
    "just",
    "don",
    "should",
    "now",
}


def _normalize_title(title: str) -> str:
    return re.sub(r"[^\w\s]", "", title or "").strip().lower()


def _normalize_category(cat: str) -> str:
    s = (cat or "").replace("_", " ").strip().lower()
    s = re.sub(r"\s+", " ", s)
    # Canonicalize common variants
    if s == "no polarizing language":
        return "no polarizing language"
    if s == "no polarizing language" or s == "no polarizing":
        return "no polarizing language"
    return s


def _normalize_span(text: str) -> str:
    return (text or "").lower().strip()


def _tokenize_span(text: str) -> list[str]:
    return _normalize_span(text).split()


def _non_stopword_overlap(span1: str, span2: str) -> bool:
    tokens1 = set(_tokenize_span(span1)) - STOP_WORDS
    tokens2 = set(_tokenize_span(span2)) - STOP_WORDS
    return len(tokens1 & tokens2) >= 2


def _spans_match(
    span1: str,
    span2: str,
    *,
    title1: str | None = None,
    title2: str | None = None,
    para1: int | None = None,
    para2: int | None = None,
) -> bool:
    if title1 is not None and title2 is not None:
        if _normalize_title(title1) != _normalize_title(title2):
            return False
    if para1 is not None and para2 is not None and para1 != para2:
        return False
    norm1 = _normalize_span(span1)
    norm2 = _normalize_span(span2)
    return (norm1 in norm2 or norm2 in norm1) and _non_stopword_overlap(span1, span2)


def _flatten_llm(llm_json: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    article_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for article in llm_json:
        title = article.get("title", "UNKNOWN_TITLE")
        anns = article.get("annotations") or article.get("items") or []
        for ann in anns:
            if not isinstance(ann, dict):
                continue
            article_map[title].append(
                {
                    "text": ann.get("text", ""),
                    "category": ann.get("category", ""),
                    "paragraphIndex": ann.get("paragraphIndex"),
                }
            )
    return article_map


def _flatten_gold(gold_json: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    article_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for article in gold_json:
        title = article.get("title", "UNKNOWN_TITLE")
        for ann in article.get("annotations", []):
            if not isinstance(ann, dict):
                continue
            article_map[title].append(
                {
                    "text": ann.get("text", ""),
                    "category": ann.get("category", ""),
                    "paragraphIndex": ann.get("paragraphIndex"),
                }
            )
    return article_map


def _greedy_match(
    llm_annotations: list[dict[str, Any]],
    gold_annotations: list[dict[str, Any]],
    *,
    llm_title: str,
    gold_title: str,
) -> tuple[list[tuple[int, int]], set[int], set[int]]:
    matched: list[tuple[int, int]] = []
    used_gold: set[int] = set()
    unmatched_llm: set[int] = set(range(len(llm_annotations)))

    for li, llm in enumerate(llm_annotations):
        for gi, gold in enumerate(gold_annotations):
            if gi in used_gold:
                continue
            if _spans_match(
                llm.get("text", ""),
                gold.get("text", ""),
                title1=llm_title,
                title2=gold_title,
                para1=llm.get("paragraphIndex"),
                para2=gold.get("paragraphIndex"),
            ):
                matched.append((li, gi))
                used_gold.add(gi)
                unmatched_llm.discard(li)
                break

    unmatched_gold = set(range(len(gold_annotations))) - used_gold
    return matched, unmatched_llm, unmatched_gold


def _load_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{path} is empty.")
    return json.loads(text)


def _compute_category_pr(
    llm_json: list[dict[str, Any]],
    gold_json: list[dict[str, Any]],
) -> dict[str, dict[str, float | int]]:
    llm_map = _flatten_llm(llm_json)
    gold_map = _flatten_gold(gold_json)

    llm_norm_to_title = {_normalize_title(k): k for k in llm_map.keys()}
    gold_norm_to_title = {_normalize_title(k): k for k in gold_map.keys()}
    shared_norm_titles = set(llm_norm_to_title.keys()) & set(gold_norm_to_title.keys())

    # Per-category counts
    tp = Counter()
    fp = Counter()
    fn = Counter()
    support = Counter()

    # Count gold support first (end-to-end denominator)
    for norm in shared_norm_titles:
        gold_title = gold_norm_to_title[norm]
        for ann in gold_map[gold_title]:
            cat = _normalize_category(str(ann.get("category", "")))
            support[cat] += 1

    # Match and update tp/fp/fn per category
    for norm in shared_norm_titles:
        llm_title = llm_norm_to_title[norm]
        gold_title = gold_norm_to_title[norm]
        l_anns = llm_map[llm_title]
        g_anns = gold_map[gold_title]

        matched, unmatched_llm, unmatched_gold = _greedy_match(
            l_anns, g_anns, llm_title=llm_title, gold_title=gold_title
        )

        for li, gi in matched:
            pred_cat = _normalize_category(str(l_anns[li].get("category", "")))
            gold_cat = _normalize_category(str(g_anns[gi].get("category", "")))
            if pred_cat == gold_cat:
                tp[gold_cat] += 1
            else:
                fp[pred_cat] += 1
                fn[gold_cat] += 1

        for li in unmatched_llm:
            pred_cat = _normalize_category(str(l_anns[li].get("category", "")))
            fp[pred_cat] += 1

        for gi in unmatched_gold:
            gold_cat = _normalize_category(str(g_anns[gi].get("category", "")))
            fn[gold_cat] += 1

    metrics: dict[str, dict[str, float | int]] = {}
    for cat in sorted(set(support.keys()) | set(tp.keys()) | set(fp.keys()) | set(fn.keys())):
        tpi = int(tp[cat])
        fpi = int(fp[cat])
        fni = int(fn[cat])
        sup = int(support[cat])

        precision = tpi / (tpi + fpi) if (tpi + fpi) else 0.0
        recall = tpi / (tpi + fni) if (tpi + fni) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

        metrics[cat] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tpi,
            "fp": fpi,
            "fn": fni,
            "support": sup,
        }

    return metrics


def _write_csv(metrics: dict[str, dict[str, float | int]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for cat, m in metrics.items():
        rows.append(
            {
                "category": cat,
                "precision": round(float(m["precision"]), 6),
                "recall": round(float(m["recall"]), 6),
                "f1": round(float(m["f1"]), 6),
                "tp": int(m["tp"]),
                "fp": int(m["fp"]),
                "fn": int(m["fn"]),
                "support": int(m["support"]),
            }
        )
    # Stable sort: by support desc, then category
    rows.sort(key=lambda r: (-r["support"], r["category"]))
    with OUTPUT_CSV.open("w", encoding="utf-8") as f:
        f.write("category,precision,recall,f1,tp,fp,fn,support\n")
        for r in rows:
            f.write(
                f'{r["category"]},{r["precision"]},{r["recall"]},{r["f1"]},{r["tp"]},{r["fp"]},{r["fn"]},{r["support"]}\n'
            )


def _plot(metrics: dict[str, dict[str, float | int]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)

    cats = CATEGORY_ORDER[:]
    if not INCLUDE_NPL:
        cats = [c for c in cats if c != "no polarizing language"]

    # Ensure we only plot categories present in metrics (but keep order).
    cats = [c for c in cats if c in metrics]

    precisions = [float(metrics[c]["precision"]) for c in cats]
    recalls = [float(metrics[c]["recall"]) for c in cats]
    supports = [int(metrics[c]["support"]) for c in cats]

    labels = [f"{c.title()} (n={n})" for c, n in zip(cats, supports)]
    x = np.arange(len(cats))
    width = 0.36

    plt.style.use("seaborn-v0_8-colorblind")
    fig, ax = plt.subplots(figsize=(11, 6.2))

    b1 = ax.bar(x - width / 2, precisions, width, label="Precision")
    b2 = ax.bar(x + width / 2, recalls, width, label="Recall")

    ax.set_ylim(0, 1.05)
    ax.set_xticks(x, labels, rotation=15, ha="right")
    ax.set_ylabel("Score", fontweight="bold")
    ax.set_xlabel("Category", fontweight="bold")
    ax.set_title(
        "Per-Category Precision/Recall (1–20 HIT Gold Standard)\n"
        "End-to-end span matching (title + paragraphIndex + overlap)",
        pad=14,
    )
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.25)

    def _annotate(bars):
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + 0.02,
                f"{h:.2f}",
                ha="center",
                va="bottom",
                fontsize=10,
            )

    _annotate(b1)
    _annotate(b2)

    fig.tight_layout()
    fig.savefig(OUTPUT_IMG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved figure to {OUTPUT_IMG}")


def main() -> None:
    llm_json = _load_json(LLM_PATH)
    gold_json = _load_json(GOLD_PATH)
    if not isinstance(llm_json, list) or not isinstance(gold_json, list):
        raise TypeError("Expected list-of-articles JSON for both LLM and gold inputs.")

    metrics = _compute_category_pr(llm_json, gold_json)
    _write_csv(metrics)
    _plot(metrics)

    # Print a compact summary for copy/paste.
    print("\nPer-category metrics (end-to-end):")
    for cat in CATEGORY_ORDER:
        if cat not in metrics:
            continue
        m = metrics[cat]
        print(
            f"- {cat}: P={float(m['precision']):.3f} R={float(m['recall']):.3f} "
            f"F1={float(m['f1']):.3f} (TP={int(m['tp'])} FP={int(m['fp'])} FN={int(m['fn'])} n={int(m['support'])})"
        )


if __name__ == "__main__":
    main()
