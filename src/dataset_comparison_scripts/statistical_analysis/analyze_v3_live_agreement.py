import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape


DEFAULT_SUBMISSIONS_PATH = (
    "src/mturk_results/live/cisc475database-default-rtdb-submissions-export.json"
)
DEFAULT_LLM_ANNOTATIONS_PATH = (
    "src/llm_annotation_results/live/cisc475database-default-rtdb-LLMAnnotations-export.json"
)
DEFAULT_OUTPUT_DIR = "src/dataset_comparison_scripts/statistical_analysis/live"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze live v3 agreement data and generate summary visualizations."
    )
    parser.add_argument("--submissions", default=DEFAULT_SUBMISSIONS_PATH)
    parser.add_argument("--llm-annotations", default=DEFAULT_LLM_ANNOTATIONS_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def is_darwin_placeholder(text):
    return isinstance(text, str) and "DARWIN Symposium 2026" in text


def get_article_title(article_titles):
    if isinstance(article_titles, dict):
        for article_id, title in article_titles.items():
            if title:
                return str(article_id), title
    elif isinstance(article_titles, list):
        for index, title in enumerate(article_titles):
            if title:
                return str(index), title
    return None, "Unknown Article"


def collect_v3_submission_details(submission):
    details = {
        "has_open_feedback_1": False,
        "has_open_feedback_2": False,
        "darwin_placeholder": False,
        "correction_count": 0,
        "corrected_subcategories": [],
    }

    def walk(node):
        if isinstance(node, dict):
            open_feedback_1 = node.get("openFeedback1")
            open_feedback_2 = node.get("openFeedback2")

            if open_feedback_1 not in (None, ""):
                details["has_open_feedback_1"] = True
            if open_feedback_2 not in (None, ""):
                details["has_open_feedback_2"] = True
            if is_darwin_placeholder(open_feedback_1) or is_darwin_placeholder(
                open_feedback_2
            ):
                details["darwin_placeholder"] = True

            if "correctedSubcategory" in node:
                details["correction_count"] += 1
                details["corrected_subcategories"].append(node["correctedSubcategory"])

            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(submission.get("surveyResponses"))
    return details


def build_valid_v3_reviews(submissions_data):
    reviews = []

    for submission_key, submission in submissions_data.items():
        article_id, article_title = get_article_title(submission.get("articleTitles"))
        details = collect_v3_submission_details(submission)

        if not (
            details["has_open_feedback_1"] and details["has_open_feedback_2"]
        ):
            continue
        if details["darwin_placeholder"]:
            continue

        reviews.append(
            {
                "submission_key": submission_key,
                "article_id": article_id,
                "article_title": article_title,
                "correction_count": details["correction_count"],
                "corrected_subcategories": details["corrected_subcategories"],
                "timestamp": submission.get("timestamp"),
            }
        )

    return reviews


def flatten_llm_annotations(llm_annotations_data):
    flattened = []

    for group_index, group in enumerate(llm_annotations_data):
        for annotation_index, annotation in enumerate(group):
            accept = int(annotation.get("accept", 0))
            deny = int(annotation.get("deny", 0))
            total = accept + deny
            accept_rate = accept / total if total else 0.0
            flattened.append(
                {
                    "group_index": group_index,
                    "annotation_index": annotation_index,
                    "subcategory": annotation.get("subcategory", "Unknown"),
                    "span": annotation.get("span", ""),
                    "accept": accept,
                    "deny": deny,
                    "total": total,
                    "accept_rate": accept_rate,
                }
            )

    return flattened


def truncate_text(text, max_len):
    text = " ".join(str(text).split())
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1].rstrip()}…"


def compute_summary(valid_reviews, flattened_llm_annotations):
    article_outcomes = defaultdict(lambda: {"agree": 0, "corrected": 0, "correction_entries": 0})
    corrected_subcategories = Counter()

    for review in valid_reviews:
        article_title = review["article_title"]
        if review["correction_count"] > 0:
            article_outcomes[article_title]["corrected"] += 1
        else:
            article_outcomes[article_title]["agree"] += 1
        article_outcomes[article_title]["correction_entries"] += review["correction_count"]
        corrected_subcategories.update(review["corrected_subcategories"])

    total_reviews = len(valid_reviews)
    reviews_with_corrections = sum(1 for review in valid_reviews if review["correction_count"] > 0)
    total_corrections = sum(review["correction_count"] for review in valid_reviews)

    total_accept = sum(annotation["accept"] for annotation in flattened_llm_annotations)
    total_deny = sum(annotation["deny"] for annotation in flattened_llm_annotations)
    total_binary_votes = total_accept + total_deny

    binary_outcome_buckets = {
        "unanimous_accept": 0,
        "majority_accept": 0,
        "tied": 0,
        "majority_deny": 0,
    }
    binary_by_subcategory = defaultdict(lambda: {"accept": 0, "deny": 0, "instances": 0})

    for annotation in flattened_llm_annotations:
        accept = annotation["accept"]
        deny = annotation["deny"]
        if deny == 0:
            binary_outcome_buckets["unanimous_accept"] += 1
        elif accept > deny:
            binary_outcome_buckets["majority_accept"] += 1
        elif accept == deny:
            binary_outcome_buckets["tied"] += 1
        else:
            binary_outcome_buckets["majority_deny"] += 1

        subcategory = annotation["subcategory"]
        binary_by_subcategory[subcategory]["accept"] += accept
        binary_by_subcategory[subcategory]["deny"] += deny
        binary_by_subcategory[subcategory]["instances"] += 1

    top_disputed_annotations = sorted(
        flattened_llm_annotations,
        key=lambda row: (-row["deny"], row["accept_rate"], -row["total"], row["subcategory"], row["span"]),
    )[:12]

    return {
        "valid_v3_review_submissions": total_reviews,
        "reviews_with_any_subcategory_correction": reviews_with_corrections,
        "full_agreement_review_submissions": total_reviews - reviews_with_corrections,
        "review_level_full_agreement_rate": (
            (total_reviews - reviews_with_corrections) / total_reviews if total_reviews else 0.0
        ),
        "review_level_correction_rate": (
            reviews_with_corrections / total_reviews if total_reviews else 0.0
        ),
        "total_subcategory_corrections": total_corrections,
        "corrected_subcategory_counts": dict(corrected_subcategories),
        "article_review_outcomes": dict(sorted(article_outcomes.items(), key=lambda item: item[0])),
        "binary_accept_total": total_accept,
        "binary_deny_total": total_deny,
        "binary_accept_rate": (total_accept / total_binary_votes if total_binary_votes else 0.0),
        "binary_vote_total": total_binary_votes,
        "binary_annotation_instances": len(flattened_llm_annotations),
        "binary_outcome_buckets": binary_outcome_buckets,
        "binary_by_subcategory": {
            key: {
                **value,
                "accept_rate": (
                    value["accept"] / (value["accept"] + value["deny"])
                    if (value["accept"] + value["deny"])
                    else 0.0
                ),
            }
            for key, value in sorted(binary_by_subcategory.items(), key=lambda item: item[0])
        },
        "top_disputed_binary_annotations": top_disputed_annotations,
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def svg_header(width, height):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>',
        'text { font-family: Arial, sans-serif; fill: #1f2937; }',
        '.title { font-size: 18px; font-weight: 700; }',
        '.subtitle { font-size: 11px; fill: #4b5563; }',
        '.label { font-size: 11px; }',
        '.small { font-size: 10px; fill: #4b5563; }',
        '.value { font-size: 11px; font-weight: 700; }',
        '</style>',
    ]


def render_article_outcomes_svg(path, article_rows):
    width = 1200
    row_height = 44
    top_margin = 90
    left_margin = 420
    right_margin = 140
    bottom_margin = 40
    chart_width = width - left_margin - right_margin
    height = top_margin + bottom_margin + len(article_rows) * row_height
    max_reviews = max((row["agree"] + row["corrected"] for row in article_rows), default=1)
    scale = chart_width / max_reviews

    svg = svg_header(width, height)
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />')
    svg.append('<text x="40" y="34" class="title">V3 Review Outcomes By Article</text>')
    svg.append(
        '<text x="40" y="54" class="subtitle">Each bar shows valid v3 human reviews with no subcategory correction versus reviews that changed at least one provided LLM label.</text>'
    )

    for tick in range(max_reviews + 1):
        x = left_margin + tick * scale
        svg.append(
            f'<line x1="{x}" y1="{top_margin - 8}" x2="{x}" y2="{height - bottom_margin + 4}" stroke="#e5e7eb" stroke-width="1" />'
        )
        svg.append(
            f'<text x="{x}" y="{height - 14}" text-anchor="middle" class="small">{tick}</text>'
        )

    legend_y = 76
    svg.append('<rect x="40" y="66" width="12" height="12" fill="#2a9d8f" rx="2" />')
    svg.append('<text x="58" y="76" class="small">Fully agreed with LLM</text>')
    svg.append('<rect x="190" y="66" width="12" height="12" fill="#e76f51" rx="2" />')
    svg.append('<text x="208" y="76" class="small">Made subcategory correction(s)</text>')

    for index, row in enumerate(article_rows):
        y = top_margin + index * row_height
        bar_y = y - 8
        agree_width = row["agree"] * scale
        corrected_width = row["corrected"] * scale
        total_reviews = row["agree"] + row["corrected"]
        correction_rate = row["corrected"] / total_reviews if total_reviews else 0.0

        svg.append(
            f'<text x="{left_margin - 14}" y="{y}" text-anchor="end" class="label">{escape(truncate_text(row["article_title"], 64))}</text>'
        )
        svg.append(
            f'<rect x="{left_margin}" y="{bar_y}" width="{agree_width}" height="16" fill="#2a9d8f" rx="3" />'
        )
        svg.append(
            f'<rect x="{left_margin + agree_width}" y="{bar_y}" width="{corrected_width}" height="16" fill="#e76f51" rx="3" />'
        )
        svg.append(
            f'<text x="{left_margin + agree_width + corrected_width + 8}" y="{y}" class="small">{row["corrected"]}/{total_reviews} corrected, {row["correction_entries"]} correction entries ({correction_rate:.0%})</text>'
        )

    svg.append("</svg>")
    path.write_text("\n".join(svg), encoding="utf-8")


def render_disputed_spans_svg(path, disputed_rows):
    width = 1300
    row_height = 42
    top_margin = 90
    left_margin = 540
    right_margin = 180
    bottom_margin = 40
    chart_width = width - left_margin - right_margin
    height = top_margin + bottom_margin + len(disputed_rows) * row_height

    svg = svg_header(width, height)
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />')
    svg.append('<text x="40" y="34" class="title">Most Disputed Binary Agreement Cases</text>')
    svg.append(
        '<text x="40" y="54" class="subtitle">Top v3 LLM-provided annotation spans ranked by highest deny count, then lowest accept rate. Bars show binary accept rate.</text>'
    )

    for percent in range(0, 101, 25):
        x = left_margin + (percent / 100.0) * chart_width
        svg.append(
            f'<line x1="{x}" y1="{top_margin - 8}" x2="{x}" y2="{height - bottom_margin + 4}" stroke="#e5e7eb" stroke-width="1" />'
        )
        svg.append(
            f'<text x="{x}" y="{height - 14}" text-anchor="middle" class="small">{percent}%</text>'
        )

    for index, row in enumerate(disputed_rows):
        y = top_margin + index * row_height
        bar_y = y - 8
        bar_width = row["accept_rate"] * chart_width
        if row["accept_rate"] >= 0.8:
            fill = "#2a9d8f"
        elif row["accept_rate"] >= 0.5:
            fill = "#e9c46a"
        else:
            fill = "#e76f51"

        label = f'{row["subcategory"]} | {truncate_text(row["span"], 62)}'
        counts = f'{row["accept"]} accept / {row["deny"]} deny'
        svg.append(
            f'<text x="{left_margin - 14}" y="{y}" text-anchor="end" class="label">{escape(label)}</text>'
        )
        svg.append(
            f'<rect x="{left_margin}" y="{bar_y}" width="{bar_width}" height="16" fill="{fill}" rx="3" />'
        )
        svg.append(
            f'<text x="{left_margin + chart_width + 10}" y="{y}" class="small">{counts} ({row["accept_rate"]:.0%})</text>'
        )

    svg.append("</svg>")
    path.write_text("\n".join(svg), encoding="utf-8")


def render_subcategory_disagreement_svg(path, subcategory_rows):
    width = 1100
    row_height = 46
    top_margin = 90
    left_margin = 300
    right_margin = 200
    bottom_margin = 40
    chart_width = width - left_margin - right_margin
    height = top_margin + bottom_margin + len(subcategory_rows) * row_height

    svg = svg_header(width, height)
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />')
    svg.append('<text x="40" y="34" class="title">Binary Disagreement By LLM Subcategory</text>')
    svg.append(
        '<text x="40" y="54" class="subtitle">Aggregate deny rate for each LLM-provided subcategory label in the live v3 binary agreement node.</text>'
    )

    for percent in range(0, 101, 25):
        x = left_margin + (percent / 100.0) * chart_width
        svg.append(
            f'<line x1="{x}" y1="{top_margin - 8}" x2="{x}" y2="{height - bottom_margin + 4}" stroke="#e5e7eb" stroke-width="1" />'
        )
        svg.append(
            f'<text x="{x}" y="{height - 14}" text-anchor="middle" class="small">{percent}%</text>'
        )

    for index, row in enumerate(subcategory_rows):
        y = top_margin + index * row_height
        bar_y = y - 8
        bar_width = row["deny_rate"] * chart_width

        if row["deny_rate"] >= 0.3:
            fill = "#e76f51"
        elif row["deny_rate"] >= 0.15:
            fill = "#e9c46a"
        else:
            fill = "#2a9d8f"

        svg.append(
            f'<text x="{left_margin - 14}" y="{y}" text-anchor="end" class="label">{escape(row["subcategory"])}</text>'
        )
        svg.append(
            f'<rect x="{left_margin}" y="{bar_y}" width="{bar_width}" height="16" fill="{fill}" rx="3" />'
        )
        svg.append(
            f'<text x="{left_margin + chart_width + 10}" y="{y}" class="small">{row["deny"]} deny / {row["total"]} votes across {row["instances"]} spans ({row["deny_rate"]:.0%})</text>'
        )

    svg.append("</svg>")
    path.write_text("\n".join(svg), encoding="utf-8")


def main():
    args = parse_args()
    submissions_data = load_json(args.submissions)
    llm_annotations_data = load_json(args.llm_annotations)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    valid_reviews = build_valid_v3_reviews(submissions_data)
    flattened_llm_annotations = flatten_llm_annotations(llm_annotations_data)
    summary = compute_summary(valid_reviews, flattened_llm_annotations)

    article_rows = [
        {
            "article_title": article_title,
            "agree": stats["agree"],
            "corrected": stats["corrected"],
            "correction_entries": stats["correction_entries"],
        }
        for article_title, stats in sorted(
            summary["article_review_outcomes"].items(),
            key=lambda item: (
                -(item[1]["corrected"]),
                -(item[1]["agree"]),
                item[0],
            ),
        )
    ]

    disputed_rows = summary["top_disputed_binary_annotations"]
    subcategory_rows = [
        {
            "subcategory": subcategory,
            "instances": stats["instances"],
            "accept": stats["accept"],
            "deny": stats["deny"],
            "total": stats["accept"] + stats["deny"],
            "accept_rate": stats["accept_rate"],
            "deny_rate": (
                stats["deny"] / (stats["accept"] + stats["deny"])
                if (stats["accept"] + stats["deny"])
                else 0.0
            ),
        }
        for subcategory, stats in sorted(
            summary["binary_by_subcategory"].items(),
            key=lambda item: (
                -(
                    item[1]["deny"] / (item[1]["accept"] + item[1]["deny"])
                    if (item[1]["accept"] + item[1]["deny"])
                    else 0.0
                ),
                -item[1]["deny"],
                item[0],
            ),
        )
    ]

    write_json(output_dir / "v3_live_agreement_summary.json", summary)
    write_csv(
        output_dir / "v3_article_review_outcomes.csv",
        article_rows,
        ["article_title", "agree", "corrected", "correction_entries"],
    )
    write_csv(
        output_dir / "v3_top_disputed_binary_annotations.csv",
        disputed_rows,
        [
            "group_index",
            "annotation_index",
            "subcategory",
            "span",
            "accept",
            "deny",
            "total",
            "accept_rate",
        ],
    )
    write_csv(
        output_dir / "v3_binary_disagreement_by_subcategory.csv",
        subcategory_rows,
        [
            "subcategory",
            "instances",
            "accept",
            "deny",
            "total",
            "accept_rate",
            "deny_rate",
        ],
    )

    render_article_outcomes_svg(
        output_dir / "v3_article_review_outcomes.svg",
        article_rows,
    )
    render_disputed_spans_svg(
        output_dir / "v3_most_disputed_binary_spans.svg",
        disputed_rows,
    )
    render_subcategory_disagreement_svg(
        output_dir / "v3_binary_disagreement_by_subcategory.svg",
        subcategory_rows,
    )

    print(f"Wrote summary and visualizations to {output_dir}")


if __name__ == "__main__":
    main()
