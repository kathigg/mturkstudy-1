from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import src.dataset_comparison_scripts.run_wrapper_multiple_llm_annotations as base  # noqa: E402
import src.dataset_comparison_scripts.run_bagozzi_inhouse_prompt_sweep as sweep  # noqa: E402
import src.dataset_comparison_scripts.run_decision_point_adjudication as decision_point  # noqa: E402


GOLD_JSON = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "consolidated_bagozzi_inhouse_overlap_gold_standard_output.json"
)
PROMPT_FILE = REPO / "src/dataset_comparison_scripts/prompt_versions/dr_bagozzi_codebook_addendum.md"
OUTPUT_ROOT = REPO / "src/llm_annotation_results/2-20/bagozzi_intersection_single_model_dr_bagozzi_prompt"
ANALYSIS_ROOT = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "single_model_dr_bagozzi_prompt"
)
PREVIOUS_ADJUDICATED_FINAL = (
    REPO
    / "src/llm_annotation_results/2-20/bagozzi_inhouse_prompt_sweep/"
    / "prompt_v3_high_precision_adjudicated_temp0p0_run1/final_annotations.json"
)


MODEL_SPECS: dict[str, dict[str, str]] = {
    "openai": {"provider": "openai", "model": "gpt-5-mini", "label": "GPT-5 mini"},
    "gemini": {"provider": "gemini", "model": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash Lite"},
    "claude": {"provider": "anthropic", "model": "claude-haiku-4-5", "label": "Claude Haiku 4.5"},
}


ROLE_DESC = (
    "You are a careful political communication annotator. Strictly follow the Dr. Bagozzi "
    "codebook and JSON schema. Be conservative: if unsure, choose No Polarizing language."
)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def load_articles_from_gold(path: Path) -> pd.DataFrame:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for article in data:
        rows.append(
            {
                "Headline": article.get("title", ""),
                "News body": article.get("news_body", ""),
                "Topic": article.get("topic", ""),
                "News Source": article.get("source", article.get("news_source", "")),
                "Rating": article.get("rating", ""),
            }
        )
    return pd.DataFrame(rows)


def load_articles_from_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def provider_key_is_present(provider: str) -> bool:
    if provider == "openai":
        return bool(os.environ.get("OPENAI_API_KEY"))
    if provider == "gemini":
        return bool(os.environ.get("GEMINI_API_KEY"))
    if provider == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    raise ValueError(provider)


def make_client(provider: str, *, request_timeout_s: float) -> Any:
    if provider == "openai":
        return base._openai_client(request_timeout_s=request_timeout_s)
    if provider == "gemini":
        return base._gemini_client(request_timeout_s=request_timeout_s)
    if provider == "anthropic":
        return base._anthropic_openai_compat_client(request_timeout_s=request_timeout_s)
    raise ValueError(provider)


def annotate_one(
    *,
    provider: str,
    client: Any,
    model: str,
    title: str,
    topic: str,
    source: str,
    rating: str,
    body: str,
    article_block: str,
    temperature: float | None,
    max_retries: int,
    request_timeout_s: float,
) -> tuple[dict[str, Any], str]:
    if provider == "openai":
        # Some GPT-5-family chat models only accept the default temperature.
        openai_temperature = None if model.startswith("gpt-5") else temperature
        return base.annotate_with_openai(
            client,
            ROLE_DESC,
            article_block,
            title,
            topic,
            source,
            rating,
            body=body,
            model=model,
            temperature=openai_temperature,
            max_retries=max_retries,
            request_timeout_s=request_timeout_s,
        )
    if provider == "gemini":
        return base.annotate_with_gemini(
            client,
            ROLE_DESC,
            article_block,
            title,
            topic,
            source,
            rating,
            body=body,
            model=model,
            max_retries=max_retries,
        )
    if provider == "anthropic":
        return base.annotate_with_openai(
            client,
            ROLE_DESC,
            article_block,
            title,
            topic,
            source,
            rating,
            body=body,
            model=model,
            temperature=None,
            max_retries=max_retries,
            request_timeout_s=request_timeout_s,
        )
    raise ValueError(provider)


def completed_indices(results_csv: Path) -> set[int]:
    if not results_csv.exists():
        return set()
    with results_csv.open(newline="", encoding="utf-8") as handle:
        out = set()
        for row in csv.DictReader(handle):
            try:
                out.add(int(row["index"]))
            except Exception:
                continue
        return out


def load_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_final_from_jsonl(jsonl_path: Path, final_json: Path) -> None:
    rows = sorted(load_jsonl_objects(jsonl_path), key=lambda row: int(row["index"]))
    final = [row["annotation"] for row in rows]
    final_json.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_model(
    df: pd.DataFrame,
    *,
    provider_key: str,
    spec: dict[str, str],
    output_root: Path,
    temperature: float,
    max_retries: int,
    request_timeout_s: float,
    resume: bool,
    overwrite: bool,
) -> dict[str, Any]:
    provider = spec["provider"]
    model = spec["model"]
    run_id = f"{provider_key}_{slug(model)}"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    results_csv = run_dir / "raw_results.csv"
    final_jsonl = run_dir / "final_annotations.jsonl"
    final_json = run_dir / "final_annotations.json"
    metadata_json = run_dir / "metadata.json"

    if overwrite and not resume:
        for path in (results_csv, final_jsonl, final_json, metadata_json):
            if path.exists():
                path.unlink()

    if not provider_key_is_present(provider):
        metadata = {
            "status": "skipped_missing_key",
            "provider": provider,
            "model": model,
            "run_id": run_id,
        }
        metadata_json.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return metadata

    client = make_client(provider, request_timeout_s=request_timeout_s)
    done = completed_indices(results_csv) if resume else set()
    fieldnames = [
        "index",
        "title",
        "topic",
        "source",
        "rating",
        "provider",
        "model",
        "prompt_file",
        "temperature",
        "raw_json",
    ]

    write_header = not results_csv.exists() or not resume
    with results_csv.open("a", newline="", encoding="utf-8") as csv_handle, final_jsonl.open(
        "a", encoding="utf-8"
    ) as jsonl_handle:
        writer = csv.DictWriter(csv_handle, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for idx, row in df.iterrows():
            if int(idx) in done:
                continue

            title, topic, source, rating, body, article_block = base.build_article_text(row.to_dict())
            print(f"[{run_id}] {idx + 1}/{len(df)} {title}", flush=True)
            obj, raw = annotate_one(
                provider=provider,
                client=client,
                model=model,
                title=title,
                topic=topic,
                source=source,
                rating=rating,
                body=body,
                article_block=article_block,
                temperature=temperature,
                max_retries=max_retries,
                request_timeout_s=request_timeout_s,
            )
            obj = base.apply_paragraph_policy(obj, body=body, paragraph_policy="min-one")
            ok, err = base.validate_annotation(obj)
            if not ok:
                raise ValueError(f"{run_id} output failed schema validation after paragraph policy: {err}")

            writer.writerow(
                {
                    "index": int(idx),
                    "title": title,
                    "topic": topic,
                    "source": source,
                    "rating": rating,
                    "provider": provider,
                    "model": model,
                    "prompt_file": str(PROMPT_FILE),
                    "temperature": temperature,
                    "raw_json": raw,
                }
            )
            csv_handle.flush()
            jsonl_handle.write(json.dumps({"index": int(idx), "annotation": obj}, ensure_ascii=False) + "\n")
            jsonl_handle.flush()
            write_final_from_jsonl(final_jsonl, final_json)

    write_final_from_jsonl(final_jsonl, final_json)
    metadata = {
        "status": "complete",
        "provider": provider,
        "model": model,
        "run_id": run_id,
        "prompt_file": str(PROMPT_FILE),
        "gold_article_source": str(GOLD_JSON),
        "final_json": str(final_json),
        "results_csv": str(results_csv),
        "article_count": len(df),
    }
    metadata_json.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def is_npl(annotation: dict[str, Any]) -> bool:
    joined = (
        sweep.normalize_label(annotation.get("category"))
        + " "
        + sweep.normalize_label(annotation.get("subcategory"))
        + " "
        + sweep.normalize_label(annotation.get("text"))
    )
    return "no polarizing language" in joined


def write_polarizing_only(input_path: Path, output_path: Path) -> dict[str, int]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    total = 0
    kept_total = 0
    out = []
    for article in data:
        row = dict(article)
        annotations = row.get("items") or row.get("annotations") or []
        total += len(annotations)
        kept = [ann for ann in annotations if not is_npl(ann)]
        kept_total += len(kept)
        row["annotations"] = kept
        row.pop("items", None)
        out.append(row)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"input_annotations": total, "polarizing_annotations": kept_total, "dropped_npl": total - kept_total}


def flatten_articles_preserving_empty(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for article in data:
        title = article.get("title", "UNKNOWN_TITLE")
        annotations = article.get("items") or article.get("annotations") or []
        out[sweep.normalize_title(title)] = {"title": title, "annotations": annotations}
    return out


def compute_article_metrics(prediction_path: Path, gold_path: Path, output_path: Path) -> dict[str, Any]:
    """Article-level binary detection: whether an article has any polarizing span."""
    prediction = flatten_articles_preserving_empty(prediction_path)
    gold = flatten_articles_preserving_empty(gold_path)
    all_titles = sorted(set(prediction) | set(gold))
    per_article: dict[str, dict[str, Any]] = {}
    tp = fp = fn = tn = 0

    for norm_title in all_titles:
        pred_article = prediction.get(norm_title, {"title": norm_title, "annotations": []})
        gold_article = gold.get(norm_title, {"title": norm_title, "annotations": []})
        pred_has = bool(pred_article["annotations"])
        gold_has = bool(gold_article["annotations"])
        if pred_has and gold_has:
            outcome = "tp"
            tp += 1
        elif pred_has and not gold_has:
            outcome = "fp"
            fp += 1
        elif not pred_has and gold_has:
            outcome = "fn"
            fn += 1
        else:
            outcome = "tn"
            tn += 1
        per_article[gold_article["title"]] = {
            "prediction_has_polarizing": pred_has,
            "gold_has_polarizing": gold_has,
            "prediction_annotations": len(pred_article["annotations"]),
            "gold_annotations": len(gold_article["annotations"]),
            "outcome": outcome,
        }

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(all_titles) if all_titles else 0.0
    payload = {
        "prediction_path": str(prediction_path),
        "gold_path": str(gold_path),
        "metric_definition": "Article-level binary detection: an article is positive if it contains at least one polarizing annotation after NPL filtering.",
        "overall": {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "accuracy": round(accuracy, 3),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "articles": len(all_titles),
        },
        "per_article": per_article,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def compute_legacy_article_overlap_metrics(prediction_path: Path, gold_path: Path, output_path: Path) -> dict[str, Any]:
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    import src.dataset_comparison_scripts.paragraph_llm_human_comparison as article_comp

    article_comp.USE_CONFIDENCE_WEIGHTING = False
    article_comp.ENFORCE_ONE_ANNOTATION_PER_PARAGRAPH = False
    comparison = article_comp.compare_all(prediction, gold)
    payload = {
        "prediction_path": str(prediction_path),
        "gold_path": str(gold_path),
        "overall": comparison["overall"],
        "per_article": comparison["per_article"],
        "n_articles_compared": len(comparison["per_article"]),
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def compute_npl_inclusive_metrics(prediction_path: Path, gold_path: Path, output_path: Path) -> dict[str, Any]:
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    metrics = decision_point.compare_predictions(
        prediction,
        gold,
        include_npl=True,
        title_policy="gold_nonempty",
    )
    payload = {
        "prediction_path": str(prediction_path),
        "gold_path": str(gold_path),
        "rule": "NPL matches only NPL in the same article and paragraph; polarizing spans use the existing overlap logic.",
        "overall": metrics,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metrics


def compare_run(
    *,
    label: str,
    provider: str,
    model: str,
    final_json: Path,
    gold_json: Path,
    analysis_root: Path,
    prompt_label: str = "Dr. Bagozzi codebook addendum",
) -> dict[str, Any]:
    safe_label = slug(label)
    polarizing_json = analysis_root / f"{safe_label}_polarizing_only.json"
    span_comparison_json = analysis_root / f"{safe_label}_span_comparison.json"
    article_comparison_json = analysis_root / f"{safe_label}_article_comparison.json"
    npl_inclusive_json = analysis_root / f"{safe_label}_npl_inclusive_comparison.json"

    filter_counts = write_polarizing_only(final_json, polarizing_json)
    npl_inclusive = compute_npl_inclusive_metrics(final_json, gold_json, npl_inclusive_json)
    span_comparison = sweep.compare_prediction_to_gold(polarizing_json, gold_json, span_comparison_json)
    article_comparison = compute_article_metrics(polarizing_json, gold_json, article_comparison_json)
    legacy_article_comparison_json = analysis_root / f"{safe_label}_legacy_article_overlap_comparison.json"
    legacy_article_comparison = compute_legacy_article_overlap_metrics(
        polarizing_json, gold_json, legacy_article_comparison_json
    )

    span = span_comparison["overall"]["span"]
    article = article_comparison["overall"]
    legacy_article = legacy_article_comparison["overall"]["article_match"]
    tp = int(span["tp"])
    pred_total = int(span["prediction_total"])
    gold_total = int(span["gold_total"])
    fp = pred_total - tp
    fn = gold_total - tp
    span_iou = round(tp / (tp + fp + fn), 3) if (tp + fp + fn) else 0.0
    npl_polarization = npl_inclusive["polarization_match"]
    npl_category = npl_inclusive["category_match"]
    npl_subcategory = npl_inclusive["subcategory_match"]
    return {
        "run": label,
        "provider": provider,
        "model": model,
        "status": "complete",
        "prompt": prompt_label,
        "llm_annotations": pred_total,
        "human_annotations": gold_total,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "article_precision": article["precision"],
        "article_recall": article["recall"],
        "article_f1": article["f1"],
        "article_accuracy": article["accuracy"],
        "article_tp": article["tp"],
        "article_fp": article["fp"],
        "article_fn": article["fn"],
        "article_tn": article["tn"],
        "legacy_article_overlap_precision": legacy_article["precision"],
        "legacy_article_overlap_recall": legacy_article["recall"],
        "legacy_article_overlap_f1": legacy_article["f1"],
        "span_precision": span["precision"],
        "span_recall": span["recall"],
        "span_f1": span["f1"],
        "span_iou": span_iou,
        "npl_polarization_precision": npl_polarization["precision"],
        "npl_polarization_recall": npl_polarization["recall"],
        "npl_polarization_f1": npl_polarization["f1"],
        "npl_category_precision": npl_category["precision"],
        "npl_category_recall": npl_category["recall"],
        "npl_category_f1": npl_category["f1"],
        "npl_subcategory_precision": npl_subcategory["precision"],
        "npl_subcategory_recall": npl_subcategory["recall"],
        "npl_subcategory_f1": npl_subcategory["f1"],
        "npl_category_agreement_on_matched": npl_inclusive["label_agreement_on_matched"]["category"],
        "npl_subcategory_agreement_on_matched": npl_inclusive["label_agreement_on_matched"]["subcategory"],
        "total_model_annotations_before_npl_filter": filter_counts["input_annotations"],
        "npl_dropped": filter_counts["dropped_npl"],
        "final_json": str(final_json),
        "polarizing_json": str(polarizing_json),
        "span_comparison_json": str(span_comparison_json),
        "article_comparison_json": str(article_comparison_json),
        "legacy_article_overlap_comparison_json": str(legacy_article_comparison_json),
        "npl_inclusive_comparison_json": str(npl_inclusive_json),
    }


def compare_outputs(output_root: Path, analysis_root: Path, include_previous: bool) -> list[dict[str, Any]]:
    analysis_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for provider_key, spec in MODEL_SPECS.items():
        run_id = f"{provider_key}_{slug(spec['model'])}"
        final_json = output_root / run_id / "final_annotations.json"
        metadata_json = output_root / run_id / "metadata.json"
        if final_json.exists():
            rows.append(
            compare_run(
                label=spec["label"],
                provider=spec["provider"],
                model=spec["model"],
                final_json=final_json,
                gold_json=GOLD_JSON,
                analysis_root=analysis_root,
                prompt_label=PROMPT_FILE.stem,
            )
            )
        elif metadata_json.exists():
            metadata = json.loads(metadata_json.read_text(encoding="utf-8"))
            rows.append(
                {
                    "run": spec["label"],
                    "provider": spec["provider"],
                    "model": spec["model"],
                    "status": metadata.get("status", "missing_output"),
                }
            )

    if include_previous and PREVIOUS_ADJUDICATED_FINAL.exists():
        rows.append(
            compare_run(
                label="Previous adjudicated V3",
                provider="multi_model_adjudicated",
                model="gpt-5.1 + gemini-3.1-pro-preview + claude-sonnet-5 -> claude-opus-4-8",
                final_json=PREVIOUS_ADJUDICATED_FINAL,
                gold_json=GOLD_JSON,
                analysis_root=analysis_root,
                prompt_label="prompt_v3_high_precision_adjudicated (previous saved run)",
            )
        )

    if rows:
        fieldnames = sorted({key for row in rows for key in row})
        summary_csv = analysis_root / "single_model_vs_previous_adjudicated_summary.csv"
        with summary_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        (analysis_root / "single_model_vs_previous_adjudicated_summary.json").write_text(
            json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Wrote summary CSV: {summary_csv}")
    return rows


def main() -> int:
    global GOLD_JSON, PROMPT_FILE

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=None,
        help="Optional article CSV. If omitted, articles are reconstructed from --gold-json for the 27-article setup.",
    )
    parser.add_argument("--providers", default="openai,gemini,claude")
    parser.add_argument("--output-root", default=str(OUTPUT_ROOT))
    parser.add_argument("--analysis-root", default=str(ANALYSIS_ROOT))
    parser.add_argument("--prompt-file", default=str(PROMPT_FILE))
    parser.add_argument("--gold-json", default=str(GOLD_JSON))
    parser.add_argument("--openai-model", default=MODEL_SPECS["openai"]["model"])
    parser.add_argument("--gemini-model", default=MODEL_SPECS["gemini"]["model"])
    parser.add_argument("--claude-model", default=MODEL_SPECS["claude"]["model"])
    parser.add_argument("--openai-label", default=MODEL_SPECS["openai"]["label"])
    parser.add_argument("--gemini-label", default=MODEL_SPECS["gemini"]["label"])
    parser.add_argument("--claude-label", default=MODEL_SPECS["claude"]["label"])
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--request-timeout-s", type=float, default=240.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--compare-only", action="store_true")
    parser.add_argument("--skip-run", action="store_true")
    parser.add_argument("--no-previous-adjudicated", action="store_true")
    args = parser.parse_args()

    base._load_dotenv_if_present()
    prompt_path = Path(args.prompt_file)
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    PROMPT_FILE = prompt_path
    GOLD_JSON = Path(args.gold_json)
    base.set_prompt_addendum(prompt_path.read_text(encoding="utf-8"))
    MODEL_SPECS["openai"].update({"model": args.openai_model, "label": args.openai_label})
    MODEL_SPECS["gemini"].update({"model": args.gemini_model, "label": args.gemini_label})
    MODEL_SPECS["claude"].update({"model": args.claude_model, "label": args.claude_label})

    output_root = Path(args.output_root)
    analysis_root = Path(args.analysis_root)
    requested = [item.strip() for item in args.providers.split(",") if item.strip()]
    unknown = sorted(set(requested) - set(MODEL_SPECS))
    if unknown:
        raise ValueError(f"Unknown providers: {unknown}; valid choices are {sorted(MODEL_SPECS)}")

    df = load_articles_from_csv(Path(args.input)) if args.input else load_articles_from_gold(GOLD_JSON)
    output_root.mkdir(parents=True, exist_ok=True)

    run_metadata = []
    if not args.compare_only and not args.skip_run:
        for provider_key in requested:
            try:
                run_metadata.append(
                    run_model(
                        df,
                        provider_key=provider_key,
                        spec=MODEL_SPECS[provider_key],
                        output_root=output_root,
                        temperature=args.temperature,
                        max_retries=args.max_retries,
                        request_timeout_s=args.request_timeout_s,
                        resume=args.resume,
                        overwrite=args.overwrite,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - record provider failure and keep comparisons usable
                spec = MODEL_SPECS[provider_key]
                run_id = f"{provider_key}_{slug(spec['model'])}"
                run_dir = output_root / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                metadata = {
                    "status": "failed",
                    "provider": spec["provider"],
                    "model": spec["model"],
                    "run_id": run_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                (run_dir / "metadata.json").write_text(
                    json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                run_metadata.append(metadata)
                print(json.dumps(metadata, indent=2, ensure_ascii=False), file=sys.stderr)

    rows = compare_outputs(
        output_root,
        analysis_root,
        include_previous=not args.no_previous_adjudicated,
    )
    print(json.dumps({"runs": run_metadata, "comparisons": rows}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
