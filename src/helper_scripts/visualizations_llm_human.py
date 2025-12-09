import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt


# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
HUMAN_PATH = BASE_DIR / "mturk_results/newest11-20HIT.json"
LLM_PATH = BASE_DIR / "llm_annotation_results/final_annotations_3annotators (1).json"
OUTPUT_DIR = BASE_DIR / "data_visualizations"
PERSUASIVE_IMG = OUTPUT_DIR / "persuasive_propaganda_pies.png"
INFLAMMATORY_IMG = OUTPUT_DIR / "inflammatory_language_pies.png"


def load_json(path: Path):
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"{path} is empty.")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def normalize_label(label: str) -> str:
    """Lowercase, trim, and replace underscores so categories align."""
    return (label or "").replace("_", " ").strip().lower()


def iter_human_annotations(payload):
    """
    Yield annotation dicts from mixed MTurk payloads.
    Handles both dict- and list-shaped 'textAnnotations' values.
    """

    def walk(obj):
        if isinstance(obj, dict):
            if {"category", "subcategory", "text"} <= set(obj.keys()):
                yield obj
            else:
                for value in obj.values():
                    yield from walk(value)
        elif isinstance(obj, list):
            for item in obj:
                yield from walk(item)

    if isinstance(payload, dict):
        for entry in payload.values():
            ta = entry.get("textAnnotations")
            if ta is not None:
                yield from walk(ta)
    elif isinstance(payload, list):
        # Unlikely for the MTurk file, but keep this as a safety valve.
        for item in payload:
            yield from walk(item)


def iter_llm_annotations(payload):
    """Yield annotation dicts from the LLM results file."""
    if not isinstance(payload, list):
        return
    for article in payload:
        for ann in article.get("annotations", []):
            yield ann


def count_subcategories_for_category(annotations, target_category: str):
    target = normalize_label(target_category)
    counts = Counter()
    for ann in annotations:
        if normalize_label(ann.get("category", "")) == target:
            sub = normalize_label(ann.get("subcategory", "unspecified")) or "unspecified"
            counts[sub] += 1
    return counts


def format_labels(counter: Counter):
    """Return keys, labels, and sizes sorted descending by size."""
    items = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)
    keys = [label for label, _ in items]
    labels = [label.title() for label in keys]
    sizes = [count for _, count in items]
    return keys, labels, sizes


def build_color_map(human_counts: Counter, llm_counts: Counter):
    """
    Assign a consistent color per label across both charts.
    Uses a repeating qualitative palette if categories exceed the base set.
    """
    all_labels = sorted({*human_counts.keys(), *llm_counts.keys()})
    base_palette = plt.get_cmap("tab20").colors  # 20 distinct colors

    color_map = {}
    for i, label in enumerate(all_labels):
        color_map[label] = base_palette[i % len(base_palette)]
    return color_map


def plot_side_by_side_pies(
    human_counts: Counter,
    llm_counts: Counter,
    output_path: Path,
    title: str,
    empty_message: str,
):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    plt.style.use("seaborn-v0_8-colorblind")
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))

    color_map = build_color_map(human_counts, llm_counts)

    datasets = [
        ("Human annotations", human_counts, axes[0]),
        ("LLM annotations", llm_counts, axes[1]),
    ]

    for title, counts, ax in datasets:
        keys, labels, sizes = format_labels(counts)
        if not sizes:
            ax.text(0.5, 0.5, empty_message, ha="center", va="center")
            ax.axis("off")
            continue

        colors = [color_map[k] for k in keys]

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct=lambda pct: f"{pct:.1f}% ({int(round(pct * sum(sizes) / 100))})",
            startangle=90,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
            textprops={"fontsize": 9},
            colors=colors,
        )
        ax.set_title(title, fontsize=12, pad=12)
        ax.axis("equal")

    fig.suptitle(title, fontsize=14, y=1.02)
    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved pie charts to {output_path}")


def main():
    human_payload = load_json(HUMAN_PATH)
    llm_payload = load_json(LLM_PATH)

    # Load annotations once so we can build multiple charts
    human_annotations = list(iter_human_annotations(human_payload))
    llm_annotations = list(iter_llm_annotations(llm_payload))

    # Persuasive propaganda distribution
    human_persuasive = count_subcategories_for_category(human_annotations, "persuasive propaganda")
    llm_persuasive = count_subcategories_for_category(llm_annotations, "persuasive propaganda")
    plot_side_by_side_pies(
        human_persuasive,
        llm_persuasive,
        PERSUASIVE_IMG,
        "Persuasive Propaganda Subcategory Distribution",
        "No persuasive propaganda labels",
    )

    # Inflammatory language distribution
    human_inflammatory = count_subcategories_for_category(human_annotations, "inflammatory language")
    llm_inflammatory = count_subcategories_for_category(llm_annotations, "inflammatory language")
    plot_side_by_side_pies(
        human_inflammatory,
        llm_inflammatory,
        INFLAMMATORY_IMG,
        "Inflammatory Language Subcategory Distribution",
        "No inflammatory language labels",
    )


if __name__ == "__main__":
    main()
