from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

import src.dataset_comparison_scripts.run_decision_point_adjudication as dp  # noqa: E402


GOLD_JSON = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "consolidated_bagozzi_inhouse_overlap_gold_with_conservative_npl_paragraph_spans.json"
)
NPL_ANALYSIS_ROOT = REPO / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/npl_prompt_comparison"
NPL_OUTPUT_ROOT = REPO / "src/llm_annotation_results/2-20/npl_prompt_comparison"
OUT_DIR = REPO / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/figures"
MISS_COUNTS_CSV = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "model_gold_miss_heatmap_npl_inclusive_counts.csv"
)
MISS_LONG_CSV = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "model_gold_miss_heatmap_npl_inclusive_long.csv"
)
HEATMAP_PNG = OUT_DIR / "model_gold_miss_heatmap_npl_inclusive.png"
OVERALL_HEATMAP_PNG = OUT_DIR / "model_gold_miss_heatmap_npl_inclusive_overall_ranked.png"


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

PROMPT_LABELS = {
    "prompt_1_default_original": "P1 default",
    "prompt_2_dr_bagozzi": "P2 Bagozzi",
    "prompt_3_precision_short_spans": "P3 short spans",
    "prompt_4_boundary_examples_precision": "P4 boundary",
    "prompt_5_human_aligned_precision_recall": "P5 human aligned",
    "Prompt 1: default original": "P1 default",
    "Prompt 2: Dr. Bagozzi": "P2 Bagozzi",
    "Prompt 3: precision short spans": "P3 short spans",
    "Prompt 4: boundary examples precision": "P4 boundary",
}

MODEL_LABELS = {
    "openai_gpt_5_1": "GPT-5.1",
    "gemini_gemini_3_1_pro_preview": "Gemini Pro",
    "claude_claude_sonnet_5": "Claude Sonnet",
    "openai_gpt_5_mini": "GPT-5 mini",
    "gemini_gemini_3_1_flash_lite": "Gemini Flash",
    "claude_claude_haiku_4_5": "Claude Haiku",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def prompt_label(stem_or_name: str) -> str:
    return PROMPT_LABELS.get(stem_or_name, stem_or_name.replace("_", " "))


def model_label(run_dir_name: str) -> str:
    return MODEL_LABELS.get(run_dir_name, run_dir_name.replace("_", " "))


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def html_escape(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "..."


def prediction_specs() -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []

    # Strong single-model outputs: 5 prompts x 3 model families.
    for root in sorted(NPL_OUTPUT_ROOT.glob("prompt_*_strong_single_models")):
        prompt_stem = root.name.removesuffix("_strong_single_models")
        for run_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            final_json = run_dir / "final_annotations.json"
            raw_csv = run_dir / "raw_results.csv"
            if not final_json.exists() or not raw_csv.exists():
                continue
            rows = read_csv_dicts(raw_csv)
            if len(rows) != 27:
                continue
            specs.append(
                {
                    "family": "strong single",
                    "system": f"{model_label(run_dir.name)} - {prompt_label(prompt_stem)}",
                    "path": str(final_json),
                }
            )

    # Small single-model outputs from the existing NPL-inclusive summary.
    metrics_csv = NPL_ANALYSIS_ROOT / "npl_inclusive_prompt_model_comparison_metrics.csv"
    for row in read_csv_dicts(metrics_csv):
        path = Path(row["prediction_path"])
        if not path.exists():
            continue
        specs.append(
            {
                "family": "small single",
                "system": f"{row['model']} - {prompt_label(row['prompt'])}",
                "path": str(path),
            }
        )

    # OG whole-article adjudication setup: 5 prompts.
    og_root = NPL_OUTPUT_ROOT / "adjudication_prompt_1_to_5"
    for run_dir in sorted(og_root.glob("prompt_*_temp0p0_run1")):
        final_json = run_dir / "final_annotations.json"
        raw_csv = run_dir / "raw_results.csv"
        if not final_json.exists() or not raw_csv.exists():
            continue
        rows = read_csv_dicts(raw_csv)
        if len(rows) != 27:
            continue
        prompt_stem = run_dir.name.removesuffix("_temp0p0_run1")
        specs.append(
            {
                "family": "OG adjudication",
                "system": f"OG adj - {prompt_label(prompt_stem)}",
                "path": str(final_json),
            }
        )

    # Saved full decision-point output.
    decision_full = REPO / "src/llm_annotation_results/2-20/decision_point_adjudication_v1/final_annotations.json"
    if decision_full.exists():
        specs.append(
            {
                "family": "decision point",
                "system": "Decision point - full",
                "path": str(decision_full),
            }
        )

    # Reconstruct decision-point ablations so the heatmap includes the best-performing setup.
    specs.extend(decision_point_ablation_specs())

    # Keep first occurrence of any repeated label/path pair.
    seen: set[tuple[str, str]] = set()
    out = []
    for spec in specs:
        key = (spec["system"], spec["path"])
        if key in seen:
            continue
        seen.add(key)
        out.append(spec)
    return out


def decision_point_ablation_specs() -> list[dict[str, str]]:
    out_dir = REPO / "src/llm_annotation_results/2-20/decision_point_adjudication_v1/ablations_for_heatmap"
    out_dir.mkdir(parents=True, exist_ok=True)

    articles = dp.load_articles(dp.DEFAULT_INPUT)
    article_titles = {article.norm_title for article in articles}
    gold_articles = load_json(GOLD_JSON)
    candidate_specs = dp.existing_specs(dp.DEFAULT_CANDIDATE_SOURCES, None)
    label_specs = dp.existing_specs(dp.DEFAULT_LABEL_SOURCES, None)

    candidates: list[dp.Candidate] = []
    for spec in candidate_specs:
        candidates.extend(dp.load_candidates_from_source(spec, article_titles))
    clusters = dp.cluster_candidates(candidates)
    dp.apply_source_votes(clusters, candidate_specs)

    label_candidates: list[dp.Candidate] = []
    for spec in label_specs:
        label_candidates.extend(dp.load_candidates_from_source(spec, article_titles))

    threshold_by_title, _ = dp.select_thresholds(
        articles,
        clusters,
        label_candidates,
        gold_articles,
        thresholds=dp.THRESHOLDS,
        fixed_threshold=0.5,
        auto_threshold=True,
    )

    outputs: list[dict[str, str]] = []
    ablations = [
        ("Decision point - candidate union", {"*": -1.0}, False),
        ("Decision point - binary filter", threshold_by_title, False),
    ]
    for label, thresholds, use_label_refinement in ablations:
        articles_out = dp.materialize_final_articles(
            articles,
            clusters,
            threshold_by_title=thresholds,
            label_candidates=label_candidates if use_label_refinement else [],
            use_label_refinement=use_label_refinement,
        )
        path = out_dir / f"{slug(label)}.json"
        path.write_text(json.dumps(articles_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        outputs.append({"family": "decision point", "system": label, "path": str(path)})
    return outputs


def subcategory_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    counts = {subcategory: 0 for subcategory in SUBCATEGORY_ORDER}
    for article in articles:
        for ann in article.get("annotations") or article.get("items") or []:
            sub = dp.canonical_subcategory(ann.get("subcategory"))
            counts.setdefault(sub, 0)
            counts[sub] += 1
    return counts


def compute_misses(predicted_articles: list[dict[str, Any]], gold_articles: list[dict[str, Any]]) -> dict[str, Any]:
    pred = dp.flatten_articles(predicted_articles, include_npl=True)
    gold = dp.flatten_articles(gold_articles, include_npl=True)
    titles = sorted(gold)

    missed_by_subcategory = {subcategory: 0 for subcategory in SUBCATEGORY_ORDER}
    matched_total = 0
    prediction_total = 0
    gold_total = 0

    for title in titles:
        pred_article = pred.get(title, {"title": gold[title]["title"], "annotations": []})
        gold_article = gold[title]
        pred_annotations = pred_article["annotations"]
        gold_annotations = gold_article["annotations"]
        pairs, _unmatched_pred, unmatched_gold = dp.greedy_match(
            pred_annotations,
            gold_annotations,
            lambda p, g, t=title: dp.npl_aware_match(p, g, t),
        )
        matched_total += len(pairs)
        prediction_total += len(pred_annotations)
        gold_total += len(gold_annotations)
        for gold_idx in unmatched_gold:
            sub = dp.canonical_subcategory(gold_annotations[gold_idx].get("subcategory"))
            missed_by_subcategory.setdefault(sub, 0)
            missed_by_subcategory[sub] += 1

    return {
        "missed_by_subcategory": missed_by_subcategory,
        "matched_total": matched_total,
        "prediction_total": prediction_total,
        "gold_total": gold_total,
        "missed_total": gold_total - matched_total,
    }


def write_csvs(rows: list[dict[str, Any]], gold_counts: dict[str, int]) -> None:
    MISS_COUNTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "family",
        "system",
        "prediction_total",
        "gold_total",
        "matched_total",
        "missed_total",
        "miss_rate",
        "polarization_precision",
        "polarization_recall",
        "polarization_f1",
    ] + SUBCATEGORY_ORDER
    with MISS_COUNTS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    with MISS_LONG_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "family",
                "system",
                "subcategory",
                "gold_count",
                "missed_count",
                "miss_rate",
            ],
        )
        writer.writeheader()
        for row in rows:
            for subcategory in SUBCATEGORY_ORDER:
                total = gold_counts.get(subcategory, 0)
                missed = int(row.get(subcategory, 0))
                writer.writerow(
                    {
                        "family": row["family"],
                        "system": row["system"],
                        "subcategory": subcategory,
                        "gold_count": total,
                        "missed_count": missed,
                        "miss_rate": round(missed / total, 3) if total else 0.0,
                    }
                )


def color_for_rate(rate: float) -> str:
    # Three-stop color ramp: near-white -> orange -> deep red.
    stops = [
        (0.0, (255, 247, 236)),
        (0.5, (253, 141, 60)),
        (1.0, (127, 0, 0)),
    ]
    rate = min(1.0, max(0.0, rate))
    for (lo, lo_rgb), (hi, hi_rgb) in zip(stops, stops[1:]):
        if lo <= rate <= hi:
            t = (rate - lo) / (hi - lo) if hi > lo else 0.0
            rgb = tuple(round(lo_rgb[i] + t * (hi_rgb[i] - lo_rgb[i])) for i in range(3))
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    rgb = stops[-1][1]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def text_color_for_rate(rate: float) -> str:
    return "#ffffff" if rate >= 0.55 else "#202020"


def make_heatmap(
    rows: list[dict[str, Any]],
    gold_counts: dict[str, int],
    out_path: Path,
    *,
    sort_mode: str,
) -> tuple[int, int]:
    if sort_mode == "overall":
        rows = sorted(
            rows,
            key=lambda row: (
                -float(row["polarization_f1"]),
                -float(row["polarization_recall"]),
                -float(row["polarization_precision"]),
                row["system"],
            ),
        )
        title = "Gold misses by model/configuration, ranked by overall performance"
        sort_note = "Rows are sorted by NPL-inclusive polarization F1, so higher overall-performing systems appear first."
    elif sort_mode == "misses":
        rows = sorted(rows, key=lambda row: (row["miss_rate"], row["missed_total"], row["system"]))
        title = "Gold misses by model/configuration"
        sort_note = "Rows are sorted from fewer missed gold annotations to more missed gold annotations."
    else:
        raise ValueError(f"Unknown sort mode: {sort_mode}")

    left = 390
    top = 132
    cell_w = 92
    cell_h = 24
    right = 55
    bottom = 92
    width = left + len(SUBCATEGORY_ORDER) * cell_w + right
    height = top + len(rows) * cell_h + bottom

    x_labels = {
        "no polarizing language": "NPL",
        "casual oversimplification": "casual oversimp.",
    }

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Helvetica,Arial,sans-serif}.title{font-size:18px;font-weight:700}.subtitle{font-size:12px;fill:#555}.axis{font-size:11px;fill:#222}.row{font-size:10px;fill:#222}.cell{font-size:10px;font-weight:700}.small{font-size:10px;fill:#555}</style>',
        f'<text class="title" x="24" y="32">{html_escape(title)}</text>',
        '<text class="subtitle" x="24" y="52">NPL-inclusive matching. A miss is an unmatched gold annotation; color shows miss rate within each gold subcategory, and cell text shows missed count.</text>',
        f'<text class="subtitle" x="24" y="72">{html_escape(sort_note)}</text>',
    ]

    # Column labels.
    for j, subcategory in enumerate(SUBCATEGORY_ORDER):
        x = left + j * cell_w + cell_w / 2
        label = x_labels.get(subcategory, subcategory)
        total = gold_counts.get(subcategory, 0)
        parts.append(f'<text class="axis" text-anchor="middle" x="{x:.1f}" y="104">{html_escape(label)}</text>')
        parts.append(f'<text class="small" text-anchor="middle" x="{x:.1f}" y="120">(n={total})</text>')

    # Row labels and cells.
    for i, row in enumerate(rows):
        y = top + i * cell_h
        label = truncate(str(row["system"]), 58)
        miss_rate = float(row["miss_rate"])
        precision = float(row["polarization_precision"])
        recall = float(row["polarization_recall"])
        f1 = float(row["polarization_f1"])
        if sort_mode == "overall":
            metric_text = f"F1={f1:.3f} P={precision:.3f} R={recall:.3f}"
        else:
            metric_text = f"miss={int(row['missed_total'])}/{int(row['gold_total'])} ({miss_rate:.0%})"
        parts.append(
            f'<text class="row" text-anchor="end" x="{left - 12}" y="{y + 16}">'
            f'{html_escape(label)}'
            f'  <tspan fill="#777">{html_escape(metric_text)}</tspan>'
            "</text>"
        )
        for j, subcategory in enumerate(SUBCATEGORY_ORDER):
            missed = int(row.get(subcategory, 0))
            total = gold_counts.get(subcategory, 0)
            rate = missed / total if total else 0.0
            x = left + j * cell_w
            color = color_for_rate(rate)
            text_color = text_color_for_rate(rate)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{color}" stroke="#ffffff" stroke-width="1"/>'
            )
            parts.append(
                f'<text class="cell" text-anchor="middle" dominant-baseline="middle" '
                f'x="{x + cell_w / 2:.1f}" y="{y + cell_h / 2 + 1:.1f}" fill="{text_color}">{missed}</text>'
            )

    # Legend.
    legend_x = left
    legend_y = height - 46
    legend_w = 260
    steps = 80
    for idx in range(steps):
        rate = idx / (steps - 1)
        x = legend_x + idx * (legend_w / steps)
        parts.append(
            f'<rect x="{x:.2f}" y="{legend_y}" width="{legend_w / steps + 0.5:.2f}" height="12" fill="{color_for_rate(rate)}"/>'
        )
    parts.append(f'<text class="small" x="{legend_x}" y="{legend_y + 30}">0% miss rate</text>')
    parts.append(f'<text class="small" text-anchor="end" x="{legend_x + legend_w}" y="{legend_y + 30}">100% miss rate</text>')
    parts.append(f'<text class="small" x="{legend_x + legend_w + 18}" y="{legend_y + 10}">Color scale</text>')
    parts.append("</svg>")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return width, height


def render_png(svg_path: Path, png_path: Path, width: int, height: int) -> None:
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
            f"--screenshot={png_path}",
            svg_path.as_uri(),
        ],
        check=True,
    )


def main() -> int:
    gold_articles = load_json(GOLD_JSON)
    gold_counts = subcategory_counts(gold_articles)
    specs = prediction_specs()

    rows: list[dict[str, Any]] = []
    for spec in specs:
        predicted_articles = load_json(Path(spec["path"]))
        miss = compute_misses(predicted_articles, gold_articles)
        row = {
            "family": spec["family"],
            "system": spec["system"],
            "prediction_total": miss["prediction_total"],
            "gold_total": miss["gold_total"],
            "matched_total": miss["matched_total"],
            "missed_total": miss["missed_total"],
            "miss_rate": round(miss["missed_total"] / miss["gold_total"], 3) if miss["gold_total"] else 0.0,
        }
        precision = miss["matched_total"] / miss["prediction_total"] if miss["prediction_total"] else 0.0
        recall = miss["matched_total"] / miss["gold_total"] if miss["gold_total"] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        row.update(
            {
                "polarization_precision": round(precision, 3),
                "polarization_recall": round(recall, 3),
                "polarization_f1": round(f1, 3),
            }
        )
        row.update({subcategory: miss["missed_by_subcategory"].get(subcategory, 0) for subcategory in SUBCATEGORY_ORDER})
        rows.append(row)

    write_csvs(rows, gold_counts)
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as handle:
        heatmap_temp_svg = Path(handle.name)
    try:
        width, height = make_heatmap(rows, gold_counts, heatmap_temp_svg, sort_mode="misses")
        render_png(heatmap_temp_svg, HEATMAP_PNG, width, height)
    finally:
        heatmap_temp_svg.unlink(missing_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as handle:
        overall_temp_svg = Path(handle.name)
    try:
        width, height = make_heatmap(rows, gold_counts, overall_temp_svg, sort_mode="overall")
        render_png(overall_temp_svg, OVERALL_HEATMAP_PNG, width, height)
    finally:
        overall_temp_svg.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "models_compared": len(rows),
                "gold_counts": gold_counts,
                "heatmap": str(HEATMAP_PNG),
                "overall_ranked_heatmap": str(OVERALL_HEATMAP_PNG),
                "counts_csv": str(MISS_COUNTS_CSV),
                "long_csv": str(MISS_LONG_CSV),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
