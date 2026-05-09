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


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Create pre-adjudication subcategory-level agree/disagree IRR "
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


def build_subcategory_rows(flattened_annotations, *, min_votes, exact_votes):
    by_subcategory = defaultdict(list)
    for row in flattened_annotations:
        total_votes = int(row["total_votes"])
        if total_votes < min_votes:
            continue
        if exact_votes is not None and total_votes != exact_votes:
            continue
        by_subcategory[row["subcategory"]].append(row)

    rows = []
    for subcategory, items in by_subcategory.items():
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
        alpha = base.krippendorff_alpha_nominal(ratings)
        rows.append(
            {
                "subcategory": subcategory,
                "unit_count": len(items),
                "accept_votes": accept_sum,
                "deny_votes": deny_sum,
                "pairwise_percent_agreement": pairwise,
                "pairwise_percent_disagreement": (1.0 - pairwise) if pairwise is not None else None,
                "exact_consensus_rate": exact_consensus / len(items) if items else None,
                "krippendorff_alpha_nominal": alpha,
            }
        )

    order_lookup = {label: index for index, label in enumerate(SUBCATEGORY_ORDER)}
    rows.sort(
        key=lambda item: (
            order_lookup.get(item["subcategory"], len(SUBCATEGORY_ORDER)),
            item["subcategory"],
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
        ".small { font-size: 10px; fill: #4b5563; }",
        "</style>",
    ]


def render_svg(path, rows, *, min_votes, exact_votes):
    width = 1460
    height = 760
    left_margin = 110
    right_margin = 120
    top_margin = 110
    bottom_margin = 250
    plot_left = left_margin
    plot_right = width - right_margin
    plot_top = top_margin
    plot_bottom = height - bottom_margin
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    if exact_votes is None:
        filter_text = f"Rows with at least {min_votes} total votes."
    else:
        filter_text = f"Rows with exactly {exact_votes} total votes."

    def y_pairwise(value):
        clamped = max(0.0, min(1.0, value))
        return plot_top + (1.0 - clamped) * plot_height

    alpha_min = -1.0
    alpha_max = 1.0

    def y_alpha(value):
        if value is None:
            return None
        clamped = max(alpha_min, min(alpha_max, value))
        normalized = (clamped - alpha_min) / (alpha_max - alpha_min)
        return plot_top + (1.0 - normalized) * plot_height

    svg = svg_header(width, height)
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />')
    svg.append(
        '<text x="40" y="36" class="title">Pre-Adjudication IRR by Subcategory (Agree/Disagree)</text>'
    )
    svg.append(
        f'<text x="40" y="56" class="subtitle">Binary accept/deny reliability by subcategory. {escape(filter_text)}</text>'
    )
    svg.append('<rect x="40" y="72" width="16" height="10" fill="#059669" />')
    svg.append('<text x="62" y="81" class="small">Pairwise agreement (left axis)</text>')
    svg.append('<line x1="275" y1="77" x2="291" y2="77" stroke="#f59e0b" stroke-width="2.5" />')
    svg.append('<text x="297" y="81" class="small">Krippendorff\'s alpha (right axis)</text>')

    for tick in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = y_pairwise(tick)
        svg.append(
            f'<line x1="{plot_left}" y1="{y:.2f}" x2="{plot_right}" y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1" />'
        )
        svg.append(
            f'<text x="{plot_left - 12}" y="{y + 4:.2f}" text-anchor="end" class="small">{tick:.1f}</text>'
        )
    for tick in [-1.0, -0.5, 0.0, 0.5, 1.0]:
        y = y_alpha(tick)
        svg.append(
            f'<text x="{plot_right + 12}" y="{y + 4:.2f}" text-anchor="start" class="small">{tick:.1f}</text>'
        )

    svg.append(
        f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_bottom}" stroke="#374151" stroke-width="1.5" />'
    )
    svg.append(
        f'<line x1="{plot_right}" y1="{plot_top}" x2="{plot_right}" y2="{plot_bottom}" stroke="#374151" stroke-width="1.5" />'
    )
    svg.append(
        f'<line x1="{plot_left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" stroke="#374151" stroke-width="1.5" />'
    )
    svg.append(f'<text x="{plot_left - 70}" y="{plot_top - 10}" class="small">Pairwise agreement</text>')
    svg.append(f'<text x="{plot_right + 14}" y="{plot_top - 10}" class="small">Alpha</text>')

    if not rows:
        svg.append(f'<text x="{plot_left}" y="{plot_top + 20}" class="small">No rows after filtering.</text>')
        svg.append("</svg>")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(svg), encoding="utf-8")
        return

    step = plot_width / len(rows)
    bar_width = step * 0.58
    alpha_points = []

    for index, row in enumerate(rows):
        x_center = plot_left + step * (index + 0.5)
        pairwise = row["pairwise_percent_agreement"] or 0.0
        y_bar_top = y_pairwise(pairwise)
        bar_left = x_center - (bar_width / 2)
        bar_height = plot_bottom - y_bar_top

        if bar_height > 0:
            svg.append(
                f'<rect x="{bar_left:.2f}" y="{y_bar_top:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" fill="#059669" opacity="0.9" />'
            )
        alpha_y = y_alpha(row["krippendorff_alpha_nominal"])
        if alpha_y is not None:
            alpha_points.append((x_center, alpha_y))

        label = f"{row['subcategory']} (n={row['unit_count']})"
        svg.append(
            f'<text x="{x_center + 4:.2f}" y="{plot_bottom + 18}" transform="rotate(55 {x_center + 4:.2f} {plot_bottom + 18})" class="small">{escape(label)}</text>'
        )
        svg.append(
            f'<text x="{x_center:.2f}" y="{y_bar_top - 6:.2f}" text-anchor="middle" class="small">{pairwise:.2f}</text>'
        )

    if len(alpha_points) >= 2:
        path_d = " ".join(
            (
                f"M {alpha_points[0][0]:.2f} {alpha_points[0][1]:.2f}",
                *[f"L {x:.2f} {y:.2f}" for x, y in alpha_points[1:]],
            )
        )
        svg.append(f'<path d="{path_d}" fill="none" stroke="#f59e0b" stroke-width="2.5" />')
    for x, y in alpha_points:
        svg.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#f59e0b" stroke="#ffffff" stroke-width="1" />'
        )

    svg.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(svg), encoding="utf-8")


def main():
    args = parse_args()
    raw = live.load_json(args.annotations)
    flattened = live.flatten_in_house_annotations(raw)
    rows = build_subcategory_rows(flattened, min_votes=args.min_votes, exact_votes=args.exact_votes)

    output_dir = Path(args.output_dir)
    csv_path = output_dir / "in_house_pre_adjudication_subcategory_binary_irr.csv"
    svg_path = output_dir / "in_house_pre_adjudication_subcategory_binary_irr.svg"

    write_csv(
        csv_path,
        rows,
        fieldnames=[
            "subcategory",
            "unit_count",
            "accept_votes",
            "deny_votes",
            "pairwise_percent_agreement",
            "pairwise_percent_disagreement",
            "exact_consensus_rate",
            "krippendorff_alpha_nominal",
        ],
    )
    render_svg(svg_path, rows, min_votes=args.min_votes, exact_votes=args.exact_votes)

    print(f"Wrote {csv_path}")
    print(f"Wrote {svg_path}")


if __name__ == "__main__":
    main()
