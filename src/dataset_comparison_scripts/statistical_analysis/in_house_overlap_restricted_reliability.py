from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_INPUT = "src/mturk_results/1-20/1-20-in-house.json"
DEFAULT_OUTPUT_JSON = (
    "src/dataset_comparison_scripts/statistical_analysis/1-20/"
    "1-20_in_house_overlap_restricted_reliability.json"
)
DEFAULT_OUTPUT_MD = (
    "src/dataset_comparison_scripts/statistical_analysis/1-20/"
    "1-20_in_house_overlap_restricted_reliability.md"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Compute full-dataset and overlap-restricted reliability views for "
            "the in-house annotation dataset."
        )
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def load_base_module():
    helper_path = Path(__file__).resolve().parent / "in_house_density_and_agreement.py"
    spec = importlib.util.spec_from_file_location("iaa_base", helper_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def units_to_list(units):
    return [worker_labels for _, worker_labels in sorted(units.items())]


def label_counts_from_unit_list(unit_list):
    return dict(Counter(label for worker_labels in unit_list for label in worker_labels.values()))


def exact_consensus_rate(unit_list):
    if not unit_list:
        return None
    return sum(1 for worker_labels in unit_list if len(set(worker_labels.values())) == 1) / len(unit_list)


def fleiss_kappa(unit_list):
    if not unit_list:
        return None

    rater_counts = {len(worker_labels) for worker_labels in unit_list}
    if len(rater_counts) != 1:
        return None
    n_raters = next(iter(rater_counts))
    if n_raters < 2:
        return None

    labels = sorted({label for worker_labels in unit_list for label in worker_labels.values()})
    if len(labels) < 2:
        return None

    p_i_values = []
    label_totals = Counter()
    total_assignments = len(unit_list) * n_raters

    for worker_labels in unit_list:
        counts = Counter(worker_labels.values())
        label_totals.update(counts)
        p_i = sum(count * (count - 1) for count in counts.values()) / (n_raters * (n_raters - 1))
        p_i_values.append(p_i)

    p_bar = sum(p_i_values) / len(p_i_values)
    p_e = sum((label_totals[label] / total_assignments) ** 2 for label in labels)
    if p_e == 1.0:
        return 1.0
    return (p_bar - p_e) / (1 - p_e)


def round_or_none(value):
    return round(value, 3) if value is not None else None


def metric_bundle(base, units):
    unit_list = units_to_list(units)
    ratings = [list(worker_labels.values()) for worker_labels in unit_list if len(worker_labels) >= 2]
    return {
        "units": len(unit_list),
        "raters_per_unit_distribution": dict(Counter(len(worker_labels) for worker_labels in unit_list)),
        "label_counts": label_counts_from_unit_list(unit_list),
        "pairwise_percent_agreement": round_or_none(base.pairwise_percent_agreement(ratings)),
        "exact_consensus_rate": round_or_none(exact_consensus_rate(unit_list)),
        "pairwise_cohen_kappa": base.pairwise_cohen_kappa(units),
        "fleiss_kappa": round_or_none(fleiss_kappa(unit_list)),
        "krippendorff_alpha_nominal": round_or_none(base.krippendorff_alpha_nominal(ratings)),
    }


def build_paragraph_units(annotations_by_worker_paragraph):
    units = defaultdict(dict)
    for (worker_id, article_id, paragraph_index), annotations in annotations_by_worker_paragraph.items():
        units[(article_id, paragraph_index)][worker_id] = annotations
    return units


def build_article_titles(raw_data):
    titles = {}
    for entry in raw_data.values():
        article_titles = entry.get("articleTitles") or []
        if isinstance(article_titles, list):
            for item in article_titles:
                if isinstance(item, dict) and item.get("id") is not None:
                    titles[str(item["id"])] = item.get("title", "")
        elif isinstance(article_titles, dict):
            for article_id, title in article_titles.items():
                titles[str(article_id)] = title
    return titles


def derive_label(base, annotations, label_mode):
    if label_mode == "binary":
        return base.derive_paragraph_binary_label(annotations)
    if label_mode == "category":
        return base.derive_paragraph_category_label(annotations)
    return base.derive_paragraph_subcategory_label(annotations)


def is_polarizing_annotation(base, ann):
    return not base.is_no_polarizing_annotation(ann)


def build_all_raters_polarizing_units(base, paragraph_units, *, label_mode):
    selected_units = {}
    selected_keys = []

    for unit_key, worker_map in sorted(paragraph_units.items()):
        if len(worker_map) != 3:
            continue
        if not all(any(is_polarizing_annotation(base, ann) for ann in annotations) for annotations in worker_map.values()):
            continue
        labels = {}
        for worker_id, annotations in worker_map.items():
            polarizing = [ann for ann in annotations if is_polarizing_annotation(base, ann)]
            label = derive_label(base, polarizing, label_mode)
            if label is not None:
                labels[worker_id] = label
        if len(labels) == 3:
            selected_units[unit_key] = labels
            selected_keys.append(unit_key)

    return selected_units, selected_keys


def overlap_graph_components(base, worker_map):
    nodes = []
    for worker_id, annotations in worker_map.items():
        for index, ann in enumerate(annotations):
            if is_polarizing_annotation(base, ann):
                nodes.append((worker_id, index, ann))

    adjacency = defaultdict(set)
    for i in range(len(nodes)):
        worker_i, _, ann_i = nodes[i]
        for j in range(i + 1, len(nodes)):
            worker_j, _, ann_j = nodes[j]
            if worker_i == worker_j:
                continue
            if base.spans_match(ann_i, ann_j, include_npl=False):
                adjacency[i].add(j)
                adjacency[j].add(i)

    seen = set()
    components = []
    for start in range(len(nodes)):
        if start in seen:
            continue
        stack = [start]
        component_indices = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component_indices.append(current)
            stack.extend(adjacency[current] - seen)
        components.append([nodes[index] for index in component_indices])

    return components


def component_label(base, annotations, label_mode):
    if label_mode == "category":
        labels = [ann["category"] for ann in annotations if ann.get("category")]
        if not labels:
            return None
        counts = Counter(labels)
        best_count = max(counts.values())
        for label in labels:
            if counts[label] == best_count:
                return label
    labels = sorted({ann["subcategory"] for ann in annotations if ann.get("subcategory")})
    if not labels:
        return None
    return labels[0] if len(labels) == 1 else base.MULTI_SUBCATEGORY_LABEL


def build_shared_span_units(base, paragraph_units, *, label_mode):
    units = {}
    supporting_paragraphs = set()

    for unit_key, worker_map in sorted(paragraph_units.items()):
        if len(worker_map) != 3:
            continue
        if not all(any(is_polarizing_annotation(base, ann) for ann in annotations) for annotations in worker_map.values()):
            continue

        components = overlap_graph_components(base, worker_map)
        component_counter = 0
        for component in components:
            per_worker = defaultdict(list)
            for worker_id, _, ann in component:
                per_worker[worker_id].append(ann)
            if len(per_worker) != 3:
                continue

            labels = {}
            for worker_id, annotations in per_worker.items():
                label = component_label(base, annotations, label_mode)
                if label is not None:
                    labels[worker_id] = label
            if len(labels) != 3:
                continue

            component_unit_key = (unit_key[0], unit_key[1], component_counter)
            units[component_unit_key] = labels
            supporting_paragraphs.add(unit_key)
            component_counter += 1

    return units, sorted(supporting_paragraphs)


def format_metric_line(metrics):
    def show(value):
        return "n/a" if value is None else value

    return (
        f"agreement `{show(metrics['pairwise_percent_agreement'])}`, "
        f"exact consensus `{show(metrics['exact_consensus_rate'])}`, "
        f"Cohen `{show(metrics['pairwise_cohen_kappa']['weighted_mean_kappa'])}`, "
        f"Fleiss `{show(metrics['fleiss_kappa'])}`, "
        f"alpha `{show(metrics['krippendorff_alpha_nominal'])}`"
    )


def write_markdown(path, payload):
    full = payload["full_dataset"]
    overlap = payload["overlap_restricted"]
    lines = []
    lines.append("# Overlap-Restricted Reliability")
    lines.append("")
    lines.append("## Clarification")
    lines.append("")
    lines.append(
        "- The raw annotation file contains explicit `No_Polarizing_Language` annotations. "
        "The IRR code is not inventing NPL when a row is absent; the paragraph-level "
        "comparison is reading those explicit NPL annotations from the saved data."
    )
    lines.append("")
    lines.append("## Unit Counts")
    lines.append("")
    counts = payload["dataset_counts"]
    lines.append(f"- Paragraph units in full dataset: `{counts['full_paragraph_units']}`")
    lines.append(f"- Paragraph units with exactly 3 raters: `{counts['three_rater_paragraph_units']}`")
    lines.append(f"- Paragraph units where all 3 raters marked polarizing spans: `{counts['all_three_polarizing_paragraph_units']}`")
    lines.append(f"- Shared 3-way overlapping span instances: `{counts['shared_three_way_span_instances']}`")
    lines.append("")
    lines.append("## Full Dataset")
    lines.append("")
    lines.append(f"- Binary: {format_metric_line(full['binary'])}")
    lines.append(f"- Category: {format_metric_line(full['category'])}")
    lines.append(f"- Subcategory: {format_metric_line(full['subcategory'])}")
    lines.append("")
    lines.append("## Overlap-Restricted Paragraphs")
    lines.append("")
    lines.append(
        "- Restriction: only paragraph units with exactly 3 raters where each rater marked at least one polarizing span."
    )
    lines.append(f"- Category: {format_metric_line(overlap['all_three_polarizing_paragraphs']['category'])}")
    lines.append(f"- Subcategory: {format_metric_line(overlap['all_three_polarizing_paragraphs']['subcategory'])}")
    lines.append("")
    lines.append("## Explicit Shared-Span Instances")
    lines.append("")
    lines.append(
        "- Restriction: only connected overlap components where all 3 raters marked the same polarizing instance."
    )
    lines.append(f"- Category: {format_metric_line(overlap['shared_three_way_span_instances']['category'])}")
    lines.append(f"- Subcategory: {format_metric_line(overlap['shared_three_way_span_instances']['subcategory'])}")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "- If overlap-restricted alpha/kappa are higher than full-dataset alpha/kappa, that supports the idea that coverage disagreement is depressing the headline paragraph-level IRR."
    )
    lines.append(
        "- The shared-span view is the cleanest estimate of label agreement after span-selection disagreement has already been removed."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    base = load_base_module()
    input_path = Path(args.input)

    raw_data, _worker_annotations_by_article, annotations_by_worker_paragraph = base.load_raw_annotations(input_path)
    paragraph_units = build_paragraph_units(annotations_by_worker_paragraph)
    article_titles = build_article_titles(raw_data)

    full_binary = metric_bundle(base, base.build_unit_labels(annotations_by_worker_paragraph, label_mode="binary"))
    full_category = metric_bundle(base, base.build_unit_labels(annotations_by_worker_paragraph, label_mode="category"))
    full_subcategory = metric_bundle(base, base.build_unit_labels(annotations_by_worker_paragraph, label_mode="subcategory"))

    overlap_paragraph_category, overlap_keys = build_all_raters_polarizing_units(
        base, paragraph_units, label_mode="category"
    )
    overlap_paragraph_subcategory, _ = build_all_raters_polarizing_units(
        base, paragraph_units, label_mode="subcategory"
    )

    shared_span_category, shared_span_paragraphs = build_shared_span_units(
        base, paragraph_units, label_mode="category"
    )
    shared_span_subcategory, _ = build_shared_span_units(
        base, paragraph_units, label_mode="subcategory"
    )

    payload = {
        "input_path": str(input_path),
        "dataset_counts": {
            "full_paragraph_units": len(paragraph_units),
            "three_rater_paragraph_units": sum(1 for worker_map in paragraph_units.values() if len(worker_map) == 3),
            "four_rater_paragraph_units": sum(1 for worker_map in paragraph_units.values() if len(worker_map) == 4),
            "all_three_polarizing_paragraph_units": len(overlap_keys),
            "shared_three_way_span_instances": len(shared_span_category),
            "shared_three_way_supporting_paragraphs": len(shared_span_paragraphs),
        },
        "clarification": {
            "explicit_npl_is_present_in_raw_data": True,
            "note": (
                "Paragraph-level disagreement between polarizing and NPL is coming from the "
                "saved annotations in the raw file, not from the IRR script manufacturing NPL "
                "labels for missing rows."
            ),
        },
        "full_dataset": {
            "binary": full_binary,
            "category": full_category,
            "subcategory": full_subcategory,
        },
        "overlap_restricted": {
            "all_three_polarizing_paragraphs": {
                "unit_keys": [
                    {
                        "article_id": article_id,
                        "paragraph_index": paragraph_index,
                        "title": article_titles.get(article_id, ""),
                    }
                    for article_id, paragraph_index in overlap_keys
                ],
                "category": metric_bundle(base, overlap_paragraph_category),
                "subcategory": metric_bundle(base, overlap_paragraph_subcategory),
            },
            "shared_three_way_span_instances": {
                "supporting_paragraph_keys": [
                    {
                        "article_id": article_id,
                        "paragraph_index": paragraph_index,
                        "title": article_titles.get(article_id, ""),
                    }
                    for article_id, paragraph_index in shared_span_paragraphs
                ],
                "category": metric_bundle(base, shared_span_category),
                "subcategory": metric_bundle(base, shared_span_subcategory),
            },
        },
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_markdown(output_md, payload)

    print(f"Saved JSON to {output_json}")
    print(f"Saved markdown to {output_md}")


if __name__ == "__main__":
    raise SystemExit(main())
