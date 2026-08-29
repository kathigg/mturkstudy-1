from __future__ import annotations

import csv
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
COUNTS_CSV = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "model_gold_miss_heatmap_npl_inclusive_counts.csv"
)
LONG_CSV = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "model_gold_miss_severity_summary.csv"
)
OUT_DIR = REPO / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/figures"
PNG_PATH = OUT_DIR / "model_misses_vs_gold_by_severity_npl_inclusive.png"


SUBCATEGORY_ORDER = [
    "no polarizing language",
    "exaggeration",
    "casual oversimplification",
    "doubt",
    "bandwagon",
    "slogans",
    "scapegoating",
    "name-calling",
    "demonization",
]

DISPLAY_LABELS = {
    "no polarizing language": "NPL",
    "casual oversimplification": "casual\noversimp.",
    "name-calling": "name-\ncalling",
}

GOLD_COUNTS = {
    "no polarizing language": 16,
    "exaggeration": 18,
    "casual oversimplification": 2,
    "doubt": 10,
    "bandwagon": 1,
    "slogans": 6,
    "scapegoating": 2,
    "name-calling": 26,
    "demonization": 5,
}


def html_escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def read_counts() -> list[dict[str, str]]:
    with COUNTS_CSV.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summarize(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    model_count = len(rows)
    out = []
    for severity, subcategory in enumerate(SUBCATEGORY_ORDER):
        gold_count = GOLD_COUNTS[subcategory]
        total_misses = sum(int(row.get(subcategory, 0) or 0) for row in rows)
        avg_misses = total_misses / model_count if model_count else 0.0
        miss_rate = total_misses / (gold_count * model_count) if gold_count and model_count else 0.0
        out.append(
            {
                "severity_rank": severity,
                "subcategory": subcategory,
                "gold_count": gold_count,
                "model_configurations": model_count,
                "total_ai_misses": total_misses,
                "avg_ai_misses_per_model": round(avg_misses, 3),
                "miss_rate_across_model_opportunities": round(miss_rate, 3),
            }
        )
    return out


def write_summary(rows: list[dict[str, Any]]) -> None:
    LONG_CSV.parent.mkdir(parents=True, exist_ok=True)
    with LONG_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def scale(value: float, domain_max: float, range_max: float) -> float:
    if domain_max <= 0:
        return 0.0
    return value / domain_max * range_max


def make_svg(rows: list[dict[str, Any]], svg_path: Path) -> tuple[int, int]:
    width = 1120
    height = 650
    left = 82
    right = 72
    top = 82
    bottom = 135
    plot_w = width - left - right
    plot_h = height - top - bottom
    group_w = plot_w / len(rows)
    bar_w = 24
    max_count = max(max(row["gold_count"], row["avg_ai_misses_per_model"]) for row in rows)
    y_max = 28 if max_count <= 26 else max_count * 1.08

    def y_for_count(value: float) -> float:
        return top + plot_h - scale(value, y_max, plot_h)

    def y_for_rate(value: float) -> float:
        return top + plot_h - scale(value, 1.0, plot_h)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Helvetica,Arial,sans-serif}.title{font-size:19px;font-weight:700;fill:#102033}.sub{font-size:12px;fill:#4b5d72}.axis{font-size:11px;fill:#2a3645}.label{font-size:11px;fill:#1c2b3a}.value{font-size:10px;font-weight:700;fill:#1c2b3a}.legend{font-size:12px;fill:#1c2b3a}</style>',
        '<text class="title" x="40" y="34">AI misses versus human gold standard by severity</text>',
        '<text class="sub" x="40" y="55">NPL-inclusive span/paragraph matching. Bars use a linear count scale; orange line is miss rate across model opportunities.</text>',
    ]

    # Plot frame and grid.
    parts.append(f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#c9d7e8" stroke-width="1"/>')
    for tick in range(0, 29, 7):
        y = y_for_count(tick)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#e8eef6" stroke-width="1"/>')
        parts.append(f'<text class="axis" text-anchor="end" x="{left - 10}" y="{y + 4:.1f}">{tick}</text>')
    parts.append(f'<text class="axis" text-anchor="middle" transform="translate(22 {top + plot_h / 2:.1f}) rotate(-90)">Annotation count</text>')

    # Right miss-rate axis.
    for tick in [0, 0.25, 0.5, 0.75, 1.0]:
        y = y_for_rate(tick)
        parts.append(f'<text class="axis" x="{left + plot_w + 10}" y="{y + 4:.1f}">{tick:.0%}</text>')
    parts.append(
        f'<text class="axis" text-anchor="middle" transform="translate({width - 20} {top + plot_h / 2:.1f}) rotate(90)">Miss rate</text>'
    )

    line_points = []
    for i, row in enumerate(rows):
        center = left + i * group_w + group_w / 2
        gold = float(row["gold_count"])
        avg = float(row["avg_ai_misses_per_model"])
        rate = float(row["miss_rate_across_model_opportunities"])

        gold_h = scale(gold, y_max, plot_h)
        avg_h = scale(avg, y_max, plot_h)
        gold_x = center - bar_w - 3
        avg_x = center + 3
        gold_y = top + plot_h - gold_h
        avg_y = top + plot_h - avg_h

        parts.append(f'<rect x="{gold_x:.1f}" y="{gold_y:.1f}" width="{bar_w}" height="{gold_h:.1f}" fill="#9fc5f8"/>')
        parts.append(f'<rect x="{avg_x:.1f}" y="{avg_y:.1f}" width="{bar_w}" height="{avg_h:.1f}" fill="#1f5fae"/>')
        parts.append(f'<text class="value" text-anchor="middle" x="{gold_x + bar_w / 2:.1f}" y="{gold_y - 5:.1f}">{int(gold)}</text>')
        parts.append(f'<text class="value" text-anchor="middle" x="{avg_x + bar_w / 2:.1f}" y="{avg_y - 5:.1f}">{avg:.1f}</text>')

        line_x = center
        line_y = y_for_rate(rate)
        line_points.append((line_x, line_y, rate))

        label = DISPLAY_LABELS.get(row["subcategory"], row["subcategory"])
        label_lines = label.split("\n")
        for line_idx, line in enumerate(label_lines):
            parts.append(
                f'<text class="label" text-anchor="middle" x="{center:.1f}" y="{top + plot_h + 26 + line_idx * 13}">{html_escape(line)}</text>'
            )
        parts.append(f'<text class="axis" text-anchor="middle" x="{center:.1f}" y="{top + plot_h + 66}">rank {row["severity_rank"]}</text>')

    # Miss-rate line.
    points_attr = " ".join(f"{x:.1f},{y:.1f}" for x, y, _rate in line_points)
    parts.append(f'<polyline points="{points_attr}" fill="none" stroke="#f28e2b" stroke-width="3"/>')
    for x, y, rate in line_points:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#f28e2b" stroke="#ffffff" stroke-width="1.5"/>')
        parts.append(f'<text class="value" text-anchor="middle" x="{x:.1f}" y="{y - 10:.1f}">{rate:.0%}</text>')

    # Legend.
    legend_y = height - 42
    parts.extend(
        [
            f'<rect x="{left}" y="{legend_y}" width="16" height="16" fill="#9fc5f8"/>',
            f'<text class="legend" x="{left + 24}" y="{legend_y + 13}">Human gold count</text>',
            f'<rect x="{left + 180}" y="{legend_y}" width="16" height="16" fill="#1f5fae"/>',
            f'<text class="legend" x="{left + 204}" y="{legend_y + 13}">Average AI misses per model/config</text>',
            f'<line x1="{left + 460}" y1="{legend_y + 8}" x2="{left + 500}" y2="{legend_y + 8}" stroke="#f28e2b" stroke-width="3"/>',
            f'<circle cx="{left + 480}" cy="{legend_y + 8}" r="5" fill="#f28e2b" stroke="#ffffff" stroke-width="1.5"/>',
            f'<text class="legend" x="{left + 510}" y="{legend_y + 13}">Miss rate</text>',
        ]
    )
    parts.append("</svg>")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return width, height


def render_png(svg_path: Path, width: int, height: int) -> None:
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.exists():
        raise RuntimeError(f"Chrome not found at {chrome}; cannot render PNG")
    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size={width},{height}",
            f"--screenshot={PNG_PATH}",
            svg_path.as_uri(),
        ],
        check=True,
    )


def main() -> int:
    rows = read_counts()
    summary = summarize(rows)
    write_summary(summary)
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as handle:
        temp_svg = Path(handle.name)
    try:
        width, height = make_svg(summary, temp_svg)
        render_png(temp_svg, width, height)
    finally:
        temp_svg.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "model_configurations": len(rows),
                "summary_csv": str(LONG_CSV),
                "figure": str(PNG_PATH),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
