from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

import src.dataset_comparison_scripts.run_decision_point_adjudication as dp  # noqa: E402


ANALYSIS_ROOT = REPO / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27"
DEFAULT_ARTICLES_CSV = REPO / "src/dataset_comparison_scripts/2-20/2-20_selected_articles.csv"
DEFAULT_GOLD = ANALYSIS_ROOT / "consolidated_bagozzi_inhouse_overlap_gold_with_conservative_npl_paragraph_spans.json"
DEFAULT_PREDICTIONS = (
    REPO
    / "src/llm_annotation_results/2-20/decision_point_adjudication_v1/"
    / "ablations_for_heatmap/decision_point_binary_filter.json"
)
DEFAULT_OUTPUT = ANALYSIS_ROOT / "intersection_gold_vs_decision_point_binary_filter_disagreements.csv"
DEFAULT_SUMMARY = ANALYSIS_ROOT / "intersection_gold_vs_decision_point_binary_filter_disagreements_summary.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_articles_csv(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {dp.normalize_title(row.get("Headline")): row for row in csv.DictReader(handle)}


def annotation_text(annotation: dict[str, Any] | None) -> str:
    if not annotation:
        return ""
    return dp.normalize_space(str(annotation.get("text") or ""))


def annotation_category(annotation: dict[str, Any] | None) -> str:
    if not annotation:
        return "NO_MATCH"
    return dp.canonical_category(annotation.get("category"))


def annotation_subcategory(annotation: dict[str, Any] | None) -> str:
    if not annotation:
        return "NO_MATCH"
    return dp.canonical_subcategory(annotation.get("subcategory"))


def annotation_polarization(annotation: dict[str, Any] | None) -> str:
    if not annotation:
        return "NO_MATCH"
    return "not_polarizing" if dp.is_npl(annotation) else "polarizing"


def annotation_label(annotation: dict[str, Any] | None) -> str:
    if not annotation:
        return "NO_MATCH"
    return " | ".join(
        [
            annotation_polarization(annotation),
            annotation_category(annotation),
            annotation_subcategory(annotation),
        ]
    )


def paragraph_text(article: dict[str, Any], paragraph_index: Any) -> str:
    try:
        index = int(paragraph_index)
    except (TypeError, ValueError):
        return ""
    body = str(article.get("news_body") or article.get("body") or "")
    paragraphs = dp.split_paragraphs(body)
    if 0 <= index < len(paragraphs):
        return dp.normalize_space(paragraphs[index])
    return ""


def article_body(article: dict[str, Any], article_csv_rows: dict[str, dict[str, str]]) -> str:
    body = str(article.get("news_body") or article.get("body") or "")
    if body:
        return body
    row = article_csv_rows.get(dp.normalize_title(article.get("title")))
    return row.get("News body", "") if row else ""


def row_for_error(
    *,
    error_type: str,
    article: dict[str, Any],
    article_csv_rows: dict[str, dict[str, str]],
    gold_ann: dict[str, Any] | None,
    pred_ann: dict[str, Any] | None,
    matched: bool,
) -> dict[str, Any]:
    paragraph_index = (
        gold_ann.get("paragraphIndex")
        if gold_ann and gold_ann.get("paragraphIndex") is not None
        else pred_ann.get("paragraphIndex")
        if pred_ann
        else ""
    )
    body = article_body(article, article_csv_rows)
    article_with_body = {**article, "news_body": body}
    return {
        "error_type": error_type,
        "news_title": article.get("title", ""),
        "news_body": body,
        "paragraph_index": paragraph_index,
        "paragraph_text": paragraph_text(article_with_body, paragraph_index),
        "intersection_ground_truth_label": annotation_label(gold_ann),
        "llm_predicted_label": annotation_label(pred_ann),
        "intersection_ground_truth_span": annotation_text(gold_ann),
        "llm_predicted_span": annotation_text(pred_ann),
        "intersection_ground_truth_category": annotation_category(gold_ann),
        "intersection_ground_truth_subcategory": annotation_subcategory(gold_ann),
        "llm_predicted_category": annotation_category(pred_ann),
        "llm_predicted_subcategory": annotation_subcategory(pred_ann),
        "matched_span_or_npl_paragraph": matched,
    }


def export_disagreements(
    *,
    gold_path: Path,
    predictions_path: Path,
    articles_csv: Path,
    output_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    gold_articles = read_json(gold_path)
    predicted_articles = read_json(predictions_path)
    article_csv_rows = read_articles_csv(articles_csv)

    gold = dp.flatten_articles(gold_articles, include_npl=True)
    pred = dp.flatten_articles(predicted_articles, include_npl=True)
    titles = sorted(title for title in set(gold) & set(pred) if gold[title]["annotations"])

    rows: list[dict[str, Any]] = []
    matched_total = 0
    category_mismatches = 0
    subcategory_mismatches = 0
    for title in titles:
        gold_article = gold[title]
        pred_article = pred[title]
        original_article = next(
            (article for article in gold_articles if dp.normalize_title(article.get("title")) == title),
            {"title": gold_article["title"], "annotations": gold_article["annotations"]},
        )
        gold_annotations = gold_article["annotations"]
        pred_annotations = pred_article["annotations"]
        pairs, unmatched_pred, unmatched_gold = dp.greedy_match(
            pred_annotations,
            gold_annotations,
            lambda p, g, t=title: dp.npl_aware_match(p, g, t),
        )
        matched_total += len(pairs)

        for pred_idx, gold_idx in pairs:
            pred_ann = pred_annotations[pred_idx]
            gold_ann = gold_annotations[gold_idx]
            category_diff = annotation_category(pred_ann) != annotation_category(gold_ann)
            subcategory_diff = annotation_subcategory(pred_ann) != annotation_subcategory(gold_ann)
            if not category_diff and not subcategory_diff:
                continue
            category_mismatches += int(category_diff)
            subcategory_mismatches += int(subcategory_diff)
            rows.append(
                row_for_error(
                    error_type="matched_span_label_mismatch",
                    article=original_article,
                    article_csv_rows=article_csv_rows,
                    gold_ann=gold_ann,
                    pred_ann=pred_ann,
                    matched=True,
                )
            )

        for gold_idx in sorted(unmatched_gold):
            rows.append(
                row_for_error(
                    error_type="missed_ground_truth",
                    article=original_article,
                    article_csv_rows=article_csv_rows,
                    gold_ann=gold_annotations[gold_idx],
                    pred_ann=None,
                    matched=False,
                )
            )

        for pred_idx in sorted(unmatched_pred):
            rows.append(
                row_for_error(
                    error_type="model_only_prediction",
                    article=original_article,
                    article_csv_rows=article_csv_rows,
                    gold_ann=None,
                    pred_ann=pred_annotations[pred_idx],
                    matched=False,
                )
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "error_type",
        "news_title",
        "news_body",
        "paragraph_index",
        "paragraph_text",
        "intersection_ground_truth_label",
        "llm_predicted_label",
        "intersection_ground_truth_span",
        "llm_predicted_span",
        "intersection_ground_truth_category",
        "intersection_ground_truth_subcategory",
        "llm_predicted_category",
        "llm_predicted_subcategory",
        "matched_span_or_npl_paragraph",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    metrics = dp.compare_predictions(predicted_articles, gold_articles, include_npl=True, title_policy="gold_nonempty")
    summary = {
        "gold_path": str(gold_path),
        "predictions_path": str(predictions_path),
        "output_csv": str(output_path),
        "titles_compared": len(titles),
        "disagreement_rows": len(rows),
        "error_type_counts": dict(Counter(row["error_type"] for row in rows)),
        "matched_span_or_npl_paragraph_count": matched_total,
        "category_mismatches_on_matched_units": category_mismatches,
        "subcategory_mismatches_on_matched_units": subcategory_mismatches,
        "metrics": metrics,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export NPL-inclusive disagreement rows between the intersection gold set and an LLM output."
    )
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--predictions", default=str(DEFAULT_PREDICTIONS))
    parser.add_argument("--articles-csv", default=str(DEFAULT_ARTICLES_CSV))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    args = parser.parse_args()

    summary = export_disagreements(
        gold_path=Path(args.gold),
        predictions_path=Path(args.predictions),
        articles_csv=Path(args.articles_csv),
        output_path=Path(args.output),
        summary_path=Path(args.summary),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
