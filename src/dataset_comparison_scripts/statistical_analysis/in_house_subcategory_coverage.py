from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt

from in_house_density_and_agreement import load_raw_annotations


SUBCATEGORY_SPECS = [
    ("no polarizing language", "No Polarizing Language", "#7f8c8d"),
    ("exaggeration", "Exaggeration", "#d97706"),
    ("slogans", "Slogans", "#d97706"),
    ("bandwagon", "Bandwagon", "#d97706"),
    ("casual oversimplification", "Casual Oversimplification", "#d97706"),
    ("doubt", "Doubt", "#d97706"),
    ("name-calling", "Name-Calling", "#b91c1c"),
    ("demonization", "Demonization", "#b91c1c"),
    ("scapegoating", "Scapegoating", "#b91c1c"),
]


def compute_rows(input_path: Path) -> tuple[list[dict], int, int]:
    _, _, annotations_by_worker_paragraph = load_raw_annotations(input_path)
    raw_annotations = [ann for anns in annotations_by_worker_paragraph.values() for ann in anns]
    total_annotations = len(raw_annotations)
    total_units = len(annotations_by_worker_paragraph)

    counts = {}
    for ann in raw_annotations:
        subcategory = ann["subcategory"]
        counts[subcategory] = counts.get(subcategory, 0) + 1

    rows = []
    for key, label, color in SUBCATEGORY_SPECS:
        count = counts.get(key, 0)
        rows.append(
            {
                "subcategory_key": key,
                "subcategory_label": label,
                "count": count,
                "share_of_annotations": round(count / total_annotations, 4) if total_annotations else 0.0,
                "annotations_per_worker_paragraph": round(count / total_units, 4) if total_units else 0.0,
                "covered": "yes" if count > 0 else "no",
                "color": color,
            }
        )

    return rows, total_annotations, total_units


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "subcategory_key",
                "subcategory_label",
                "count",
                "share_of_annotations",
                "annotations_per_worker_paragraph",
                "covered",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in writer.fieldnames})


def write_plot(rows: list[dict], *, total_annotations: int, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    labels = [row["subcategory_label"] for row in rows]
    counts = [row["count"] for row in rows]
    colors = [row["color"] for row in rows]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(labels, counts, color=colors, edgecolor="black", linewidth=0.5)

    ax.set_title("Latest In-House Annotation Coverage by Subcategory")
    ax.set_ylabel("Raw Annotation Count")
    ax.set_xlabel("Subcategory")
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    for bar, row in zip(bars, rows):
        count = row["count"]
        share = row["share_of_annotations"] * 100
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.8,
            f"{count}\n{share:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    ax.text(
        0.99,
        0.98,
        f"Total annotations: {total_annotations}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#dddddd", "boxstyle": "round,pad=0.3"},
    )

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=str(base_dir / "../../mturk_results/1-20/1-20-in-house.json"),
    )
    parser.add_argument(
        "--csv-output",
        default=str(base_dir / "1-20/1-20_in_house_subcategory_coverage.csv"),
    )
    parser.add_argument(
        "--plot-output",
        default=str(base_dir / "1-20/1-20_in_house_subcategory_coverage.png"),
    )
    args = parser.parse_args(argv)

    rows, total_annotations, total_units = compute_rows(Path(args.input).resolve())
    csv_output = Path(args.csv_output).resolve()
    plot_output = Path(args.plot_output).resolve()

    write_csv(rows, csv_output)
    write_plot(rows, total_annotations=total_annotations, output_path=plot_output)

    print(f"Wrote CSV: {csv_output}")
    print(f"Wrote plot: {plot_output}")
    print(f"Total annotations: {total_annotations}")
    print(f"Worker-paragraph units: {total_units}")
    missing = [row["subcategory_label"] for row in rows if row["count"] == 0]
    print(f"Missing subcategories: {missing if missing else 'None'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
