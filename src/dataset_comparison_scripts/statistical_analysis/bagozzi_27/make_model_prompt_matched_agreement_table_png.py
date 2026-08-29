from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

import src.dataset_comparison_scripts.run_decision_point_adjudication as dp  # noqa: E402
from src.dataset_comparison_scripts.statistical_analysis.bagozzi_27.make_model_prompt_overall_f1_table import (  # noqa: E402
    GOLD_JSON,
    build_specs,
    load_json,
)


OUT_DIR = REPO / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/figures"
CSV_PATH = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "model_prompt_matched_agreement_table_npl_inclusive.csv"
)
PNG_PATH = OUT_DIR / "model_prompt_matched_agreement_table_npl_inclusive.png"


def html_escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def display_architecture(value: str) -> str:
    return "single model" if value.startswith("single ") else value


def metric(value: float) -> str:
    return f"{value:.3f}"


def wrap_lines(value: str, width: int, max_lines: int = 3) -> list[str]:
    lines: list[str] = []
    for chunk in str(value).splitlines() or [""]:
        lines.extend(textwrap.wrap(chunk, width=width, break_long_words=False) or [""])
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [lines[max_lines - 1].rstrip(" .") + "..."]
    return lines


def build_rows() -> list[dict[str, Any]]:
    gold = load_json(GOLD_JSON)
    rows: list[dict[str, Any]] = []
    for spec in build_specs():
        predicted = load_json(Path(spec["prediction_path"]))
        metrics = dp.compare_predictions(predicted, gold, include_npl=True, title_policy="gold_nonempty")
        polarization = metrics["polarization_match"]
        labels = metrics["label_agreement_on_matched"]
        row = {
            "architecture": display_architecture(spec["architecture"]),
            "model": spec["model"],
            "system_prompt": spec["prompt"],
            "matched_units": labels["matched"],
            "polarization_f1": polarization["f1"],
            "category_agreement_on_matched": labels["category"],
            "subcategory_agreement_on_matched": labels["subcategory"],
        }
        row["mean_score"] = round(
            (
                row["polarization_f1"]
                + row["category_agreement_on_matched"]
                + row["subcategory_agreement_on_matched"]
            )
            / 3,
            3,
        )
        rows.append(row)
    rows.sort(
        key=lambda row: (
            -float(row["mean_score"]),
            -float(row["polarization_f1"]),
            -float(row["category_agreement_on_matched"]),
            -float(row["subcategory_agreement_on_matched"]),
            row["model"],
            row["system_prompt"],
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def write_csv(rows: list[dict[str, Any]]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "architecture",
        "model",
        "system_prompt",
        "matched_units",
        "polarization_f1",
        "category_agreement_on_matched",
        "subcategory_agreement_on_matched",
        "mean_score",
    ]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{key: row[key] for key in fieldnames} for row in rows])


def make_svg(rows: list[dict[str, Any]], svg_path: Path) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    columns = [
        ("rank", "Rank", 52, "middle"),
        ("architecture", "Architecture", 145, "start"),
        ("model", "Model/config", 355, "start"),
        ("system_prompt", "System prompt", 465, "start"),
        ("matched_units", "Matched", 82, "end"),
        ("polarization_f1", "Pol. F1", 86, "end"),
        ("category_agreement_on_matched", "Cat. agree", 96, "end"),
        ("subcategory_agreement_on_matched", "Subcat. agree", 118, "end"),
        ("mean_score", "Mean", 82, "end"),
    ]
    margin_x = 34
    title_h = 96
    header_h = 44
    row_h = 38
    footer_h = 42
    table_w = sum(col[2] for col in columns)
    width = margin_x * 2 + table_w
    height = title_h + header_h + row_h * len(rows) + footer_h

    x_positions: list[int] = []
    cursor = margin_x
    for _key, _label, col_w, _anchor in columns:
        x_positions.append(cursor)
        cursor += col_w

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        (
            "<style>"
            "text{font-family:Helvetica,Arial,sans-serif;fill:#102033}"
            ".title{font-size:24px;font-weight:700}"
            ".subtitle{font-size:13px;fill:#536579}"
            ".header{font-size:12px;font-weight:700;fill:#f8fbff}"
            ".cell{font-size:11px;fill:#132238}"
            ".small{font-size:10px;fill:#536579}"
            ".metric{font-size:12px;font-weight:700;fill:#132238}"
            "</style>"
        ),
        '<text class="title" x="34" y="34">Model and Prompt Performance Against Human Gold Standard</text>',
        (
            '<text class="subtitle" x="34" y="58">'
            "Ranked by mean of polarization F1, category agreement, and subcategory agreement."
            "</text>"
        ),
        (
            '<text class="subtitle" x="34" y="78">'
            "NPL-inclusive; category/subcategory agreement is computed only for already-matched spans or NPL paragraphs."
            "</text>"
        ),
    ]

    table_x = margin_x
    table_y = title_h
    parts.append(
        f'<rect x="{table_x}" y="{table_y}" width="{table_w}" height="{header_h}" fill="#245a9a"/>'
    )

    for x, (_key, label, col_w, anchor) in zip(x_positions, columns):
        text_x = x + (col_w / 2 if anchor == "middle" else col_w - 10 if anchor == "end" else 10)
        parts.append(
            f'<text class="header" text-anchor="{anchor}" x="{text_x:.1f}" y="{table_y + 27}">'
            f"{html_escape(label)}</text>"
        )

    best_mean = max(float(row["mean_score"]) for row in rows)
    for row_idx, row in enumerate(rows):
        y = table_y + header_h + row_idx * row_h
        fill = "#eaf3ff" if row_idx % 2 == 0 else "#ffffff"
        if float(row["mean_score"]) == best_mean:
            fill = "#dff0ff"
        parts.append(f'<rect x="{table_x}" y="{y}" width="{table_w}" height="{row_h}" fill="{fill}"/>')
        parts.append(
            f'<line x1="{table_x}" y1="{y + row_h}" x2="{table_x + table_w}" y2="{y + row_h}" stroke="#d8e2ee" stroke-width="1"/>'
        )

        for x, (key, _label, col_w, anchor) in zip(x_positions, columns):
            value = row[key]
            text_x = x + (col_w / 2 if anchor == "middle" else col_w - 10 if anchor == "end" else 10)
            css = "metric" if key.endswith("f1") or key.endswith("matched") or key == "mean_score" else "cell"
            if key in {"model", "system_prompt"}:
                max_chars = 45 if key == "model" else 58
                lines = wrap_lines(str(value), max_chars, max_lines=2)
                first_y = y + 15 if len(lines) > 1 else y + 24
                for line_idx, line in enumerate(lines):
                    parts.append(
                        f'<text class="{css}" text-anchor="{anchor}" x="{text_x:.1f}" '
                        f'y="{first_y + line_idx * 13}">{html_escape(line)}</text>'
                    )
            elif isinstance(value, float):
                parts.append(
                    f'<text class="{css}" text-anchor="{anchor}" x="{text_x:.1f}" y="{y + 24}">'
                    f"{metric(value)}</text>"
                )
            else:
                parts.append(
                    f'<text class="{css}" text-anchor="{anchor}" x="{text_x:.1f}" y="{y + 24}">'
                    f"{html_escape(value)}</text>"
                )

    footer_y = height - 17
    parts.append(
        f'<text class="small" x="34" y="{footer_y}">'
        "Gold reference: consolidated Dr. Bagozzi + in-house intersection with conservative NPL paragraph spans."
        "</text>"
    )
    parts.append("</svg>")
    svg_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def render_png(svg_path: Path) -> None:
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.exists():
        raise RuntimeError(f"Chrome renderer not found at {chrome}")
    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size={1565},{1626}",
            f"--screenshot={PNG_PATH}",
            svg_path.as_uri(),
        ],
        check=True,
    )


def main() -> int:
    rows = build_rows()
    write_csv(rows)
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as handle:
        temp_svg = Path(handle.name)
    try:
        make_svg(rows, temp_svg)
        render_png(temp_svg)
    finally:
        temp_svg.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "rows": len(rows),
                "csv": str(CSV_PATH),
                "png": str(PNG_PATH),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
