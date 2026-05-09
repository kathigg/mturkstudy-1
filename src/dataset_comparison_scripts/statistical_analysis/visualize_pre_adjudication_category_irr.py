import argparse
import csv
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

import analyze_in_house_live_validation as live
import in_house_density_and_agreement as base


DEFAULT_ANNOTATIONS_PATH = (
    "src/mturk_results/live/cisc475database-default-rtdb-InHouse-Annotations-export.json"
)
DEFAULT_OUTPUT_DIR = "src/dataset_comparison_scripts/statistical_analysis/live"


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Create pre-adjudication category-level agree/disagree IRR "
            "visualization from in-house live annotation votes."
        )
    )
    parser.add_argument("--annotations", default=DEFAULT_ANNOTATIONS_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--min-votes",
        type=int,
        default=2,
        help="Minimum accept+deny votes required for an annotation row to be included.",
    )
    parser.add_argument(
        "--exact-votes",
        type=int,
        default=None,
        help="If set, only include rows with exactly this many total votes.",
    )
    return parser.parse_args()


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def format_pct(value):
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def format_float(value):
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def build_category_rows(flattened_annotations, *, min_votes, exact_votes):
    by_category = defaultdict(list)
    for row in flattened_annotations:
        total_votes = int(row["total_votes"])
        if total_votes < min_votes:
            continue
        if exact_votes is not None and total_votes != exact_votes:
            continue
        by_category[row["category"]].append(row)

    rows = []
    for category, items in by_category.items():
        ratings = []
        accept_sum = 0
        deny_sum = 0
        exact_consensus = 0

        for item in items:
            accept = int(item["accept"])
            deny = int(item["deny"])
            accept_sum += accept
            deny_sum += deny
            ratings.append((["accept"] * accept) + (["deny"] * deny))
            if accept == 0 or deny == 0:
                exact_consensus += 1

        pairwise = base.pairwise_percent_agreement(ratings)
        disagreement = (1.0 - pairwise) if pairwise is not None else None
        alpha = base.krippendorff_alpha_nominal(ratings)
        exact_consensus_rate = exact_consensus / len(items) if items else None

        rows.append(
            {
                "category": category,
                "unit_count": len(items),
                "accept_votes": accept_sum,
                "deny_votes": deny_sum,
                "pairwise_percent_agreement": pairwise,
                "pairwise_percent_disagreement": disagreement,
                "exact_consensus_rate": exact_consensus_rate,
                "krippendorff_alpha_nominal": alpha,
            }
        )

    rows.sort(
        key=lambda item: (
            -(item["pairwise_percent_disagreement"] or -1.0),
            item["category"],
        )
    )
    return rows


def svg_header(width, height):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, sans-serif; fill: #1f2937; }",
        ".title { font-size: 19px; font-weight: 700; }",
        ".subtitle { font-size: 11px; fill: #4b5563; }",
        ".label { font-size: 12px; }",
        ".small { font-size: 10px; fill: #4b5563; }",
        ".value { font-size: 11px; font-weight: 700; }",
        "</style>",
    ]


def render_svg(path, rows, *, min_votes, exact_votes):
    width = 1180
    left_margin = 360
    right_margin = 40
    top_margin = 112
    row_height = 44
    bar_height = 18
    bottom_margin = 44
    bar_width = width - left_margin - right_margin
    height = top_margin + (len(rows) * row_height) + bottom_margin

    if exact_votes is None:
        filter_text = f"Rows with at least {min_votes} total votes."
    else:
        filter_text = f"Rows with exactly {exact_votes} total votes."

    svg = svg_header(width, height)
    svg.append(
        '<text x="40" y="36" class="title">Pre-Adjudication IRR by Category (Binary Accept vs Deny)</text>'
    )
    svg.append(
        f'<text x="40" y="56" class="subtitle">Pairwise agreement/disagreement on raw in-house annotations. {escape(filter_text)}</text>'
    )
    svg.append(
        '<rect x="40" y="72" width="16" height="10" fill="#10b981" />'
    )
    svg.append('<text x="62" y="81" class="small">Agree</text>')
    svg.append(
        '<rect x="120" y="72" width="16" height="10" fill="#ef4444" />'
    )
    svg.append('<text x="142" y="81" class="small">Disagree</text>')

    for index, row in enumerate(rows):
        y = top_margin + (index * row_height)
        label_y = y + 14
        bar_y = y + 20
        agree = row["pairwise_percent_agreement"] or 0.0
        disagree = row["pairwise_percent_disagreement"] or 0.0
        agree_width = max(0.0, min(bar_width, bar_width * agree))
        disagree_width = max(0.0, min(bar_width - agree_width, bar_width * disagree))

        svg.append(
            f'<text x="{left_margin - 14}" y="{label_y}" text-anchor="end" class="label">'
            f'{escape(row["category"])} (n={row["unit_count"]})</text>'
        )
        svg.append(
            f'<rect x="{left_margin}" y="{bar_y}" width="{bar_width}" height="{bar_height}" fill="#e5e7eb" />'
        )
        if agree_width > 0:
            svg.append(
                f'<rect x="{left_margin}" y="{bar_y}" width="{agree_width}" height="{bar_height}" fill="#10b981" />'
            )
        if disagree_width > 0:
            svg.append(
                f'<rect x="{left_margin + agree_width}" y="{bar_y}" width="{disagree_width}" height="{bar_height}" fill="#ef4444" />'
            )

        value_text = (
            f"agree {format_pct(row['pairwise_percent_agreement'])} | "
            f"disagree {format_pct(row['pairwise_percent_disagreement'])} | "
            f"alpha {format_float(row['krippendorff_alpha_nominal'])}"
        )
        svg.append(
            f'<text x="{left_margin + bar_width + 10}" y="{bar_y + 13}" class="value">{escape(value_text)}</text>'
        )

    svg.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(svg), encoding="utf-8")


def main():
    args = parse_args()
    raw = live.load_json(args.annotations)
    flattened = live.flatten_in_house_annotations(raw)
    rows = build_category_rows(
        flattened,
        min_votes=args.min_votes,
        exact_votes=args.exact_votes,
    )

    output_dir = Path(args.output_dir)
    csv_path = output_dir / "in_house_pre_adjudication_category_binary_irr.csv"
    svg_path = output_dir / "in_house_pre_adjudication_category_binary_irr.svg"

    write_csv(
        csv_path,
        rows,
        fieldnames=[
            "category",
            "unit_count",
            "accept_votes",
            "deny_votes",
            "pairwise_percent_agreement",
            "pairwise_percent_disagreement",
            "exact_consensus_rate",
            "krippendorff_alpha_nominal",
        ],
    )
    render_svg(
        svg_path,
        rows,
        min_votes=args.min_votes,
        exact_votes=args.exact_votes,
    )

    print(f"Wrote {csv_path}")
    print(f"Wrote {svg_path}")


if __name__ == "__main__":
    main()
