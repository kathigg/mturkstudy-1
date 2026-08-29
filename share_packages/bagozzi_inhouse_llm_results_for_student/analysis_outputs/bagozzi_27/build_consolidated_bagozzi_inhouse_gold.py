from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
DEFAULT_ARTICLES_CSV = REPO / "src/dataset_comparison_scripts/2-20/2-20_selected_articles.csv"
DEFAULT_AGREED_SPANS = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "inhouse_bagozzi_agreed_polarizing_spans.csv"
)
DEFAULT_OUTPUT = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "consolidated_bagozzi_inhouse_overlap_gold_standard_output.json"
)
DEFAULT_SUMMARY = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    / "consolidated_bagozzi_inhouse_overlap_gold_summary.json"
)


def normalize_title(text: str | None) -> str:
    return re.sub(r"[^\w\s]", "", text or "").strip().lower()


def normalize_label(text: str | None) -> str:
    return re.sub(r"[_-]+", " ", text or "").strip().lower()


def canonical_category(text: str | None) -> str:
    label = normalize_label(text)
    if label == "inflammatory language":
        return "Inflammatory Language"
    if label == "persuasive propaganda":
        return "Persuasive Propaganda"
    if label == "no polarizing language":
        return "No Polarizing language"
    return (text or "").strip()


def canonical_subcategory(text: str | None) -> str:
    label = normalize_label(text)
    mapping = {
        "causal oversimplification": "casual oversimplification",
        "casual oversimplification": "casual oversimplification",
        "name calling": "name-calling",
        "name-calling": "name-calling",
        "no polarizing language": "no polarizing language",
    }
    if label in mapping:
        return mapping[label]
    if label in {"exaggeration", "slogans", "bandwagon", "doubt", "demonization", "scapegoating"}:
        return label
    if (text or "").strip().lower() == "name-calling":
        return "name-calling"
    if label == "causal oversimplification":
        return "casual oversimplification"
    return label


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_gold(articles_csv: Path, agreed_spans_csv: Path) -> tuple[list[dict], dict]:
    article_rows = read_csv(articles_csv)
    article_by_norm = {normalize_title(row.get("Headline")): row for row in article_rows}

    annotations_by_title: dict[str, list[dict]] = defaultdict(list)
    unmatched_titles = set()
    for row in read_csv(agreed_spans_csv):
        title = row.get("article_title", "")
        norm = normalize_title(title)
        if norm not in article_by_norm:
            unmatched_titles.add(title)
            continue

        annotation = {
            "paragraphIndex": int(float(row["paragraph_index"])),
            "text": (row.get("agreed_text") or row.get("bagozzi_text") or row.get("inhouse_text") or "").strip(),
            "category": canonical_category(row.get("category") or row.get("bagozzi_category")),
            "subcategory": canonical_subcategory(row.get("subcategory") or row.get("bagozzi_subcategory")),
            "confidence": 1.0,
            "num_supporters": 2,
            "label_source": "dr_bagozzi_priority",
            "match_basis": "span overlap between Dr. Bagozzi and final in-house adjudicated annotations",
            "bagozzi_text": row.get("bagozzi_text", ""),
            "inhouse_text": row.get("inhouse_text", ""),
            "bagozzi_category": row.get("bagozzi_category", ""),
            "bagozzi_subcategory": row.get("bagozzi_subcategory", ""),
            "inhouse_category": row.get("inhouse_category", ""),
            "inhouse_subcategory": row.get("inhouse_subcategory", ""),
            "inhouse_vote_pattern": row.get("inhouse_vote_pattern", ""),
        }
        annotations_by_title[norm].append(annotation)

    articles = []
    for row in article_rows:
        norm = normalize_title(row.get("Headline"))
        annotations = annotations_by_title.get(norm, [])
        articles.append(
            {
                "title": row.get("Headline", ""),
                "news_body": row.get("News body", ""),
                "topic": row.get("Topic", ""),
                "source": row.get("News Source", ""),
                "rating": row.get("Rating", ""),
                "annotations": annotations,
            }
        )

    all_annotations = [ann for article in articles for ann in article["annotations"]]
    summary = {
        "definition": "Consolidated Bagozzi/final in-house overlap gold. Includes only polarizing spans where Dr. Bagozzi and final in-house adjudicated annotations overlap. Labels use the agreed CSV category/subcategory, which is Bagozzi-priority when labels differ.",
        "article_count": len(articles),
        "articles_with_annotations": sum(1 for article in articles if article["annotations"]),
        "annotation_count": len(all_annotations),
        "category_counts": dict(Counter(ann["category"] for ann in all_annotations)),
        "subcategory_counts": dict(Counter(ann["subcategory"] for ann in all_annotations)),
        "unmatched_overlap_titles": sorted(unmatched_titles),
        "inputs": {
            "articles_csv": str(articles_csv),
            "agreed_spans_csv": str(agreed_spans_csv),
        },
    }
    return articles, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--articles-csv", default=str(DEFAULT_ARTICLES_CSV))
    parser.add_argument("--agreed-spans-csv", default=str(DEFAULT_AGREED_SPANS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    args = parser.parse_args()

    output = Path(args.output)
    summary_path = Path(args.summary)
    articles, summary = build_gold(Path(args.articles_csv), Path(args.agreed_spans_csv))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(articles, indent=2, ensure_ascii=False), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({**summary, "output": str(output), "summary": str(summary_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
