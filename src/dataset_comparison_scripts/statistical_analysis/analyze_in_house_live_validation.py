import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import in_house_density_and_agreement as base


DEFAULT_ANNOTATIONS_PATH = (
    "src/mturk_results/live/cisc475database-default-rtdb-InHouse-Annotations-export.json"
)
DEFAULT_SUBMISSIONS_PATH = (
    "src/mturk_results/live/cisc475database-default-rtdb-InHouse-Submissions-export.json"
)
DEFAULT_OUTPUT_DIR = "src/dataset_comparison_scripts/statistical_analysis/live"

SUBCATEGORY_TO_CATEGORY = {
    "exaggeration": "persuasive propaganda",
    "slogans": "persuasive propaganda",
    "bandwagon": "persuasive propaganda",
    "casual oversimplification": "persuasive propaganda",
    "doubt": "persuasive propaganda",
    "name-calling": "inflammatory language",
    "demonization": "inflammatory language",
    "scapegoating": "inflammatory language",
    "no polarizing language": "no polarizing language",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Analyze the live in-house validation node, including a consolidated "
            "final human-approved annotation set."
        )
    )
    parser.add_argument("--annotations", default=DEFAULT_ANNOTATIONS_PATH)
    parser.add_argument("--submissions", default=DEFAULT_SUBMISSIONS_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


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


def normalize_subcategory(label):
    return base.normalize_label(label)


def derive_category(subcategory):
    return SUBCATEGORY_TO_CATEGORY.get(subcategory, "")


def flatten_in_house_annotations(raw_annotations):
    flattened = []
    for article_index, article in enumerate(raw_annotations):
        if not isinstance(article, list):
            continue
        for paragraph_index, paragraph in enumerate(article):
            if not isinstance(paragraph, list):
                continue
            for annotation in paragraph:
                if not isinstance(annotation, dict):
                    continue
                subcategory = normalize_subcategory(annotation.get("subcategory"))
                accept = int(annotation.get("accept", 0) or 0)
                deny = int(annotation.get("deny", 0) or 0)
                total_votes = accept + deny
                flattened.append(
                    {
                        "article_index": article_index,
                        "paragraph_index": paragraph_index,
                        "text": annotation.get("span", ""),
                        "subcategory": subcategory,
                        "category": derive_category(subcategory),
                        "meta": annotation.get("meta", ""),
                        "accept": accept,
                        "deny": deny,
                        "total_votes": total_votes,
                        "accept_rate": (accept / total_votes) if total_votes else 0.0,
                    }
                )
    return flattened


def build_article_title_mapping(submissions):
    mapping = {}

    for submission in submissions.values():
        article_titles = submission.get("articleTitles")
        if isinstance(article_titles, list):
            for article_index, title in enumerate(article_titles):
                if title:
                    mapping.setdefault(article_index, title)
        elif isinstance(article_titles, dict):
            for article_index, title in article_titles.items():
                if title:
                    mapping.setdefault(int(article_index), title)

    return mapping


def raw_status(annotation):
    if annotation["total_votes"] == 0:
        return "no_votes"
    if annotation["accept"] > annotation["deny"]:
        return "majority_accept"
    if annotation["accept"] < annotation["deny"]:
        return "majority_deny"
    return "tie"


def representative_rank(annotation):
    return (
        annotation["accept_rate"],
        annotation["accept"],
        -annotation["deny"],
        len(base.normalize_span(annotation["text"])),
        annotation["meta"],
    )


def cluster_annotations(paragraph_annotations):
    clusters = []
    used = [False] * len(paragraph_annotations)

    for index, anchor in enumerate(paragraph_annotations):
        if used[index]:
            continue

        used[index] = True
        cluster = [anchor]

        for compare_index, candidate in enumerate(paragraph_annotations[index + 1 :], start=index + 1):
            if used[compare_index]:
                continue
            if anchor["subcategory"] != candidate["subcategory"]:
                continue
            if base.spans_match(anchor, candidate, include_npl=True):
                used[compare_index] = True
                cluster.append(candidate)

        clusters.append(cluster)

    return clusters


def consolidate_annotations(flattened_annotations, article_title_mapping):
    paragraph_buckets = defaultdict(list)
    for annotation in flattened_annotations:
        paragraph_buckets[(annotation["article_index"], annotation["paragraph_index"])].append(annotation)

    consolidated_rows = []
    final_majority_approved = defaultdict(list)

    for (article_index, paragraph_index), paragraph_annotations in sorted(paragraph_buckets.items()):
        for cluster_index, cluster in enumerate(cluster_annotations(paragraph_annotations)):
            representative = max(cluster, key=representative_rank)
            status = raw_status(representative)
            accept_sum = sum(item["accept"] for item in cluster)
            deny_sum = sum(item["deny"] for item in cluster)
            total_votes_sum = accept_sum + deny_sum
            row = {
                "article_index": article_index,
                "article_title": article_title_mapping.get(article_index, f"ARTICLE_{article_index}"),
                "paragraph_index": paragraph_index,
                "cluster_index": cluster_index,
                "subcategory": representative["subcategory"],
                "category": representative["category"],
                "representative_text": representative["text"],
                "representative_meta": representative["meta"],
                "representative_accept": representative["accept"],
                "representative_deny": representative["deny"],
                "representative_total_votes": representative["total_votes"],
                "representative_accept_rate": representative["accept_rate"],
                "cluster_member_count": len(cluster),
                "cluster_accept_sum": accept_sum,
                "cluster_deny_sum": deny_sum,
                "cluster_total_votes_sum": total_votes_sum,
                "cluster_accept_rate_sum": (
                    accept_sum / total_votes_sum if total_votes_sum else 0.0
                ),
                "cluster_status": status,
                "cluster_metas": sorted({item["meta"] for item in cluster}),
                "cluster_texts": [item["text"] for item in cluster],
            }
            consolidated_rows.append(row)

            if status == "majority_accept":
                final_majority_approved[article_index].append(
                    {
                        "category": representative["category"],
                        "subcategory": representative["subcategory"],
                        "text": representative["text"],
                        "paragraphIndex": paragraph_index,
                        "representativeMeta": representative["meta"],
                        "accept": representative["accept"],
                        "deny": representative["deny"],
                        "clusterMemberCount": len(cluster),
                    }
                )

    final_annotations = []
    for article_index in sorted(article_title_mapping):
        final_annotations.append(
            {
                "articleIndex": article_index,
                "title": article_title_mapping.get(article_index, f"ARTICLE_{article_index}"),
                "annotations": sorted(
                    final_majority_approved.get(article_index, []),
                    key=lambda ann: (
                        ann["paragraphIndex"],
                        ann["category"],
                        ann["subcategory"],
                        base.normalize_span(ann["text"]),
                    ),
                ),
            }
        )

    return consolidated_rows, final_annotations


def summarize(flattened_annotations, consolidated_rows):
    raw_subcategory = defaultdict(lambda: {"accept": 0, "deny": 0, "instances": 0})
    raw_category = defaultdict(lambda: {"accept": 0, "deny": 0, "instances": 0})
    raw_meta = defaultdict(lambda: {"accept": 0, "deny": 0, "instances": 0})
    raw_status_counts = Counter()

    for annotation in flattened_annotations:
        status = raw_status(annotation)
        raw_status_counts[status] += 1

        raw_subcategory[annotation["subcategory"]]["accept"] += annotation["accept"]
        raw_subcategory[annotation["subcategory"]]["deny"] += annotation["deny"]
        raw_subcategory[annotation["subcategory"]]["instances"] += 1

        raw_category[annotation["category"]]["accept"] += annotation["accept"]
        raw_category[annotation["category"]]["deny"] += annotation["deny"]
        raw_category[annotation["category"]]["instances"] += 1

        raw_meta[annotation["meta"]]["accept"] += annotation["accept"]
        raw_meta[annotation["meta"]]["deny"] += annotation["deny"]
        raw_meta[annotation["meta"]]["instances"] += 1

    consolidated_subcategory = defaultdict(
        lambda: {"majority_accept": 0, "majority_deny": 0, "tie": 0, "no_votes": 0}
    )
    consolidated_category = defaultdict(
        lambda: {"majority_accept": 0, "majority_deny": 0, "tie": 0, "no_votes": 0}
    )
    consolidated_article = defaultdict(
        lambda: {
            "cluster_count": 0,
            "majority_accept": 0,
            "majority_deny": 0,
            "tie": 0,
            "no_votes": 0,
            "approved_final_annotations": 0,
        }
    )
    consolidated_status_counts = Counter()

    for row in consolidated_rows:
        status = row["cluster_status"]
        consolidated_status_counts[status] += 1
        consolidated_subcategory[row["subcategory"]][status] += 1
        consolidated_category[row["category"]][status] += 1

        article_title = row["article_title"]
        consolidated_article[article_title]["cluster_count"] += 1
        consolidated_article[article_title][status] += 1
        if status == "majority_accept":
            consolidated_article[article_title]["approved_final_annotations"] += 1

    raw_vote_total = sum(item["accept"] + item["deny"] for item in flattened_annotations)
    raw_accept_total = sum(item["accept"] for item in flattened_annotations)
    raw_deny_total = sum(item["deny"] for item in flattened_annotations)

    raw_eligible_annotations = [item for item in flattened_annotations if item["total_votes"] >= 2]
    consolidated_eligible_rows = [row for row in consolidated_rows if row["representative_total_votes"] >= 2]

    def build_binary_ratings(items, *, accept_key, deny_key):
        ratings = []
        for item in items:
            accept = int(item[accept_key])
            deny = int(item[deny_key])
            total = accept + deny
            if total < 2:
                continue
            ratings.append((["accept"] * accept) + (["deny"] * deny))
        return ratings

    def unit_pair_agreement(accept, deny):
        total = accept + deny
        if total < 2:
            return None
        return ((accept * (accept - 1)) + (deny * (deny - 1))) / (total * (total - 1))

    def binary_reliability(items, *, accept_key, deny_key):
        ratings = build_binary_ratings(items, accept_key=accept_key, deny_key=deny_key)
        pair_agreements = [
            unit_pair_agreement(int(item[accept_key]), int(item[deny_key]))
            for item in items
            if unit_pair_agreement(int(item[accept_key]), int(item[deny_key])) is not None
        ]
        exact_consensus_count = 0
        for item in items:
            accept = int(item[accept_key])
            deny = int(item[deny_key])
            total = accept + deny
            if total >= 2 and (accept == 0 or deny == 0):
                exact_consensus_count += 1

        alpha = base.krippendorff_alpha_nominal(ratings)
        return {
            "eligible_unit_count": len(ratings),
            "krippendorff_alpha_nominal": alpha,
            "mean_pairwise_percent_agreement": (
                sum(pair_agreements) / len(pair_agreements) if pair_agreements else None
            ),
            "exact_consensus_count": exact_consensus_count,
            "exact_consensus_rate": (
                exact_consensus_count / len(ratings) if ratings else None
            ),
        }

    summary = {
        "raw_proposal_level": {
            "proposal_count": len(flattened_annotations),
            "vote_eligible_proposal_count": len(raw_eligible_annotations),
            "no_vote_proposal_count": sum(1 for item in flattened_annotations if item["total_votes"] == 0),
            "vote_total": raw_vote_total,
            "accept_total": raw_accept_total,
            "deny_total": raw_deny_total,
            "accept_rate": (raw_accept_total / raw_vote_total) if raw_vote_total else 0.0,
            "status_counts": dict(raw_status_counts),
            "status_rates": {
                key: (
                    value / len(raw_eligible_annotations)
                    if raw_eligible_annotations and key != "no_votes"
                    else (
                        value / len(flattened_annotations) if flattened_annotations else 0.0
                    )
                )
                for key, value in sorted(raw_status_counts.items())
            },
            "binary_reliability": binary_reliability(
                raw_eligible_annotations, accept_key="accept", deny_key="deny"
            ),
            "by_subcategory": {
                label: {
                    **stats,
                    "total_votes": stats["accept"] + stats["deny"],
                    "accept_rate": (
                        stats["accept"] / (stats["accept"] + stats["deny"])
                        if (stats["accept"] + stats["deny"])
                        else 0.0
                    ),
                }
                for label, stats in sorted(raw_subcategory.items())
            },
            "by_category": {
                label: {
                    **stats,
                    "total_votes": stats["accept"] + stats["deny"],
                    "accept_rate": (
                        stats["accept"] / (stats["accept"] + stats["deny"])
                        if (stats["accept"] + stats["deny"])
                        else 0.0
                    ),
                }
                for label, stats in sorted(raw_category.items())
            },
            "by_meta": {
                label: {
                    **stats,
                    "total_votes": stats["accept"] + stats["deny"],
                    "accept_rate": (
                        stats["accept"] / (stats["accept"] + stats["deny"])
                        if (stats["accept"] + stats["deny"])
                        else 0.0
                    ),
                }
                for label, stats in sorted(raw_meta.items())
            },
        },
        "consolidated_cluster_level": {
            "cluster_count": len(consolidated_rows),
            "vote_eligible_cluster_count": len(consolidated_eligible_rows),
            "no_vote_cluster_count": sum(
                1 for row in consolidated_rows if row["representative_total_votes"] == 0
            ),
            "status_counts": dict(consolidated_status_counts),
            "status_rates": {
                key: (
                    value / len(consolidated_eligible_rows)
                    if consolidated_eligible_rows and key != "no_votes"
                    else (value / len(consolidated_rows) if consolidated_rows else 0.0)
                )
                for key, value in sorted(consolidated_status_counts.items())
            },
            "binary_reliability": binary_reliability(
                consolidated_eligible_rows,
                accept_key="representative_accept",
                deny_key="representative_deny",
            ),
            "final_majority_approved_annotation_count": sum(
                1 for row in consolidated_rows if row["cluster_status"] == "majority_accept"
            ),
            "by_subcategory": dict(sorted(consolidated_subcategory.items())),
            "by_category": dict(sorted(consolidated_category.items())),
            "by_article": dict(sorted(consolidated_article.items())),
        },
    }

    return summary


def build_csv_rows(summary, consolidated_rows):
    raw_subcategory_rows = []
    for label, stats in summary["raw_proposal_level"]["by_subcategory"].items():
        raw_subcategory_rows.append(
            {
                "subcategory": label,
                "instances": stats["instances"],
                "accept": stats["accept"],
                "deny": stats["deny"],
                "total_votes": stats["total_votes"],
                "accept_rate": stats["accept_rate"],
            }
        )

    consolidated_subcategory_rows = []
    for label, stats in summary["consolidated_cluster_level"]["by_subcategory"].items():
        total = (
            stats["majority_accept"]
            + stats["majority_deny"]
            + stats["tie"]
            + stats["no_votes"]
        )
        eligible = total - stats["no_votes"]
        consolidated_subcategory_rows.append(
            {
                "subcategory": label,
                "cluster_count": total,
                "majority_accept": stats["majority_accept"],
                "majority_deny": stats["majority_deny"],
                "tie": stats["tie"],
                "no_votes": stats["no_votes"],
                "majority_accept_rate": (
                    stats["majority_accept"] / eligible if eligible else 0.0
                ),
            }
        )

    article_rows = []
    for title, stats in summary["consolidated_cluster_level"]["by_article"].items():
        article_rows.append({"article_title": title, **stats})

    consolidated_rows_csv = [
        {
            **row,
            "cluster_metas": " | ".join(row["cluster_metas"]),
            "cluster_texts": " || ".join(row["cluster_texts"]),
        }
        for row in consolidated_rows
    ]

    return (
        raw_subcategory_rows,
        consolidated_subcategory_rows,
        article_rows,
        consolidated_rows_csv,
    )


def main():
    args = parse_args()
    annotations = load_json(args.annotations)
    submissions = load_json(args.submissions)
    article_title_mapping = build_article_title_mapping(submissions)
    flattened_annotations = flatten_in_house_annotations(annotations)
    consolidated_rows, final_annotations = consolidate_annotations(
        flattened_annotations, article_title_mapping
    )
    summary = summarize(flattened_annotations, consolidated_rows)

    output_dir = Path(args.output_dir)
    write_json(output_dir / "in_house_live_validation_summary.json", summary)
    write_json(
        output_dir / "in_house_live_majority_approved_annotations.json",
        final_annotations,
    )

    (
        raw_subcategory_rows,
        consolidated_subcategory_rows,
        article_rows,
        consolidated_rows_csv,
    ) = build_csv_rows(summary, consolidated_rows)

    write_csv(
        output_dir / "in_house_live_validation_raw_subcategory_votes.csv",
        raw_subcategory_rows,
        ["subcategory", "instances", "accept", "deny", "total_votes", "accept_rate"],
    )
    write_csv(
        output_dir / "in_house_live_validation_consolidated_subcategories.csv",
        consolidated_subcategory_rows,
        [
            "subcategory",
            "cluster_count",
            "majority_accept",
            "majority_deny",
            "tie",
            "no_votes",
            "majority_accept_rate",
        ],
    )
    write_csv(
        output_dir / "in_house_live_validation_article_summary.csv",
        article_rows,
        [
            "article_title",
            "cluster_count",
            "majority_accept",
            "majority_deny",
            "tie",
            "no_votes",
            "approved_final_annotations",
        ],
    )
    write_csv(
        output_dir / "in_house_live_validation_consolidated_clusters.csv",
        consolidated_rows_csv,
        [
            "article_index",
            "article_title",
            "paragraph_index",
            "cluster_index",
            "subcategory",
            "category",
            "representative_text",
            "representative_meta",
            "representative_accept",
            "representative_deny",
            "representative_total_votes",
            "representative_accept_rate",
            "cluster_member_count",
            "cluster_accept_sum",
            "cluster_deny_sum",
            "cluster_total_votes_sum",
            "cluster_accept_rate_sum",
            "cluster_status",
            "cluster_metas",
            "cluster_texts",
        ],
    )

    print(f"Wrote in-house live validation outputs to {output_dir}")


if __name__ == "__main__":
    main()
