import json
import re
from pathlib import Path
from collections import defaultdict

# Paths for the JSON files
BASE_DIR = Path(__file__).resolve().parent.parent  # goes up to /src
LLM_PATH = BASE_DIR / "llm_annotation_results/GPT-5-annotations.json"
GOLD_PATH = BASE_DIR / "mturk_results/gold_standard_output.json"


# ------------------------
# Utility functions
# ------------------------
def load_json(path):
    with open(path, "r") as f:
        content = f.read().strip()
        if not content:
            raise ValueError(f"File {path} is empty.")
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}")


def normalize_text(text):
    """Lowercase, remove punctuation, strip."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def normalize_label(label):
    """Normalize category/subcategory labels (spaces/underscores -> spaces, lowercase)."""
    if not label:
        return ""
    return re.sub(r"[_]", " ", label).strip().lower()


def tokenize(text):
    return normalize_text(text).split()


def overlap(span1, span2, min_overlap=2):
    """Check if there are at least min_overlap shared non-stopwords."""
    tokens1 = set(tokenize(span1))
    tokens2 = set(tokenize(span2))
    return len(tokens1 & tokens2) >= min_overlap


def match_annotation(llm_ann, gold_ann):
    """Return True if annotations overlap and category/subcategory match."""
    if not overlap(llm_ann["text"], gold_ann["text"]):
        return False
    return (
        normalize_label(llm_ann["category"]) == normalize_label(gold_ann["category"])
        and normalize_label(llm_ann["subcategory"]) == normalize_label(gold_ann["subcategory"])
    )


# ------------------------
# Flatten helpers
# ------------------------
def flatten_llm(llm_json):
    """Flatten LLM annotations into {title: [annotations...]} dict.
       Supports both 'items' (GPT-5) and 'annotations' (older format)."""
    article_map = defaultdict(list)
    for article in llm_json:
        title = article.get("title", "UNKNOWN_TITLE")
        anns = article.get("items") or article.get("annotations") or []
        for ann in anns:
            article_map[title].append(
                {
                    "text": ann.get("text", ""),
                    "category": ann.get("category", ""),
                    "subcategory": ann.get("subcategory", ""),
                }
            )
    return article_map


def flatten_gold(gold_json):
    """Flatten gold annotations into {title: [annotations...]} dict."""
    article_map = defaultdict(list)
    for _, anns in gold_json.items():
        for ann in anns:
            title = ann.get("title", "UNKNOWN_TITLE")
            article_map[title].append(
                {
                    "text": ann.get("text", ""),
                    "category": ann.get("category", ""),
                    "subcategory": ann.get("subcategory", ""),
                }
            )
    return article_map


# ------------------------
# Comparison
# ------------------------
def compare_article(llm_annotations, gold_annotations):
    """Compare annotations for a single article and return metrics."""
    correct = 0
    used_gold = set()
    for llm in llm_annotations:
        for i, gold in enumerate(gold_annotations):
            if i in used_gold:
                continue
            if match_annotation(llm, gold):
                correct += 1
                used_gold.add(i)
                break

    precision = correct / len(llm_annotations) if llm_annotations else 0
    recall = correct / len(gold_annotations) if gold_annotations else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "correct_matches": correct,
        "total_llm": len(llm_annotations),
        "total_gold": len(gold_annotations),
    }


def compare_all(llm_json, gold_json):
    llm_map = flatten_llm(llm_json)
    gold_map = flatten_gold(gold_json)

    # Find overlap of article titles
    common_titles = set(llm_map.keys()) & set(gold_map.keys())

    all_results = {}
    for title in common_titles:
        llm_annotations = llm_map[title]
        gold_annotations = gold_map[title]
        scores = compare_article(llm_annotations, gold_annotations)
        all_results[title] = scores

    # compute overall only on common titles
    total_correct = sum(r["correct_matches"] for r in all_results.values())
    total_llm = sum(r["total_llm"] for r in all_results.values())
    total_gold = sum(r["total_gold"] for r in all_results.values())

    precision = total_correct / total_llm if total_llm else 0
    recall = total_correct / total_gold if total_gold else 0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0
    )

    overall = {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "correct_matches": total_correct,
        "total_llm": total_llm,
        "total_gold": total_gold,
    }

    return {"overall": overall, "per_article": all_results}


# ------------------------
# Main
# ------------------------
if __name__ == "__main__":
    llm_json = load_json(LLM_PATH)
    gold_json = load_json(GOLD_PATH)
    output_file = "annotation_comparison_results.json"

    results = compare_all(llm_json, gold_json)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to {output_file}")