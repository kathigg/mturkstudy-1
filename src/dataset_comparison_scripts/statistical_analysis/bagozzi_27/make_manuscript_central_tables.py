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
    build_specs,
    load_json,
)


ANALYSIS_ROOT = REPO / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27"
OUT_DIR = ANALYSIS_ROOT / "manuscript_tables"
FIG_DIR = ANALYSIS_ROOT / "figures"

EXPERT_REFERENCE = ANALYSIS_ROOT / "bagozzi_27_human_min_one_gold_standard_output.json"
INHOUSE_REFERENCE = ANALYSIS_ROOT / "final_inhouse_adjudicated_gold_standard_output.json"
INTERSECTION_REFERENCE = ANALYSIS_ROOT / "consolidated_bagozzi_inhouse_overlap_gold_with_conservative_npl_paragraph_spans.json"
BEST_MODEL_PATH = (
    REPO
    / "src/llm_annotation_results/2-20/decision_point_adjudication_v1/"
    / "ablations_for_heatmap/decision_point_binary_filter.json"
)

TABLE1_CSV = OUT_DIR / "table1_model_prompt_performance_matched_agreement.csv"
TABLE1_MD = OUT_DIR / "table1_model_prompt_performance_matched_agreement.md"
TABLE1_TEX = OUT_DIR / "table1_model_prompt_performance_matched_agreement.tex"
TABLE1_PNG = FIG_DIR / "table1_model_prompt_performance_matched_agreement.png"

TABLE2_CSV = OUT_DIR / "table2_best_model_alignment_by_reference_set.csv"
TABLE2_MD = OUT_DIR / "table2_best_model_alignment_by_reference_set.md"
TABLE2_TEX = OUT_DIR / "table2_best_model_alignment_by_reference_set.tex"
TABLE2_PNG = FIG_DIR / "table2_best_model_alignment_by_reference_set.png"


def html_escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def latex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def display_architecture(value: str) -> str:
    return "single model" if value.startswith("single ") else value


def fmt(value: float) -> str:
    return f"{value:.3f}"


def wrap_lines(value: str, width: int, max_lines: int = 2) -> list[str]:
    lines: list[str] = []
    for chunk in str(value).splitlines() or [""]:
        lines.extend(textwrap.wrap(chunk, width=width, break_long_words=False) or [""])
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [lines[max_lines - 1].rstrip(" .") + "..."]
    return lines


def metric_triplet(value: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {
        f"{prefix}_precision": value["precision"],
        f"{prefix}_recall": value["recall"],
        f"{prefix}_f1": value["f1"],
    }


def reference_counts(reference: list[dict[str, Any]]) -> dict[str, int]:
    polarizing = 0
    npl = 0
    for article in reference:
        for annotation in article.get("annotations") or article.get("items") or []:
            if dp.is_npl(annotation):
                npl += 1
            else:
                polarizing += 1
    return {"polarizing": polarizing, "npl": npl, "total": polarizing + npl}


def table1_rows() -> list[dict[str, Any]]:
    gold = load_json(INTERSECTION_REFERENCE)
    rows: list[dict[str, Any]] = []
    for spec in build_specs():
        predicted = load_json(Path(spec["prediction_path"]))
        metrics = dp.compare_predictions(predicted, gold, include_npl=True, title_policy="gold_nonempty")
        polarization = metrics["polarization_match"]
        labels = metrics["label_agreement_on_matched"]
        row = {
            "architecture": display_architecture(spec["architecture"]),
            "model_config": spec["model"],
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
            row["model_config"],
            row["system_prompt"],
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def table2_rows() -> list[dict[str, Any]]:
    predicted = load_json(BEST_MODEL_PATH)
    refs = [
        (
            "Expert reference",
            "Dr. Bagozzi full set",
            EXPERT_REFERENCE,
        ),
        (
            "In-house reference",
            "Final adjudicated in-house full set",
            INHOUSE_REFERENCE,
        ),
        (
            "Consensus intersection",
            "Spans where expert and in-house overlap; conservative NPL paragraphs",
            INTERSECTION_REFERENCE,
        ),
    ]
    rows: list[dict[str, Any]] = []
    for reference_set, definition, path in refs:
        gold = load_json(path)
        counts = reference_counts(gold)
        metrics = dp.compare_predictions(predicted, gold, include_npl=True, title_policy="gold_nonempty")
        polarization = metrics["polarization_match"]
        labels = metrics["label_agreement_on_matched"]
        row: dict[str, Any] = {
            "reference_set": reference_set,
            "definition": definition,
            "titles_compared": metrics["titles_compared"],
            "reference_total": counts["total"],
            "reference_polarizing": counts["polarizing"],
            "reference_npl": counts["npl"],
            "model_units_compared": polarization["prediction_total"],
            "matched_units": labels["matched"],
        }
        row.update(metric_triplet(polarization, "polarization"))
        row["category_agreement_on_matched"] = labels["category"]
        row["subcategory_agreement_on_matched"] = labels["subcategory"]
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
    rows.sort(key=lambda row: -float(row["mean_score"]))
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> None:
    lines = [
        "| " + " | ".join(label for _key, label in columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    maxima = metric_maxima(rows)
    for row in rows:
        values: list[str] = []
        for key, _label in columns:
            value = row[key]
            if isinstance(value, float):
                text = fmt(value)
                if key in maxima and float(value) == maxima[key]:
                    text = f"**{text}**"
            else:
                text = str(value)
            values.append(text)
        lines.append("| " + " | ".join(values) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latex(
    path: Path,
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
    *,
    caption: str,
    label: str,
) -> None:
    maxima = metric_maxima(rows)
    col_spec = "rlllrrrrr" if len(columns) == 9 else "rllrrrrrrrrr"
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        f"\\caption{{{latex_escape(caption)}}}",
        f"\\label{{{latex_escape(label)}}}",
        r"\small",
        f"\\begin{{tabular}}{{{col_spec}}}",
        r"\toprule",
        " & ".join(latex_escape(label) for _key, label in columns) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        values: list[str] = []
        for key, _label in columns:
            value = row[key]
            if isinstance(value, float):
                text = fmt(value)
                if key in maxima and float(value) == maxima[key]:
                    text = rf"\textbf{{{text}}}"
            else:
                text = latex_escape(value)
            values.append(text)
        lines.append(" & ".join(values) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def metric_maxima(rows: list[dict[str, Any]]) -> dict[str, float]:
    metric_keys = [
        "polarization_f1",
        "category_agreement_on_matched",
        "subcategory_agreement_on_matched",
        "mean_score",
    ]
    return {key: max(float(row[key]) for row in rows) for key in metric_keys if key in rows[0]}


def draw_table_svg(
    path: Path,
    rows: list[dict[str, Any]],
    columns: list[dict[str, Any]],
    *,
    title: str,
    subtitle: str,
    footer: str,
    width: int,
    row_h: int,
) -> tuple[int, int]:
    title_h = 92
    header_h = 44
    footer_h = 40
    margin_x = 34
    table_w = sum(col["width"] for col in columns)
    height = title_h + header_h + row_h * len(rows) + footer_h
    maxima = metric_maxima(rows)

    x_positions = []
    cursor = margin_x
    for column in columns:
        x_positions.append(cursor)
        cursor += column["width"]

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
            ".metric{font-size:12px;font-weight:700;fill:#132238}"
            ".footer{font-size:10px;fill:#536579}"
            "</style>"
        ),
        f'<text class="title" x="{margin_x}" y="34">{html_escape(title)}</text>',
        f'<text class="subtitle" x="{margin_x}" y="58">{html_escape(subtitle)}</text>',
    ]

    table_x = margin_x
    table_y = title_h
    parts.append(f'<rect x="{table_x}" y="{table_y}" width="{table_w}" height="{header_h}" fill="#245a9a"/>')
    for x, column in zip(x_positions, columns):
        anchor = column.get("anchor", "start")
        text_x = x + (column["width"] / 2 if anchor == "middle" else column["width"] - 10 if anchor == "end" else 10)
        parts.append(
            f'<text class="header" text-anchor="{anchor}" x="{text_x:.1f}" y="{table_y + 27}">'
            f'{html_escape(column["label"])}</text>'
        )

    for row_idx, row in enumerate(rows):
        y = table_y + header_h + row_idx * row_h
        fill = "#eaf3ff" if row_idx % 2 == 0 else "#ffffff"
        if row.get("rank") == 1:
            fill = "#dff0ff"
        parts.append(f'<rect x="{table_x}" y="{y}" width="{table_w}" height="{row_h}" fill="{fill}"/>')
        parts.append(
            f'<line x1="{table_x}" y1="{y + row_h}" x2="{table_x + table_w}" y2="{y + row_h}" stroke="#d8e2ee" stroke-width="1"/>'
        )
        for x, column in zip(x_positions, columns):
            key = column["key"]
            value = row[key]
            anchor = column.get("anchor", "start")
            text_x = x + (column["width"] / 2 if anchor == "middle" else column["width"] - 10 if anchor == "end" else 10)
            css = "metric" if isinstance(value, (int, float)) else "cell"
            highlight = key in maxima and isinstance(value, float) and float(value) == maxima[key]
            if highlight:
                parts.append(
                    f'<rect x="{x + 3}" y="{y + 5}" width="{column["width"] - 6}" height="{row_h - 10}" fill="#ffe89a" opacity="0.72"/>'
                )
            if isinstance(value, float):
                text = fmt(value)
                parts.append(
                    f'<text class="{css}" text-anchor="{anchor}" x="{text_x:.1f}" y="{y + row_h / 2 + 5:.1f}">{text}</text>'
                )
            elif key in {"model_config", "system_prompt", "definition"}:
                lines = wrap_lines(str(value), column.get("wrap", 42), max_lines=column.get("max_lines", 2))
                first_y = y + row_h / 2 - 5 if len(lines) > 1 else y + row_h / 2 + 5
                for line_idx, line in enumerate(lines):
                    parts.append(
                        f'<text class="{css}" text-anchor="{anchor}" x="{text_x:.1f}" y="{first_y + line_idx * 13:.1f}">'
                        f"{html_escape(line)}</text>"
                    )
            else:
                parts.append(
                    f'<text class="{css}" text-anchor="{anchor}" x="{text_x:.1f}" y="{y + row_h / 2 + 5:.1f}">'
                    f"{html_escape(value)}</text>"
                )

    parts.append(f'<text class="footer" x="{margin_x}" y="{height - 16}">{html_escape(footer)}</text>')
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return width, height


def render_png(svg_path: Path, png_path: Path, width: int, height: int) -> None:
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.exists():
        raise RuntimeError(f"Chrome renderer not found at {chrome}")
    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size={width},{height}",
            f"--screenshot={png_path}",
            svg_path.as_uri(),
        ],
        check=True,
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    rows1 = table1_rows()
    rows2 = table2_rows()

    table1_columns = [
        ("rank", "Rank"),
        ("architecture", "Architecture"),
        ("model_config", "Model/config"),
        ("system_prompt", "System prompt/configuration"),
        ("matched_units", "Matched units"),
        ("polarization_f1", "Polarization F1"),
        ("category_agreement_on_matched", "Category agreement"),
        ("subcategory_agreement_on_matched", "Subcategory agreement"),
        ("mean_score", "Mean"),
    ]
    table2_columns = [
        ("rank", "Rank"),
        ("reference_set", "Reference set"),
        ("definition", "Definition"),
        ("reference_total", "Gold units"),
        ("reference_polarizing", "Polarizing"),
        ("reference_npl", "NPL"),
        ("matched_units", "Matched units"),
        ("polarization_precision", "Pol. precision"),
        ("polarization_recall", "Pol. recall"),
        ("polarization_f1", "Pol. F1"),
        ("category_agreement_on_matched", "Category agreement"),
        ("subcategory_agreement_on_matched", "Subcategory agreement"),
        ("mean_score", "Mean"),
    ]

    write_csv(TABLE1_CSV, rows1)
    write_csv(TABLE2_CSV, rows2)
    write_markdown(TABLE1_MD, rows1, table1_columns)
    write_markdown(TABLE2_MD, rows2, table2_columns)
    write_latex(
        TABLE1_TEX,
        rows1,
        table1_columns,
        caption=(
            "Model and prompt performance against the consolidated human consensus reference. "
            "Category and subcategory agreement are computed only for matched spans or NPL paragraphs."
        ),
        label="tab:model_prompt_performance",
    )
    write_latex(
        TABLE2_TEX,
        rows2,
        table2_columns,
        caption=(
            "Alignment of the best-performing model configuration with expert, in-house, "
            "and consensus human reference sets."
        ),
        label="tab:best_model_alignment",
    )

    table1_svg_cols = [
        {"key": "rank", "label": "Rank", "width": 52, "anchor": "middle"},
        {"key": "architecture", "label": "Architecture", "width": 145},
        {"key": "model_config", "label": "Model/config", "width": 355, "wrap": 42},
        {"key": "system_prompt", "label": "System prompt/configuration", "width": 500, "wrap": 62},
        {"key": "matched_units", "label": "Matched", "width": 88, "anchor": "end"},
        {"key": "polarization_f1", "label": "Pol. F1", "width": 92, "anchor": "end"},
        {"key": "category_agreement_on_matched", "label": "Cat. agree", "width": 108, "anchor": "end"},
        {"key": "subcategory_agreement_on_matched", "label": "Subcat. agree", "width": 126, "anchor": "end"},
        {"key": "mean_score", "label": "Mean", "width": 88, "anchor": "end"},
    ]
    width1 = 34 * 2 + sum(col["width"] for col in table1_svg_cols)
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as handle:
        table1_temp_svg = Path(handle.name)
    try:
        w1, h1 = draw_table_svg(
            table1_temp_svg,
            rows1,
            table1_svg_cols,
            title="Model and Prompt Performance Against Human Consensus",
            subtitle=(
                "Ranked by mean of polarization F1, category agreement, and subcategory agreement; "
                "best metric values highlighted."
            ),
            footer="Gold reference: consolidated Dr. Bagozzi + in-house intersection with conservative NPL paragraph spans.",
            width=width1,
            row_h=38,
        )
        render_png(table1_temp_svg, TABLE1_PNG, w1, h1)
    finally:
        table1_temp_svg.unlink(missing_ok=True)

    table2_svg_cols = [
        {"key": "rank", "label": "Rank", "width": 52, "anchor": "middle"},
        {"key": "reference_set", "label": "Reference set", "width": 170},
        {"key": "definition", "label": "Definition", "width": 430, "wrap": 54, "max_lines": 2},
        {"key": "reference_total", "label": "Gold", "width": 70, "anchor": "end"},
        {"key": "reference_polarizing", "label": "Pol.", "width": 70, "anchor": "end"},
        {"key": "reference_npl", "label": "NPL", "width": 70, "anchor": "end"},
        {"key": "matched_units", "label": "Matched", "width": 82, "anchor": "end"},
        {"key": "polarization_precision", "label": "Pol. P", "width": 86, "anchor": "end"},
        {"key": "polarization_recall", "label": "Pol. R", "width": 86, "anchor": "end"},
        {"key": "polarization_f1", "label": "Pol. F1", "width": 86, "anchor": "end"},
        {"key": "category_agreement_on_matched", "label": "Cat. agree", "width": 105, "anchor": "end"},
        {"key": "subcategory_agreement_on_matched", "label": "Subcat. agree", "width": 124, "anchor": "end"},
        {"key": "mean_score", "label": "Mean", "width": 78, "anchor": "end"},
    ]
    width2 = 34 * 2 + sum(col["width"] for col in table2_svg_cols)
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as handle:
        table2_temp_svg = Path(handle.name)
    try:
        w2, h2 = draw_table_svg(
            table2_temp_svg,
            rows2,
            table2_svg_cols,
            title="Best Model Alignment Across Human Reference Sets",
            subtitle="Best configuration: Decision point binary filter. NPL-inclusive matching.",
            footer="Category/subcategory agreement is conditional on an already-matched span or NPL paragraph.",
            width=width2,
            row_h=50,
        )
        render_png(table2_temp_svg, TABLE2_PNG, w2, h2)
    finally:
        table2_temp_svg.unlink(missing_ok=True)

    print(
        json.dumps(
            {
                "table1": {
                    "csv": str(TABLE1_CSV),
                    "markdown": str(TABLE1_MD),
                    "latex": str(TABLE1_TEX),
                    "png": str(TABLE1_PNG),
                },
                "table2": {
                    "csv": str(TABLE2_CSV),
                    "markdown": str(TABLE2_MD),
                    "latex": str(TABLE2_TEX),
                    "png": str(TABLE2_PNG),
                },
                "alignment_rows": rows2,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
