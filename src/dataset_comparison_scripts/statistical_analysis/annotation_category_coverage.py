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


CATEGORY_SPECS = [
    ("no polarizing language", "No Polarizing Language", "#7f8c8d"),
    ("persuasive propaganda", "Persuasive Propaganda", "#d97706"),
    ("inflammatory language", "Inflammatory Language", "#b91c1c"),
]


def load_json(path: Path):
    return json.loads(path.read_text())


def normalize_label(label: str | None) -> str:
    return (label or "").replace("_", " ").strip().lower()


def compute_rows(input_path: Path) -> tuple[list[dict], int]:
    data = load_json(input_path)
    counts = {key: 0 for key, _, _ in CATEGORY_SPECS}
    total_annotations = 0

    for article in data:
        for ann in article.get("annotations", []):
            key = normalize_label(ann.get("category"))
            if key not in counts:
                counts[key] = 0
            counts[key] += 1
            total_annotations += 1

    rows = []
    for key, label, color in CATEGORY_SPECS:
        count = counts.get(key, 0)
        rows.append(
            {
                "category_key": key,
                "category_label": label,
                "count": count,
                "share_of_annotations": round(count / total_annotations, 4) if total_annotations else 0.0,
                "covered": "yes" if count > 0 else "no",
                "color": color,
            }
        )

    return rows, total_annotations


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["category_key", "category_label", "count", "share_of_annotations", "covered"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in writer.fieldnames})


def write_plot(rows: list[dict], *, total_annotations: int, output_path: Path, title: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    MPL_DIR.mkdir(parents=True, exist_ok=True)

    labels = [row["category_label"] for row in rows]
    counts = [row["count"] for row in rows]
    colors = [row["color"] for row in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, counts, color=colors, edgecolor="black", linewidth=0.5)

    ax.set_title(title)
    ax.set_ylabel("Annotation Count")
    ax.set_xlabel("Category")
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)

    for bar, row in zip(bars, rows):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.5,
            f"{row['count']}\n{row['share_of_annotations'] * 100:.1f}%",
            ha="center",
            va="bottom",
            fontsize=10,
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
    parser.add_argument("--input", required=True)
    parser.add_argument("--csv-output", required=True)
    parser.add_argument("--plot-output", required=True)
    parser.add_argument("--title", default="Category Distribution")
    args = parser.parse_args(argv)

    rows, total_annotations = compute_rows(Path(args.input).resolve())
    csv_output = Path(args.csv_output).resolve()
    plot_output = Path(args.plot_output).resolve()

    write_csv(rows, csv_output)
    write_plot(rows, total_annotations=total_annotations, output_path=plot_output, title=args.title)

    print(f"Wrote CSV: {csv_output}")
    print(f"Wrote plot: {plot_output}")
    print(f"Total annotations: {total_annotations}")
    missing = [row["category_label"] for row in rows if row["count"] == 0]
    print(f"Missing categories: {missing if missing else 'None'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
