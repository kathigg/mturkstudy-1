from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # .../src
MPL_DIR = BASE_DIR / "data_visualizations" / ".mplconfig"
os.environ.setdefault("MPLCONFIGDIR", str(MPL_DIR))

import matplotlib.pyplot as plt  # noqa: E402


CATEGORY_ORDER = [
    "no polarizing language",
    "persuasive propaganda",
    "inflammatory language",
]

CATEGORY_LABELS = {
    "no polarizing language": "No Polarizing Language",
    "persuasive propaganda": "Persuasive Propaganda",
    "inflammatory language": "Inflammatory Language",
}

SOURCE_COLORS = {
    "Human": "#2563eb",
    "LLM": "#dc2626",
}


def load_json(path: Path):
    return json.loads(path.read_text())


def normalize_label(label: str | None) -> str:
    return (label or "").replace("_", " ").strip().lower()


def canonical_category(category: str | None) -> str:
    label = normalize_label(category)
    if label in CATEGORY_LABELS:
        return label
    return label


def count_categories(path: Path) -> tuple[dict[str, int], int]:
    data = load_json(path)
    counts = {key: 0 for key in CATEGORY_ORDER}
    total = 0
    for article in data:
        for ann in article.get("annotations", []):
            key = canonical_category(ann.get("category"))
            if key not in counts:
                counts[key] = 0
            counts[key] += 1
            total += 1
    return counts, total


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["category_key", "category_label", "source", "count", "share_within_source"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_plot(rows: list[dict], *, human_total: int, llm_total: int, output_path: Path, title: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    MPL_DIR.mkdir(parents=True, exist_ok=True)

    x_labels = [CATEGORY_LABELS[key] for key in CATEGORY_ORDER]
    human_counts = [next(row["count"] for row in rows if row["category_key"] == key and row["source"] == "Human") for key in CATEGORY_ORDER]
    llm_counts = [next(row["count"] for row in rows if row["category_key"] == key and row["source"] == "LLM") for key in CATEGORY_ORDER]
    human_shares = [next(row["share_within_source"] for row in rows if row["category_key"] == key and row["source"] == "Human") for key in CATEGORY_ORDER]
    llm_shares = [next(row["share_within_source"] for row in rows if row["category_key"] == key and row["source"] == "LLM") for key in CATEGORY_ORDER]

    width = 0.36
    positions = range(len(CATEGORY_ORDER))

    fig, ax = plt.subplots(figsize=(9, 5.2))
    bars_h = ax.bar(
        [p - width / 2 for p in positions],
        human_counts,
        width=width,
        color=SOURCE_COLORS["Human"],
        edgecolor="black",
        linewidth=0.5,
        label=f"Human (n={human_total})",
    )
    bars_l = ax.bar(
        [p + width / 2 for p in positions],
        llm_counts,
        width=width,
        color=SOURCE_COLORS["LLM"],
        edgecolor="black",
        linewidth=0.5,
        label=f"LLM (n={llm_total})",
    )

    ax.set_title(title)
    ax.set_ylabel("Annotation Count")
    ax.set_xticks(list(positions))
    ax.set_xticklabels(x_labels, rotation=12, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    ax.legend(frameon=False)

    for bars, shares in [(bars_h, human_shares), (bars_l, llm_shares)]:
        for bar, share in zip(bars, shares):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.5,
                f"{int(bar.get_height())}\n{share * 100:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--human-path",
        default=str(base_dir / "../2-20/../../mturk_results/2-20/2-20_human_min_one_gold_standard_output.json"),
    )
    parser.add_argument(
        "--llm-path",
        default=str(base_dir / "../2-20/../../llm_annotation_results/2-20/2-20_llm_min_one_final_annotations_3annotators.json"),
    )
    parser.add_argument(
        "--csv-output",
        default=str(base_dir / "2-20/2-20_human_vs_llm_category_distribution.csv"),
    )
    parser.add_argument(
        "--plot-output",
        default=str(base_dir / "2-20/2-20_human_vs_llm_category_distribution.png"),
    )
    parser.add_argument(
        "--title",
        default="2-20 Human vs LLM Category Distribution",
    )
    args = parser.parse_args(argv)

    human_path = Path(args.human_path).resolve()
    llm_path = Path(args.llm_path).resolve()
    csv_output = Path(args.csv_output).resolve()
    plot_output = Path(args.plot_output).resolve()

    human_counts, human_total = count_categories(human_path)
    llm_counts, llm_total = count_categories(llm_path)

    rows = []
    for key in CATEGORY_ORDER:
        rows.append(
            {
                "category_key": key,
                "category_label": CATEGORY_LABELS[key],
                "source": "Human",
                "count": human_counts.get(key, 0),
                "share_within_source": round(human_counts.get(key, 0) / human_total, 4) if human_total else 0.0,
            }
        )
        rows.append(
            {
                "category_key": key,
                "category_label": CATEGORY_LABELS[key],
                "source": "LLM",
                "count": llm_counts.get(key, 0),
                "share_within_source": round(llm_counts.get(key, 0) / llm_total, 4) if llm_total else 0.0,
            }
        )

    write_csv(rows, csv_output)
    write_plot(rows, human_total=human_total, llm_total=llm_total, output_path=plot_output, title=args.title)

    print(f"Wrote CSV: {csv_output}")
    print(f"Wrote plot: {plot_output}")
    print("Human counts:", human_counts)
    print("LLM counts:", llm_counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
