import csv
import json
import re
from collections import Counter, defaultdict
from importlib import util
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Rectangle


REPO = Path(__file__).resolve().parents[4]
OUT_DIR = REPO / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27"

RAW_PRECISION_RECALL = OUT_DIR / "bagozzi_vs_original_unadjudicated_inhouse_precision_recall.json"
FINAL_INHOUSE = OUT_DIR / "final_inhouse_adjudicated_gold_standard_output.json"
BAGOZZI = OUT_DIR / "bagozzi_27_human_min_one_gold_standard_output.json"
AGREED_SPANS = OUT_DIR / "inhouse_bagozzi_agreed_polarizing_spans.csv"
LIVE_THREE_WAY = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/live/"
    / "in_house_live_validation_three_way_split_clusters.csv"
)
FOUR_ARTICLES = OUT_DIR / "turker_training_set_four_articles_consensus_final.json"

FIG_DIR = OUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def load_module(name: str, path: Path):
    spec = util.spec_from_file_location(name, path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


comparison = load_module(
    "paragraph_llm_human_comparison",
    REPO / "src/dataset_comparison_scripts/paragraph_llm_human_comparison.py",
)


def normalize_title(text: str | None) -> str:
    return re.sub(r"[^\w\s]", "", text or "").strip().lower()


def normalize_label(text: str | None) -> str:
    return re.sub(r"_+", " ", text or "").strip().lower()


def is_npl(annotation_or_row: dict) -> bool:
    joined = (
        normalize_label(annotation_or_row.get("category"))
        + " "
        + normalize_label(annotation_or_row.get("subcategory"))
    )
    return "no polarizing language" in joined


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def flatten_articles(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for article in data:
        for ann in article.get("annotations", []):
            row = dict(ann)
            row["title"] = article["title"]
            rows.append(row)
    return rows


def classify_overlap(inhouse_row: dict, bagozzi_rows: list[dict]) -> str:
    pidx = int(float(inhouse_row["paragraph_index"]))
    title = inhouse_row["article_title"]
    text = inhouse_row["representative_text"]
    exact = False
    partial = False

    for bagozzi in bagozzi_rows:
        if normalize_title(bagozzi["title"]) != normalize_title(title):
            continue
        if int(bagozzi["paragraphIndex"]) != pidx:
            continue
        if comparison.normalize_span(bagozzi["text"]) == comparison.normalize_span(text):
            exact = True
            break
        if comparison.spans_match(
            text,
            bagozzi["text"],
            title,
            bagozzi["title"],
            pidx,
            int(bagozzi["paragraphIndex"]),
        ):
            partial = True

    if exact:
        return "exact"
    if partial:
        return "partial"
    return "none"


def draw_flow(ax, x0, y0, h0, x1, y1, h1, color, alpha=0.42):
    verts = [
        (x0, y0),
        ((x0 + x1) / 2, y0),
        ((x0 + x1) / 2, y1),
        (x1, y1),
        (x1, y1 + h1),
        ((x0 + x1) / 2, y1 + h1),
        ((x0 + x1) / 2, y0 + h0),
        (x0, y0 + h0),
        (x0, y0),
    ]
    codes = [
        MplPath.MOVETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.LINETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CLOSEPOLY,
    ]
    ax.add_patch(PathPatch(MplPath(verts, codes), facecolor=color, edgecolor="none", alpha=alpha, zorder=1))


def draw_flow_highlight(ax, x0, y0, x1, y1, color, linewidth=14):
    verts = [
        (x0, y0),
        ((x0 + x1) / 2, y0),
        ((x0 + x1) / 2, y1),
        (x1, y1),
    ]
    codes = [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4]
    ax.add_patch(
        PathPatch(
            MplPath(verts, codes),
            facecolor="none",
            edgecolor=color,
            linewidth=linewidth,
            alpha=0.95,
            capstyle="round",
            joinstyle="round",
            zorder=2,
        )
    )


def sankey_figure(metrics: dict) -> Path:
    counts = metrics["sankey_counts"]
    fig, ax = plt.subplots(figsize=(13.5, 5.8), facecolor="white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0.0, 0.93)
    ax.axis("off")
    font_family = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]

    scale = 0.48 / counts["inhouse_started_polarizing_raw_individual"]
    colors = {
        "inhouse": "#0096FF",
        "inhouse_other": "#7DD3FC",
        "bagozzi": "#FFB000",
        "bagozzi_other": "#FFD166",
        "agree": "#00C853",
    }

    nodes = {
        "inhouse_start": (0.05, 0.64, counts["inhouse_started_polarizing_raw_individual"], colors["inhouse"]),
        "bagozzi": (0.05, 0.10, counts["bagozzi_polarizing"], colors["bagozzi"]),
        "inhouse_2of3": (0.31, 0.66, counts["final_inhouse_2of3_polarizing"], colors["inhouse"]),
        "inhouse_other": (
            0.31,
            0.41,
            counts["inhouse_started_polarizing_raw_individual"] - counts["final_inhouse_2of3_polarizing"],
            colors["inhouse_other"],
        ),
        "agreed": (0.69, 0.43, counts["greedy_2of3_inhouse_bagozzi_agreed_spans"], colors["agree"]),
        "inhouse_no_overlap": (
            0.69,
            0.77,
            counts["final_inhouse_2of3_polarizing"] - counts["greedy_2of3_inhouse_bagozzi_agreed_spans"],
            colors["inhouse_other"],
        ),
        "bagozzi_no_overlap": (
            0.69,
            0.09,
            counts["bagozzi_polarizing"] - counts["greedy_2of3_inhouse_bagozzi_agreed_spans"],
            colors["bagozzi_other"],
        ),
    }

    def node_box(name, label):
        x, y_mid, value, color = nodes[name]
        h = max(value * scale, 0.035)
        y = y_mid - h / 2
        width = 0.06
        text_color = "#0f172a" if name in {"bagozzi", "inhouse_other", "inhouse_no_overlap", "bagozzi_no_overlap"} else "white"
        label_position = {
            "inhouse_2of3": "above",
            "inhouse_other": "inside",
        }.get(name, "below")
        ax.add_patch(Rectangle((x, y), width, h, facecolor=color, edgecolor="white", linewidth=1.2, zorder=3))
        ax.text(
            x + width / 2,
            y_mid,
            f"{value}",
            ha="center",
            va="center",
            color=text_color,
            fontsize=14,
            fontweight="bold",
            fontfamily=font_family,
            zorder=4,
        )
        if label_position == "above":
            label_y = y + h + 0.018
            va = "bottom"
        elif label_position == "inside":
            label_y = y_mid - min(h * 0.28, 0.085)
            va = "center"
        else:
            label_y = y - 0.022
            va = "top"
        ax.text(
            x + width / 2,
            label_y,
            label,
            ha="center",
            va=va,
            fontsize=9.5,
            color="#0f172a",
            fontfamily=font_family,
            zorder=4,
        )
        return x, y, h

    x0, y0, h0 = node_box("inhouse_start", "Raw in-house\npolarizing annotations")
    x1, y1, h1 = node_box("inhouse_2of3", "Final in-house\n2/3 labels")
    xi, yi, hi = node_box("inhouse_other", "Other raw\nin-house annotations")
    xb, yb, hb = node_box("bagozzi", "Expert\nannotations")
    xa, ya, ha = node_box("agreed", "2/3 in-house +\nexpert span overlap")
    xn, yn, hn = node_box("inhouse_no_overlap", "2/3 labels without\nexpert span overlap")
    xe, ye, he = node_box("bagozzi_no_overlap", "Expert annotations\nnot retained")

    h_in_2 = counts["final_inhouse_2of3_polarizing"] * scale
    h_in_drop = (counts["inhouse_started_polarizing_raw_individual"] - counts["final_inhouse_2of3_polarizing"]) * scale
    draw_flow(ax, x0 + 0.06, y0 + h0 - h_in_2, h_in_2, x1, y1, h1, colors["inhouse"], 0.58)
    draw_flow(ax, x0 + 0.06, y0, h_in_drop, xi, yi, hi, colors["inhouse_other"], 0.58)

    h_agree = counts["greedy_2of3_inhouse_bagozzi_agreed_spans"] * scale
    h_2_no = (counts["final_inhouse_2of3_polarizing"] - counts["greedy_2of3_inhouse_bagozzi_agreed_spans"]) * scale
    draw_flow(ax, x1 + 0.06, y1 + h1 - h_agree, h_agree, xa, ya + ha - h_agree, h_agree, colors["agree"], 0.68)
    draw_flow(ax, x1 + 0.06, y1, h_2_no, xn, yn, hn, colors["inhouse_other"], 0.55)

    h_b_agree = counts["greedy_2of3_inhouse_bagozzi_agreed_spans"] * scale
    h_b_no = (counts["bagozzi_polarizing"] - counts["greedy_2of3_inhouse_bagozzi_agreed_spans"]) * scale
    expert_overlap_y0 = yb + hb - h_b_agree
    expert_overlap_y1 = ya
    draw_flow(ax, xb + 0.06, expert_overlap_y0, h_b_agree, xa, expert_overlap_y1, h_b_agree, colors["bagozzi"], 0.72)
    draw_flow_highlight(
        ax,
        xb + 0.06,
        expert_overlap_y0 + h_b_agree / 2,
        xa,
        expert_overlap_y1 + h_b_agree / 2,
        colors["bagozzi"],
    )
    draw_flow(ax, xb + 0.06, yb, h_b_no, xe, ye, he, colors["bagozzi_other"], 0.58)

    ax.set_title(
        "Polarizing Annotations: Expert, In-House, and Retained Span Overlap",
        fontsize=16,
        fontweight="bold",
        pad=18,
        fontfamily=font_family,
    )
    out = FIG_DIR / "sankey_inhouse_bagozzi_annotation_funnel.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def agreement_overlap_figure(metrics: dict) -> Path:
    groups = ["2/3 in-house", "1/3 in-house"]
    exact = [metrics["overlap_counts"]["2-1"]["exact"], metrics["overlap_counts"]["1-2"]["exact"]]
    partial = [metrics["overlap_counts"]["2-1"]["partial"], metrics["overlap_counts"]["1-2"]["partial"]]
    none = [metrics["overlap_counts"]["2-1"]["none"], metrics["overlap_counts"]["1-2"]["none"]]

    fig, ax = plt.subplots(figsize=(9.5, 6), facecolor="white")
    x = np.arange(len(groups))
    width = 0.55
    ax.bar(x, exact, width, label="Exact span text", color="#16a34a")
    ax.bar(x, partial, width, bottom=exact, label="Partial span overlap", color="#65a30d")
    ax.bar(x, none, width, bottom=np.array(exact) + np.array(partial), label="No Bagozzi overlap", color="#cbd5e1")

    totals = [sum(v) for v in zip(exact, partial, none)]
    for idx, total in enumerate(totals):
        ax.text(idx, total + 2, f"n={total}", ha="center", va="bottom", fontsize=10)
        ax.text(idx, exact[idx] / 2 if exact[idx] else 0.7, str(exact[idx]), ha="center", va="center", color="white", fontweight="bold")
        ax.text(idx, exact[idx] + partial[idx] / 2, str(partial[idx]), ha="center", va="center", color="white", fontweight="bold")
        ax.text(
            idx,
            exact[idx] + partial[idx] + none[idx] / 2,
            str(none[idx]),
            ha="center",
            va="center",
            color="#334155",
            fontweight="bold",
        )

    ax.set_xticks(x, groups)
    ax.set_ylabel("In-house validation clusters")
    ax.set_title("Bagozzi Span Agreement: Exact vs. Partial Overlap", fontsize=15, fontweight="bold")
    ax.legend(loc="upper right", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
    out = FIG_DIR / "agreement_exact_vs_partial_span_overlap.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def heatmap_figure(four_articles: list[dict]) -> Path:
    article_labels = [short_title(article["title"]) for article in four_articles]
    categories = ["Persuasive Propaganda", "Inflammatory Language"]
    subcategories = [
        "Exaggeration",
        "Casual Oversimplification",
        "Doubt",
        "Bandwagon",
        "Slogans",
        "Scapegoating",
        "Name-Calling",
        "Demonization",
    ]

    cat_matrix = np.array([
        [sum(1 for ann in article["annotations"] if normalize_label(ann["category"]) == normalize_label(cat)) for cat in categories]
        for article in four_articles
    ])
    sub_matrix = np.array([
        [sum(1 for ann in article["annotations"] if normalize_label(ann["subcategory"]) == normalize_label(sub)) for sub in subcategories]
        for article in four_articles
    ])

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(13, 8),
        facecolor="white",
        gridspec_kw={"height_ratios": [1, 2.2], "hspace": 0.48},
    )
    for ax, matrix, cols, title in [
        (axes[0], cat_matrix, categories, "Top-Level Category Frequency"),
        (axes[1], sub_matrix, subcategories, "Subcategory Frequency"),
    ]:
        im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto")
        ax.set_xticks(np.arange(len(cols)), cols, rotation=30, ha="right")
        ax.set_yticks(np.arange(len(article_labels)), article_labels)
        ax.set_title(title, fontsize=12, fontweight="bold")
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                val = int(matrix[i, j])
                ax.text(j, i, str(val), ha="center", va="center", color="#0f172a", fontweight="bold" if val else "normal")
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)

    fig.suptitle("Four-Article Final Annotation Distribution", fontsize=16, fontweight="bold", y=0.98)
    out = FIG_DIR / "four_article_category_subcategory_heatmap.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def coverage_figure(four_articles: list[dict], metrics: dict) -> Path:
    subcategories = [
        "Exaggeration",
        "Casual Oversimplification",
        "Doubt",
        "Bandwagon",
        "Slogans",
        "Scapegoating",
        "Name-Calling",
        "Demonization",
    ]
    colors = {
        "Exaggeration": "#60a5fa",
        "Casual Oversimplification": "#93c5fd",
        "Doubt": "#2563eb",
        "Bandwagon": "#1d4ed8",
        "Slogans": "#172554",
        "Scapegoating": "#f97316",
        "Name-Calling": "#dc2626",
        "Demonization": "#7f1d1d",
    }

    article_labels = [short_title(article["title"]) for article in four_articles]
    x = np.arange(len(four_articles))
    bottoms = np.zeros(len(four_articles))

    fig, ax = plt.subplots(figsize=(12, 6.8), facecolor="white")
    for sub in subcategories:
        vals = np.array([
            sum(1 for ann in article["annotations"] if normalize_label(ann["subcategory"]) == normalize_label(sub))
            for article in four_articles
        ])
        ax.bar(x, vals, bottom=bottoms, color=colors[sub], label=sub)
        bottoms += vals

    for idx, total in enumerate(bottoms):
        ax.text(idx, total + 0.25, str(int(total)), ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_xticks(x, article_labels, rotation=18, ha="right")
    ax.set_ylabel("Final agreed annotations")
    ax.set_title("Coverage by Article: Final Annotation Subcategories", fontsize=15, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
    ax.legend(ncol=2, bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False, fontsize=9)

    out = FIG_DIR / "four_article_coverage_by_annotation_category.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def short_title(title: str) -> str:
    mapping = {
        "George Conway Urges Trump To Resign Over Aborted Iran Strike": "George Conway",
        "Trump Rips 'Horrible' New York Times, Washington Post, Wonders If People Will 'Demand' He Stay In White House": "Trump Rips\n'Horrible'",
        "'Every American Is Entitled To Health Care': Sen. Bernie Sanders": "Health Care\nSanders",
        "'We Are Livid!': Mural Honoring Philadelphia Police Officer Killed In Line Of Duty Vandalized": "We Are\nLivid",
    }
    return mapping.get(title, title[:28])


def main():
    precision = json.loads(RAW_PRECISION_RECALL.read_text(encoding="utf-8"))
    final_inhouse = flatten_articles(FINAL_INHOUSE)
    final_inhouse_polarizing = [ann for ann in final_inhouse if not is_npl(ann)]
    final_inhouse_2of3 = [
        ann for ann in final_inhouse_polarizing if ann.get("vote_pattern") == "2-1"
    ]
    bagozzi_polarizing = [ann for ann in flatten_articles(BAGOZZI) if not is_npl(ann)]
    agreed_rows = read_csv(AGREED_SPANS)
    greedy_2of3_agreed = [
        row for row in agreed_rows if row["inhouse_vote_pattern"] == "2-1"
    ]

    live_rows = [row for row in read_csv(LIVE_THREE_WAY) if not is_npl(row)]
    overlap_counts = {}
    overlap_detail_rows = []
    for vote_pattern in ["2-1", "1-2"]:
        bucket = Counter()
        for row in live_rows:
            if row["vote_pattern"] != vote_pattern:
                continue
            overlap_type = classify_overlap(row, bagozzi_polarizing)
            bucket[overlap_type] += 1
            overlap_detail_rows.append(
                {
                    "vote_pattern": vote_pattern,
                    "article_title": row["article_title"],
                    "paragraph_index": row["paragraph_index"],
                    "subcategory": row["subcategory"],
                    "representative_text": row["representative_text"],
                    "overlap_type": overlap_type,
                }
            )
        overlap_counts[vote_pattern] = {
            "total": sum(bucket.values()),
            "exact": bucket["exact"],
            "partial": bucket["partial"],
            "overlap_total": bucket["exact"] + bucket["partial"],
            "none": bucket["none"],
        }

    four_articles = json.loads(FOUR_ARTICLES.read_text(encoding="utf-8"))

    metrics = {
        "source_files": {
            "raw_precision_recall": str(RAW_PRECISION_RECALL),
            "final_inhouse": str(FINAL_INHOUSE),
            "bagozzi": str(BAGOZZI),
            "agreed_spans": str(AGREED_SPANS),
            "live_three_way": str(LIVE_THREE_WAY),
            "four_articles": str(FOUR_ARTICLES),
        },
        "definitions": {
            "started_inhouse": "raw individual polarizing in-house annotations",
            "final_2of3_label": "final in-house polarizing annotations with vote_pattern == 2-1",
            "bagozzi_annotations": "Dr. Bagozzi polarizing annotations",
            "sankey_overlap": "greedy retained agreed polarizing spans with inhouse_vote_pattern == 2-1",
            "agreement_overlap": "direct existence overlap from live three-way validation clusters against Dr. Bagozzi polarizing annotations",
            "exact_overlap": "normalized span text is identical",
            "partial_overlap": "repo spans_match returned true, but normalized span text was not identical",
        },
        "sankey_counts": {
            "inhouse_started_polarizing_raw_individual": precision["counts"]["raw_inhouse_polarizing_individual"],
            "final_inhouse_polarizing": len(final_inhouse_polarizing),
            "final_inhouse_2of3_polarizing": len(final_inhouse_2of3),
            "bagozzi_polarizing": len(bagozzi_polarizing),
            "greedy_2of3_inhouse_bagozzi_agreed_spans": len(greedy_2of3_agreed),
        },
        "overlap_counts": overlap_counts,
        "four_article_annotation_counts": {
            article["title"]: len(article.get("annotations", [])) for article in four_articles
        },
        "four_article_subcategory_counts": dict(
            Counter(
                normalize_label(ann["subcategory"])
                for article in four_articles
                for ann in article.get("annotations", [])
            )
        ),
    }

    output_paths = {
        "sankey": str(sankey_figure(metrics)),
        "agreement_overlap": str(agreement_overlap_figure(metrics)),
        "heatmap": str(heatmap_figure(four_articles)),
        "coverage": str(coverage_figure(four_articles, metrics)),
    }
    metrics["figures"] = output_paths

    with (OUT_DIR / "inhouse_bagozzi_visualization_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)
        handle.write("\n")

    with (OUT_DIR / "inhouse_bagozzi_overlap_exact_partial.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "vote_pattern",
                "article_title",
                "paragraph_index",
                "subcategory",
                "representative_text",
                "overlap_type",
            ],
        )
        writer.writeheader()
        writer.writerows(overlap_detail_rows)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
