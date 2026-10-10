from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap


REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from src.dataset_comparison_scripts.statistical_analysis.bagozzi_27 import (  # noqa: E402
    make_model_miss_heatmap as base,
)


OUTPUT_STEM = "subcategory_gold_miss_heatmap_binary_decision_point_only"
PNG_PATH = base.OUT_DIR / f"{OUTPUT_STEM}.png"
WIDE_CSV_PATH = base.GOLD_JSON.parent / f"{OUTPUT_STEM}.csv"
LONG_CSV_PATH = base.GOLD_JSON.parent / f"{OUTPUT_STEM}_long.csv"
MASTER_RESULTS_CSV = base.GOLD_JSON.parent / "model_prompt_overall_f1_table_npl_inclusive.csv"

DISPLAY_LABELS = {
    "no polarizing language": "No polarizing\nlanguage",
    "exaggeration": "Exaggeration",
    "casual oversimplification": "Casual\noversimplification",
    "doubt": "Doubt",
    "bandwagon": "Bandwagon",
    "slogans": "Slogans",
    "scapegoating": "Scapegoating",
    "name-calling": "Name-calling",
    "demonization": "Demonization",
}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def selected_prediction_specs() -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    for row in base.read_csv_dicts(MASTER_RESULTS_CSV):
        if row["architecture"] == "decision point" and row["model"] != "Decision point binary filter":
            continue
        path = Path(row["prediction_path"])
        if not path.exists():
            raise FileNotFoundError(f"Missing prediction file listed in master results: {path}")
        if row["model"] == "Decision point binary filter":
            system = "Decision point - binary filter"
        elif row["architecture"] == "OG adjudication":
            system = f"OG adj - {row['prompt']}"
        else:
            system = f"{row['model']} - {row['prompt']}"
        specs.append(
            {
                "family": row["architecture"],
                "system": system,
                "path": str(path),
            }
        )
    return specs


def build_rows(
    specs: list[dict[str, str]], gold_articles: list[dict[str, Any]], gold_counts: dict[str, int]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        miss = compute_misses(base.load_json(Path(spec["path"])), gold_articles)
        precision = miss["matched_total"] / miss["prediction_total"] if miss["prediction_total"] else 0.0
        recall = miss["matched_total"] / miss["gold_total"] if miss["gold_total"] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        row: dict[str, Any] = {
            "family": spec["family"],
            "system": spec["system"],
            "prediction_total": miss["prediction_total"],
            "gold_total": miss["gold_total"],
            "matched_total": miss["matched_total"],
            "polarization_precision": precision,
            "polarization_recall": recall,
            "polarization_f1": f1,
        }
        for subcategory in base.SUBCATEGORY_ORDER:
            missed = miss["missed_by_subcategory"].get(subcategory, 0)
            total = gold_counts.get(subcategory, 0)
            row[f"{subcategory}_missed"] = missed
            row[f"{subcategory}_miss_rate"] = missed / total if total else 0.0
        rows.append(row)

    return sorted(
        rows,
        key=lambda row: (
            row["system"] != "Decision point - binary filter",
            -row["polarization_f1"],
            row["system"],
        ),
    )


def compute_misses(
    predicted_articles: list[dict[str, Any]], gold_articles: list[dict[str, Any]]
) -> dict[str, Any]:
    pred = base.dp.flatten_articles(predicted_articles, include_npl=True)
    gold = base.dp.flatten_articles(gold_articles, include_npl=True)
    # Match the manuscript evaluation policy: exclude articles with no gold annotations.
    titles = sorted(title for title, article in gold.items() if article["annotations"])
    missed_by_subcategory = {subcategory: 0 for subcategory in base.SUBCATEGORY_ORDER}
    matched_total = 0
    prediction_total = 0
    gold_total = 0
    for title in titles:
        pred_annotations = pred.get(title, {"annotations": []})["annotations"]
        gold_annotations = gold[title]["annotations"]
        pairs, _unmatched_pred, unmatched_gold = base.dp.greedy_match(
            pred_annotations,
            gold_annotations,
            lambda prediction, reference, current_title=title: base.dp.npl_aware_match(
                prediction, reference, current_title
            ),
        )
        matched_total += len(pairs)
        prediction_total += len(pred_annotations)
        gold_total += len(gold_annotations)
        for gold_index in unmatched_gold:
            subcategory = base.dp.canonical_subcategory(gold_annotations[gold_index].get("subcategory"))
            missed_by_subcategory[subcategory] += 1
    return {
        "missed_by_subcategory": missed_by_subcategory,
        "matched_total": matched_total,
        "prediction_total": prediction_total,
        "gold_total": gold_total,
    }


def write_outputs(rows: list[dict[str, Any]], gold_counts: dict[str, int]) -> None:
    wide_rows: list[dict[str, Any]] = []
    long_rows: list[dict[str, Any]] = []
    for row in rows:
        wide: dict[str, Any] = {
            "family": row["family"],
            "system": row["system"],
            "prediction_total": row["prediction_total"],
            "gold_total": row["gold_total"],
            "matched_total": row["matched_total"],
            "polarization_precision": round(row["polarization_precision"], 6),
            "polarization_recall": round(row["polarization_recall"], 6),
            "polarization_f1": round(row["polarization_f1"], 6),
        }
        for severity_rank, subcategory in enumerate(base.SUBCATEGORY_ORDER):
            missed = row[f"{subcategory}_missed"]
            miss_rate = row[f"{subcategory}_miss_rate"]
            wide[f"{subcategory}_missed"] = missed
            wide[f"{subcategory}_miss_rate"] = round(miss_rate, 6)
            long_rows.append(
                {
                    "family": row["family"],
                    "system": row["system"],
                    "polarization_f1": round(row["polarization_f1"], 6),
                    "severity_rank": severity_rank,
                    "subcategory": subcategory,
                    "gold_support": gold_counts[subcategory],
                    "missed_count": missed,
                    "miss_rate": round(miss_rate, 6),
                }
            )
        wide_rows.append(wide)

    write_csv(WIDE_CSV_PATH, wide_rows)
    write_csv(LONG_CSV_PATH, long_rows)


def render_heatmap(rows: list[dict[str, Any]], gold_counts: dict[str, int]) -> None:
    subcategories = base.SUBCATEGORY_ORDER
    matrix = np.array(
        [[row[f"{subcategory}_miss_rate"] for subcategory in subcategories] for row in rows],
        dtype=float,
    )
    aggregate = matrix.mean(axis=0, keepdims=True)
    plot_matrix = np.vstack([matrix, aggregate])

    row_labels = [
        f"{row['system']}   |   F1 {row['polarization_f1']:.3f}"
        for row in rows
    ] + ["Across-system mean"]
    column_labels = [
        f"{DISPLAY_LABELS[subcategory]}\n(n={gold_counts[subcategory]})"
        for subcategory in subcategories
    ]

    cmap = LinearSegmentedColormap.from_list(
        "miss_rate_blue",
        ["#f7fbff", "#b9e3ff", "#4fa3f7", "#1261a6", "#073763"],
    )
    plt.rcParams.update(
        {
            "font.family": ["Avenir Next", "Avenir", "DejaVu Sans"],
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    fig_height = max(12.0, 0.34 * len(row_labels) + 3.0)
    fig, ax = plt.subplots(figsize=(17.5, fig_height), constrained_layout=True)
    image = ax.imshow(plot_matrix, cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto", interpolation="nearest")

    ax.set_xticks(np.arange(len(column_labels)), labels=column_labels)
    ax.set_yticks(np.arange(len(row_labels)), labels=row_labels)
    ax.tick_params(axis="x", top=True, bottom=False, labeltop=True, labelbottom=False, length=0, pad=10)
    ax.tick_params(axis="y", length=0, pad=8)
    plt.setp(ax.get_xticklabels(), fontsize=9.5, fontweight="semibold")
    plt.setp(ax.get_yticklabels(), fontsize=8.5)
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.get_yticklabels()[-1].set_fontweight("bold")

    for i in range(plot_matrix.shape[0]):
        for j in range(plot_matrix.shape[1]):
            rate = plot_matrix[i, j]
            if i == len(rows):
                label = f"{rate:.0%}"
            else:
                missed = rows[i][f"{subcategories[j]}_missed"]
                total = gold_counts[subcategories[j]]
                label = f"{rate:.0%}\n{missed}/{total}"
            ax.text(
                j,
                i,
                label,
                ha="center",
                va="center",
                fontsize=7.8,
                fontweight="semibold" if i in {0, len(rows)} else "normal",
                color="white" if rate >= 0.55 else "#10243b",
                linespacing=1.05,
            )

    ax.axhline(0.5, color="#f28e2b", linewidth=2.5)
    ax.axhline(len(rows) - 0.5, color="#10243b", linewidth=2.0)
    ax.set_xticks(np.arange(-0.5, len(subcategories), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(row_labels), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        "Gold-Standard Polarization Misses by Subcategory",
        loc="left",
        fontsize=19,
        fontweight="bold",
        pad=112,
        color="#10243b",
    )
    ax.text(
        0.0,
        1.105,
        "NPL-inclusive intersection gold set. Columns follow increasing polarization severity; darker cells indicate a higher share of gold annotations missed.",
        transform=ax.transAxes,
        fontsize=10.5,
        color="#4a5b6b",
        va="bottom",
    )
    ax.text(
        0.0,
        1.068,
        "Cells show miss rate and missed/gold count. Only the weighted binary-filter decision-point variant is included; rows are otherwise ordered by polarization F1.",
        transform=ax.transAxes,
        fontsize=9.5,
        color="#667788",
        va="bottom",
    )

    colorbar = fig.colorbar(image, ax=ax, orientation="horizontal", fraction=0.025, pad=0.035, aspect=55)
    colorbar.set_label("Gold annotation miss rate", fontsize=9.5)
    colorbar.set_ticks([0, 0.25, 0.5, 0.75, 1.0], labels=["0%", "25%", "50%", "75%", "100%"])
    colorbar.outline.set_visible(False)

    PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG_PATH, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    gold_articles = base.load_json(base.GOLD_JSON)
    gold_counts = base.subcategory_counts(gold_articles)
    rows = build_rows(selected_prediction_specs(), gold_articles, gold_counts)
    write_outputs(rows, gold_counts)
    render_heatmap(rows, gold_counts)
    print(
        json.dumps(
            {
                "systems": len(rows),
                "gold_counts": gold_counts,
                "png": str(PNG_PATH),
                "wide_csv": str(WIDE_CSV_PATH),
                "long_csv": str(LONG_CSV_PATH),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
