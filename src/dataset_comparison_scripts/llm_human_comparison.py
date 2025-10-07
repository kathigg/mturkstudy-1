import json
import re
from pathlib import Path
from collections import defaultdict

# ------------------------
# Paths for JSON files
# ------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
LLM_PATH = BASE_DIR / "llm_annotation_results/GPT-5-annotations.json"
GOLD_PATH = BASE_DIR / "mturk_results/v2_2nd_hit_gold_standard_output.json"
# GOLD_PATH = BASE_DIR / "mturk_results/gold_standard_output.json"

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
    """Check if there are at least min_overlap shared words."""
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


def match_category(llm_ann, gold_ann):
    """Return True if category/subcategory match (and overlap)."""
    if overlap(llm_ann["text"], gold_ann["text"]):
        return (
            normalize_label(llm_ann["category"]) == normalize_label(gold_ann["category"])
            and normalize_label(llm_ann["subcategory"]) == normalize_label(gold_ann["subcategory"])
        )
    return False


# ------------------------
# Flatten helpers
# ------------------------
def flatten_llm(llm_json):
    """Flatten LLM annotations into {title: [annotations...]} dict."""
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
    """
    Flatten gold annotations into {title: [annotations...]} dict.
    Handles both numeric-keyed dicts and list-of-article formats.
    """
    article_map = defaultdict(list)

    # Case 1: dict keyed by article ID
    if isinstance(gold_json, dict):
        for art_id, anns in gold_json.items():
            title = f"ARTICLE_{art_id}"
            for ann in anns:
                article_map[title].append(
                    {
                        "text": ann.get("text", ""),
                        "category": ann.get("category", ""),
                        "subcategory": ann.get("subcategory", ""),
                    }
                )

    # Case 2: list of full article objects
    elif isinstance(gold_json, list):
        for article in gold_json:
            title = article.get("title", "UNKNOWN_TITLE")
            anns = article.get("annotations", [])
            for ann in anns:
                article_map[title].append(
                    {
                        "text": ann.get("text", ""),
                        "category": ann.get("category", ""),
                        "subcategory": ann.get("subcategory", ""),
                    }
                )
    else:
        raise TypeError("Unexpected gold dataset format.")

    return article_map


# ------------------------
# Comparison helpers
# ------------------------
def num_of_overlap(llm_ann, gold_ann):
    """Compare annotations for a single article and return number of matching spans."""
    correct = 0
    used_gold = set()
    for llm in llm_ann:
        for i, gold in enumerate(gold_ann):
            if i in used_gold:
                continue
            if match_annotation(llm, gold):
                correct += 1
                used_gold.add(i)
                break
    return correct


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


def compare_category(llm_annotations, gold_annotations):
    """Compare annotations for a single article (category/subcategory only)."""
    total_shared = num_of_overlap(llm_annotations, gold_annotations)
    correct = 0
    used_gold = set()

    for llm in llm_annotations:
        for i, gold in enumerate(gold_annotations):
            if i in used_gold:
                continue
            if match_category(llm, gold):
                correct += 1
                used_gold.add(i)
                break

    precision = correct / total_shared if total_shared else 0
    recall = correct / total_shared if total_shared else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "correct_matches": correct,
        "total_matches": total_shared,
    }


# ------------------------
# Aggregate Comparison
# ------------------------
def compare_all(llm_json, gold_json):
    llm_map = flatten_llm(llm_json)
    gold_map = flatten_gold(gold_json)

    # --- FIX: match numeric gold IDs to LLM titles ---
    # If no shared titles, try fallback by comparing all pairs
    if not (set(llm_map.keys()) & set(gold_map.keys())):
        print("⚠️ No direct title matches found. Using fallback comparison mode.")
        all_results = {}
        total_correct_article = total_llm = total_gold = 0
        total_correct_cat = total_shared = 0

        for g_title, g_anns in gold_map.items():
            for l_title, l_anns in llm_map.items():
                # Compare every gold article to every LLM article (slower but robust)
                result = compare_article(l_anns, g_anns)
                cat_result = compare_category(l_anns, g_anns)

                all_results[f"{g_title} ↔ {l_title}"] = {
                    "article_match": result,
                    "category_match": cat_result,
                }

                total_correct_article += result["correct_matches"]
                total_llm += result["total_llm"]
                total_gold += result["total_gold"]
                total_correct_cat += cat_result["correct_matches"]
                total_shared += cat_result["total_matches"]

        # Aggregate results
        precision_article = total_correct_article / total_llm if total_llm else 0
        recall_article = total_correct_article / total_gold if total_gold else 0
        f1_article = (2 * precision_article * recall_article / (precision_article + recall_article)
                      if (precision_article + recall_article) else 0)

        precision_cat = total_correct_cat / total_shared if total_shared else 0
        recall_cat = total_correct_cat / total_shared if total_shared else 0
        f1_cat = (2 * precision_cat * recall_cat / (precision_cat + recall_cat)
                  if (precision_cat + recall_cat) else 0)

        return {
            "overall": {
                "article_match": {
                    "precision": round(precision_article, 3),
                    "recall": round(recall_article, 3),
                    "f1": round(f1_article, 3),
                    "correct_matches": total_correct_article,
                    "total_llm": total_llm,
                    "total_gold": total_gold,
                },
                "category_match": {
                    "precision": round(precision_cat, 3),
                    "recall": round(recall_cat, 3),
                    "f1": round(f1_cat, 3),
                    "correct_matches": total_correct_cat,
                    "total_matches": total_shared,
                },
            },
            "per_article": all_results,
        }

# ------------------------
# Main
# ------------------------
if __name__ == "__main__":
    llm_json = load_json(LLM_PATH)
    gold_json = load_json(GOLD_PATH)
    output_file = "annotation_comparison_results.json"

    # --- Debug: Check structure of both datasets before comparison ---
    from pprint import pprint

    # Flatten manually to inspect
    llm_map = flatten_llm(llm_json)
    gold_map = flatten_gold(gold_json)

    print("\n=== DEBUG INFO ===")
    print(f"LLM has {len(llm_map)} articles.")
    print(f"Gold has {len(gold_map)} articles.\n")

    print("Sample LLM article keys:")
    pprint(list(llm_map.keys())[:5])

    print("\nSample Gold article keys:")
    pprint(list(gold_map.keys())[:5])

    # Optional: check one random annotation example from each
    for title, anns in list(llm_map.items())[:1]:
        print(f"\nLLM example from '{title}':")
        pprint(anns[:2])
    for title, anns in list(gold_map.items())[:1]:
        print(f"\nGold example from '{title}':")
        pprint(anns[:2])

    print("=== END DEBUG ===\n")

    results = compare_all(llm_json, gold_json)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print("=== Overall Results ===")
    print("Article Match:", results["overall"]["article_match"])
    print("Category Match:", results["overall"]["category_match"])
    print(f"\nDetailed results saved to {output_file}")