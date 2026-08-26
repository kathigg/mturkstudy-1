from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
WRAPPER = REPO / "src/dataset_comparison_scripts/run_wrapper_multiple_llm_annotations.py"
INPUT_CSV = REPO / "src/dataset_comparison_scripts/2-20/2-20_selected_articles.csv"
PROMPT_DIR = REPO / "src/dataset_comparison_scripts/prompt_versions/bagozzi_inhouse_fewshot"
OUTPUT_ROOT = REPO / "src/llm_annotation_results/2-20/bagozzi_inhouse_prompt_sweep"
ANALYSIS_ROOT = REPO / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/prompt_sweep"
GOLD_JSON = REPO / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/consolidated_bagozzi_inhouse_overlap_gold_standard_output.json"


def normalize_title(text: str | None) -> str:
    return re.sub(r"[^\w\s]", "", text or "").strip().lower()


def normalize_label(text: str | None) -> str:
    return re.sub(r"_+", " ", text or "").strip().lower()


def is_npl(annotation: dict[str, Any]) -> bool:
    joined = normalize_label(annotation.get("category")) + " " + normalize_label(annotation.get("subcategory"))
    return "no polarizing language" in joined


def f1(precision: float, recall: float) -> float:
    return (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0


def load_comparison_module():
    import importlib.util

    path = REPO / "src/dataset_comparison_scripts/paragraph_llm_human_comparison.py"
    spec = importlib.util.spec_from_file_location("paragraph_llm_human_comparison", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def flatten_article_list(path: Path, *, polarizing_only: bool) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    by_title: dict[str, dict[str, Any]] = {}
    for article in data:
        title = article.get("title", "UNKNOWN_TITLE")
        annotations = article.get("items") or article.get("annotations") or []
        if polarizing_only:
            annotations = [ann for ann in annotations if not is_npl(ann)]
        by_title[normalize_title(title)] = {
            "title": title,
            "annotations": [
                {
                    "text": ann.get("text", ""),
                    "category": ann.get("category", ""),
                    "subcategory": ann.get("subcategory", ""),
                    "confidence": ann.get("confidence"),
                    "paragraphIndex": ann.get("paragraphIndex"),
                }
                for ann in annotations
            ],
        }
    return by_title


def write_polarizing_only_json(input_path: Path, output_path: Path) -> dict[str, int]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    total_annotations = 0
    kept_annotations = 0
    out = []
    for article in data:
        row = dict(article)
        annotations = row.get("items") or row.get("annotations") or []
        total_annotations += len(annotations)
        kept = [ann for ann in annotations if not is_npl(ann)]
        kept_annotations += len(kept)
        row["annotations"] = kept
        row.pop("items", None)
        out.append(row)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "input_annotations": total_annotations,
        "polarizing_annotations": kept_annotations,
        "dropped_npl_annotations": total_annotations - kept_annotations,
    }


def compare_prediction_to_gold(prediction_path: Path, gold_path: Path, output_path: Path) -> dict[str, Any]:
    comp = load_comparison_module()
    pred = flatten_article_list(prediction_path, polarizing_only=True)
    gold = flatten_article_list(gold_path, polarizing_only=True)
    all_titles = sorted(set(pred) | set(gold))

    per_article = {}
    totals = {
        "span_tp": 0,
        "pred_total": 0,
        "gold_total": 0,
        "category_correct": 0,
        "subcategory_correct": 0,
    }

    for norm_title in all_titles:
        pred_article = pred.get(norm_title, {"title": norm_title, "annotations": []})
        gold_article = gold.get(norm_title, {"title": norm_title, "annotations": []})
        pred_annotations = pred_article["annotations"]
        gold_annotations = gold_article["annotations"]
        matched_pairs, unmatched_pred, unmatched_gold = comp.greedy_weighted_match(
            pred_annotations,
            gold_annotations,
            lambda p, g: comp.match_annotation(p, g, pred_article["title"], gold_article["title"]),
        )
        category_correct = 0
        subcategory_correct = 0
        for pred_idx, gold_idx, _ in matched_pairs:
            pred_ann = pred_annotations[pred_idx]
            gold_ann = gold_annotations[gold_idx]
            if normalize_label(pred_ann.get("category")) == normalize_label(gold_ann.get("category")):
                category_correct += 1
            if normalize_label(pred_ann.get("subcategory")) == normalize_label(gold_ann.get("subcategory")):
                subcategory_correct += 1

        totals["span_tp"] += len(matched_pairs)
        totals["pred_total"] += len(pred_annotations)
        totals["gold_total"] += len(gold_annotations)
        totals["category_correct"] += category_correct
        totals["subcategory_correct"] += subcategory_correct

        per_article[gold_article["title"]] = {
            "matched_spans": len(matched_pairs),
            "prediction_only": len(unmatched_pred),
            "gold_only": len(unmatched_gold),
            "prediction_total": len(pred_annotations),
            "gold_total": len(gold_annotations),
            "category_correct_on_matched": category_correct,
            "subcategory_correct_on_matched": subcategory_correct,
        }

    span_precision = totals["span_tp"] / totals["pred_total"] if totals["pred_total"] else 0.0
    span_recall = totals["span_tp"] / totals["gold_total"] if totals["gold_total"] else 0.0
    matched = totals["span_tp"]
    overall = {
        "span": {
            "precision": round(span_precision, 3),
            "recall": round(span_recall, 3),
            "f1": round(f1(span_precision, span_recall), 3),
            "tp": totals["span_tp"],
            "prediction_total": totals["pred_total"],
            "gold_total": totals["gold_total"],
            "prediction_only": totals["pred_total"] - totals["span_tp"],
            "gold_only": totals["gold_total"] - totals["span_tp"],
        },
        "category_agreement_on_matched_spans": {
            "agreement": round(totals["category_correct"] / matched, 3) if matched else 0.0,
            "correct": totals["category_correct"],
            "matched_spans": matched,
        },
        "subcategory_agreement_on_matched_spans": {
            "agreement": round(totals["subcategory_correct"] / matched, 3) if matched else 0.0,
            "correct": totals["subcategory_correct"],
            "matched_spans": matched,
        },
    }
    payload = {
        "prediction_path": str(prediction_path),
        "gold_path": str(gold_path),
        "comparison_basis": "polarizing-only; all gold and prediction article titles are retained so empty-annotation articles still count",
        "overall": overall,
        "per_article": per_article,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def parse_temperatures(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def run_command(cmd: list[str]) -> None:
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


def run_command_with_resumable_retries(cmd: list[str], *, attempts: int, run_id: str) -> None:
    last_exc: subprocess.CalledProcessError | None = None
    for attempt in range(1, attempts + 1):
        retry_cmd = list(cmd)
        if attempt > 1 and "--resume" not in retry_cmd:
            retry_cmd.append("--resume")

        print(f"[{run_id}] wrapper attempt {attempt}/{attempts}")
        try:
            run_command(retry_cmd)
            return
        except subprocess.CalledProcessError as exc:
            last_exc = exc
            if attempt >= attempts:
                raise
            sleep_s = min(90, 10 * attempt)
            print(
                f"[{run_id}] wrapper failed with exit code {exc.returncode}; "
                f"sleeping {sleep_s}s and resuming from checkpoint.",
                file=sys.stderr,
            )
            time.sleep(sleep_s)

    if last_exc is not None:
        raise last_exc


def build_gold() -> None:
    cmd = [
        sys.executable,
        str(REPO / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/build_consolidated_bagozzi_inhouse_gold.py"),
        "--output",
        str(GOLD_JSON),
    ]
    run_command(cmd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(INPUT_CSV))
    parser.add_argument("--prompt-dir", default=str(PROMPT_DIR))
    parser.add_argument("--output-root", default=str(OUTPUT_ROOT))
    parser.add_argument("--analysis-root", default=str(ANALYSIS_ROOT))
    parser.add_argument("--gold-json", default=str(GOLD_JSON))
    parser.add_argument("--openai-model", default="gpt-5.1")
    parser.add_argument("--gemini-model", default="gemini-3.1-pro-preview")
    parser.add_argument("--claude-model", default="claude-sonnet-5")
    parser.add_argument("--claude-adjudicator-model", default="claude-opus-4-8")
    parser.add_argument("--adjudicator-model", default=None)
    parser.add_argument("--annotator-b-provider", default="gemini", choices=["gemini", "openai"])
    parser.add_argument("--annotator-c-provider", default="anthropic", choices=["openai", "anthropic", "none"])
    parser.add_argument("--adjudicator-provider", default="anthropic", choices=["openai", "anthropic"])
    parser.add_argument("--temperatures", default="0")
    parser.add_argument("--stochastic-runs", type=int, default=1)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--checkpoint-every", type=int, default=1)
    parser.add_argument(
        "--wrapper-attempts",
        type=int,
        default=1,
        help="Number of times to relaunch a failed per-prompt wrapper command with --resume.",
    )
    parser.add_argument("--prompt-version", action="append", help="Optional prompt file stem to run, e.g. prompt_v3_high_precision_adjudicated.")
    parser.add_argument("--compare-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    build_gold()
    prompt_dir = Path(args.prompt_dir)
    prompt_files = sorted(prompt_dir.glob("*.md"))
    if args.prompt_version:
        allowed = set(args.prompt_version)
        prompt_files = [path for path in prompt_files if path.stem in allowed]
    if not prompt_files:
        raise FileNotFoundError(f"No prompt version files found in {prompt_dir}")

    output_root = Path(args.output_root)
    analysis_root = Path(args.analysis_root)
    gold_json = Path(args.gold_json)
    temperatures = parse_temperatures(args.temperatures)
    summary_rows: list[dict[str, Any]] = []

    for prompt_file in prompt_files:
        for temperature in temperatures:
            repetitions = 1 if temperature == 0 else args.stochastic_runs
            for run_index in range(1, repetitions + 1):
                temp_label = str(temperature).replace(".", "p")
                run_id = f"{prompt_file.stem}_temp{temp_label}_run{run_index}"
                run_dir = output_root / run_id
                final_json = run_dir / "final_annotations.json"
                final_jsonl = run_dir / "final_annotations.jsonl"
                results_csv = run_dir / "raw_results.csv"
                polarizing_json = run_dir / "final_annotations_polarizing_only.json"
                comparison_json = analysis_root / f"{run_id}_comparison.json"

                if not args.compare_only:
                    cmd = [
                        sys.executable,
                        str(WRAPPER),
                        "--input",
                        str(args.input),
                        "--results-csv",
                        str(results_csv),
                        "--final-json",
                        str(final_json),
                        "--final-jsonl",
                        str(final_jsonl),
                        "--prompt-addendum-file",
                        str(prompt_file),
                        "--temperature",
                        str(temperature),
                        "--paragraph-policy",
                        "min-one",
                        "--checkpoint-every",
                        str(args.checkpoint_every),
                        "--max-retries",
                        str(args.max_retries),
                        "--openai-model",
                        args.openai_model,
                        "--gemini-model",
                        args.gemini_model,
                        "--claude-model",
                        args.claude_model,
                        "--claude-adjudicator-model",
                        args.claude_adjudicator_model,
                        "--annotator-b-provider",
                        args.annotator_b_provider,
                        "--annotator-c-provider",
                        args.annotator_c_provider,
                        "--adjudicator-provider",
                        args.adjudicator_provider,
                    ]
                    if args.adjudicator_model:
                        cmd += ["--adjudicator-model", args.adjudicator_model]
                    if args.resume:
                        cmd.append("--resume")
                    if args.overwrite:
                        cmd.append("--overwrite")
                    if args.dry_run:
                        cmd.append("--dry-run")
                    if final_json.exists() and not args.resume and not args.overwrite:
                        print(f"Skipping existing run: {run_id}")
                    else:
                        run_command_with_resumable_retries(
                            cmd,
                            attempts=max(1, args.wrapper_attempts),
                            run_id=run_id,
                        )

                if not final_json.exists():
                    print(f"Skipping comparison; missing final JSON: {final_json}")
                    continue

                filter_counts = write_polarizing_only_json(final_json, polarizing_json)
                comparison = compare_prediction_to_gold(polarizing_json, gold_json, comparison_json)
                overall = comparison["overall"]
                summary_rows.append(
                    {
                        "run_id": run_id,
                        "prompt_version": prompt_file.stem,
                        "temperature": temperature,
                        "run_index": run_index,
                        "openai_model": args.openai_model,
                        "gemini_model": args.gemini_model,
                        "claude_model": args.claude_model,
                        "claude_adjudicator_model": args.claude_adjudicator_model,
                        "adjudicator_provider": args.adjudicator_provider,
                        "adjudicator_model": args.adjudicator_model
                        or (args.claude_adjudicator_model if args.adjudicator_provider == "anthropic" else args.openai_model),
                        "annotator_b_provider": args.annotator_b_provider,
                        "annotator_c_provider": args.annotator_c_provider,
                        "prediction_annotations_total": filter_counts["input_annotations"],
                        "prediction_polarizing_annotations": filter_counts["polarizing_annotations"],
                        "prediction_npl_dropped": filter_counts["dropped_npl_annotations"],
                        "span_precision": overall["span"]["precision"],
                        "span_recall": overall["span"]["recall"],
                        "span_f1": overall["span"]["f1"],
                        "matched_spans": overall["span"]["tp"],
                        "prediction_only": overall["span"]["prediction_only"],
                        "gold_only": overall["span"]["gold_only"],
                        "category_agreement_on_matched": overall["category_agreement_on_matched_spans"]["agreement"],
                        "subcategory_agreement_on_matched": overall["subcategory_agreement_on_matched_spans"]["agreement"],
                        "final_json": str(final_json),
                        "polarizing_json": str(polarizing_json),
                        "comparison_json": str(comparison_json),
                    }
                )

    analysis_root.mkdir(parents=True, exist_ok=True)
    summary_csv = analysis_root / "bagozzi_inhouse_prompt_sweep_summary.csv"
    if summary_rows:
        with summary_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)
    print(f"Wrote summary CSV: {summary_csv}")
    print(json.dumps({"runs_compared": len(summary_rows), "summary_csv": str(summary_csv)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
