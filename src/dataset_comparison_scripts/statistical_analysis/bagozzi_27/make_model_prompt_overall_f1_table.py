from __future__ import annotations

import csv
import json
import sys
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
OUTPUT_CSV = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "model_prompt_overall_f1_table_npl_inclusive.csv"
)
OUTPUT_MD = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "model_prompt_overall_f1_table_npl_inclusive.md"
)
NPL_ROOT = REPO / "src/llm_annotation_results/2-20/npl_prompt_comparison"


PROMPTS = {
    "prompt_1_default_original": "P1 default",
    "prompt_2_dr_bagozzi": "P2 Bagozzi",
    "prompt_3_precision_short_spans": "P3 short spans",
    "prompt_4_boundary_examples_precision": "P4 boundary",
    "prompt_5_human_aligned_precision_recall": "P5 human aligned",
}

SMALL_MODELS = {
    "openai_gpt_5_mini": ("OpenAI", "GPT-5 mini"),
    "gemini_gemini_3_1_flash_lite": ("Gemini", "Gemini 3.1 Flash Lite"),
    "claude_claude_haiku_4_5": ("Anthropic", "Claude Haiku 4.5"),
}

STRONG_MODELS = {
    "openai_gpt_5_1": ("OpenAI", "GPT-5.1"),
    "gemini_gemini_3_1_pro_preview": ("Gemini", "Gemini 3.1 Pro Preview"),
    "claude_claude_sonnet_5": ("Anthropic", "Claude Sonnet 5"),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_from_dir(name: str) -> str:
    for stem, label in PROMPTS.items():
        if name.startswith(stem):
            return label
    return name.replace("_", " ")


def add_spec(
    specs: list[dict[str, str]],
    *,
    architecture: str,
    provider: str,
    model: str,
    prompt: str,
    prediction_path: Path,
) -> None:
    if not prediction_path.exists():
        return
    specs.append(
        {
            "architecture": architecture,
            "provider": provider,
            "model": model,
            "prompt": prompt,
            "prediction_path": str(prediction_path),
        }
    )


def build_specs() -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []

    # Small single-model runs. Prompt 2 originally lives in a sibling output root.
    for prompt_stem, prompt_label in PROMPTS.items():
        if prompt_stem == "prompt_2_dr_bagozzi":
            base = REPO / "src/llm_annotation_results/2-20/bagozzi_intersection_single_model_dr_bagozzi_prompt"
        else:
            base = NPL_ROOT / f"{prompt_stem}_single_models"
        for model_dir, (provider, model) in SMALL_MODELS.items():
            add_spec(
                specs,
                architecture="single small model",
                provider=provider,
                model=model,
                prompt=prompt_label,
                prediction_path=base / model_dir / "final_annotations.json",
            )

    # Strong single-model runs.
    for prompt_stem, prompt_label in PROMPTS.items():
        base = NPL_ROOT / f"{prompt_stem}_strong_single_models"
        for model_dir, (provider, model) in STRONG_MODELS.items():
            add_spec(
                specs,
                architecture="single strong model",
                provider=provider,
                model=model,
                prompt=prompt_label,
                prediction_path=base / model_dir / "final_annotations.json",
            )

    # Original whole-article adjudication runs.
    adj_root = NPL_ROOT / "adjudication_prompt_1_to_5"
    for run_dir in sorted(adj_root.glob("*_temp0p0_run1")):
        add_spec(
            specs,
            architecture="OG adjudication",
            provider="multi-model",
            model="GPT-5.1 + Gemini Pro + Claude Sonnet -> Claude Opus",
            prompt=prompt_from_dir(run_dir.name.removesuffix("_temp0p0_run1")),
            prediction_path=run_dir / "final_annotations.json",
        )

    # Decision-point pipeline and ablations.
    decision_root = REPO / "src/llm_annotation_results/2-20/decision_point_adjudication_v1"
    decision_specs = [
        ("Decision point full", decision_root / "final_annotations.json"),
        ("Decision point candidate union", decision_root / "ablations_for_heatmap/decision_point_candidate_union.json"),
        ("Decision point binary filter", decision_root / "ablations_for_heatmap/decision_point_binary_filter.json"),
    ]
    for model, path in decision_specs:
        add_spec(
            specs,
            architecture="decision point",
            provider="multi-model",
            model=model,
            prompt="P5 candidates + P2 adjudication + P4 label refinement",
            prediction_path=path,
        )

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for spec in specs:
        key = spec["prediction_path"]
        if key in seen:
            continue
        seen.add(key)
        out.append(spec)
    return out


def metric_fields(metric: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {
        f"{prefix}_precision": metric["precision"],
        f"{prefix}_recall": metric["recall"],
        f"{prefix}_f1": metric["f1"],
    }


def row_for_spec(spec: dict[str, str], gold: list[dict[str, Any]]) -> dict[str, Any]:
    predicted = load_json(Path(spec["prediction_path"]))
    metrics = dp.compare_predictions(predicted, gold, include_npl=True, title_policy="gold_nonempty")
    row: dict[str, Any] = {
        "architecture": spec["architecture"],
        "provider": spec["provider"],
        "model": spec["model"],
        "prompt": spec["prompt"],
        "titles_compared": metrics["titles_compared"],
        "prediction_total": metrics["polarization_match"]["prediction_total"],
        "gold_total": metrics["polarization_match"]["gold_total"],
    }
    row.update(metric_fields(metrics["polarization_match"], "polarization"))
    row.update(metric_fields(metrics["category_match"], "category"))
    row.update(metric_fields(metrics["subcategory_match"], "subcategory"))
    row["prediction_path"] = spec["prediction_path"]
    return row


def rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = sorted(
        rows,
        key=lambda row: (
            -float(row["polarization_f1"]),
            -float(row["category_f1"]),
            -float(row["subcategory_f1"]),
            row["architecture"],
            row["model"],
            row["prompt"],
        ),
    )
    best_polar = max(float(row["polarization_f1"]) for row in rows)
    best_category = max(float(row["category_f1"]) for row in rows)
    best_subcategory = max(float(row["subcategory_f1"]) for row in rows)
    best_recall = max(float(row["polarization_recall"]) for row in rows)
    for idx, row in enumerate(rows, start=1):
        row["rank_by_polarization_f1"] = idx
        row["best_polarization_f1"] = float(row["polarization_f1"]) == best_polar
        row["best_category_f1"] = float(row["category_f1"]) == best_category
        row["best_subcategory_f1"] = float(row["subcategory_f1"]) == best_subcategory
        row["best_polarization_recall"] = float(row["polarization_recall"]) == best_recall
    return rows


def write_csv(rows: list[dict[str, Any]]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, Any]]) -> None:
    columns = [
        "rank_by_polarization_f1",
        "architecture",
        "model",
        "prompt",
        "polarization_precision",
        "polarization_recall",
        "polarization_f1",
        "category_f1",
        "subcategory_f1",
    ]
    headers = [
        "Rank",
        "Architecture",
        "Model",
        "Prompt",
        "Pol. P",
        "Pol. R",
        "Pol. F1",
        "Cat. F1",
        "Subcat. F1",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        values: list[str] = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                text = f"{value:.3f}"
            else:
                text = str(value)
            if column == "polarization_f1" and row["best_polarization_f1"]:
                text = f"**{text}**"
            if column == "category_f1" and row["best_category_f1"]:
                text = f"**{text}**"
            if column == "subcategory_f1" and row["best_subcategory_f1"]:
                text = f"**{text}**"
            if column == "polarization_recall" and row["best_polarization_recall"]:
                text = f"**{text}**"
            values.append(text)
        lines.append("| " + " | ".join(values) + " |")
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    gold = load_json(GOLD_JSON)
    specs = build_specs()
    rows = rank_rows([row_for_spec(spec, gold) for spec in specs])
    write_csv(rows)
    write_markdown(rows)
    print(
        json.dumps(
            {
                "configurations": len(rows),
                "csv": str(OUTPUT_CSV),
                "markdown": str(OUTPUT_MD),
                "best_polarization_f1": next(row for row in rows if row["best_polarization_f1"]),
                "best_category_f1": next(row for row in rows if row["best_category_f1"]),
                "best_subcategory_f1": next(row for row in rows if row["best_subcategory_f1"]),
                "best_polarization_recall": next(row for row in rows if row["best_polarization_recall"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
