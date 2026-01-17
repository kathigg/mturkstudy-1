import json
import re
from pathlib import Path
from collections import defaultdict

# --- Shared span-matching logic (mirrors turk_annotation_aggregator.py) ---
STOP_WORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your',
    'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she',
    'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their',
    'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that',
    'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an',
    'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of',
    'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through',
    'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down',
    'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then',
    'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any',
    'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
    'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'can',
    'will', 'just', 'don', 'should', 'now'
}

def normalize_span(text):
    return (text or "").lower().strip()

def tokenize_span(text):
    return normalize_span(text).split()

def titles_match(title1, title2):
    t1 = re.sub(r"[^\w\s]", "", title1 or "").strip().lower()
    t2 = re.sub(r"[^\w\s]", "", title2 or "").strip().lower()
    return t1 == t2

def non_stopword_overlap(span1, span2):
    tokens1 = set(tokenize_span(span1)) - STOP_WORDS
    tokens2 = set(tokenize_span(span2)) - STOP_WORDS
    return len(tokens1 & tokens2) >= 2

def spans_match(span1, span2, title1=None, title2=None):
    if title1 is not None and title2 is not None and not titles_match(title1, title2):
        return False
    norm1 = normalize_span(span1)
    norm2 = normalize_span(span2)
    return (norm1 in norm2 or norm2 in norm1) and non_stopword_overlap(span1, span2)

# ------------------------
# Paths for JSON files
# ------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
# LLM_PATH = BASE_DIR / "dataset_comparison_scripts/LLM_Commitee_test_2.json"
# LLM_PATH = BASE_DIR / "mturk_results/gpt-5-twelve_article_annotations.json"
# LLM_PATH = BASE_DIR / "mturk_results/11-20_hit_gold_standard_output.json"
LLM_PATH = BASE_DIR / "llm_annotation_results/paragraph_final_annotations_3annotators.json"
GOLD_PATH = BASE_DIR / "mturk_results/1-8_hit_gold_standard_output.json"
# GOLD_PATH = BASE_DIR / "mturk_results/gold_standard_output.json"
OUTPUT_PATH = BASE_DIR / "annotation_comparison_results.json"

# Toggle confidence-weighted metrics (True = use gold confidence weights; False = treat all gold weights as 1.0).
USE_CONFIDENCE_WEIGHTING = True

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
    """Lowercase and strip, keep punctuation for overlap."""
    return text.lower().strip()


def normalize_label(label):
    """Normalize category/subcategory labels (spaces/underscores -> spaces, lowercase)."""
    if not label:
        return ""
    return re.sub(r"[_]", " ", label).strip().lower()


def tokenize(text):
    return normalize_text(text).split()


def overlap(span1, span2, min_overlap=4):
    tokens1 = set(tokenize(span1))
    tokens2 = set(tokenize(span2))
    # token overlap OR substring overlap
    if len(tokens1 & tokens2) >= min_overlap:
        return True
    norm1, norm2 = span1.lower(), span2.lower()
    return norm1 in norm2 or norm2 in norm1

def is_no_polarizing(ann):
    """Return True if annotation indicates no polarizing or manipulative language."""
    cat = normalize_label(ann.get("category", ""))
    text = ann.get("text", "").lower()
    return "no polarizing language" in cat or "no polarizing language" in text

def match_annotation(llm_ann, gold_ann, llm_title=None, gold_title=None):
    """Return True if titles match and annotations overlap (or both say no polarizing language)."""
    if llm_title is not None and gold_title is not None and not titles_match(llm_title, gold_title):
        return False
    # Special case: both label "no polarizing language"
    if is_no_polarizing(llm_ann) and is_no_polarizing(gold_ann):
        return True
    return spans_match(llm_ann.get("text", ""), gold_ann.get("text", ""), llm_title, gold_title)


def match_category(llm_ann, gold_ann, llm_title=None, gold_title=None):
    """Return True if titles match and category/subcategory match (and overlap)."""
    if llm_title is not None and gold_title is not None and not titles_match(llm_title, gold_title):
        return False
    if is_no_polarizing(llm_ann) and is_no_polarizing(gold_ann):
        return True
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

# ------------------------
# Weighted matching helpers
# ------------------------
def get_gold_weight(ann):
    if not USE_CONFIDENCE_WEIGHTING:
        return 1.0
    # Default mirrors gold-builder levels: 1.0 (3/3), 0.67 (2 w/consistency), 0.5 (2 w/o), 0.33 (1)
    # If not present, assume a conservative 0.33.
    return float(ann.get("confidence", 0.33))

def greedy_weighted_match(llm_annotations, gold_annotations, match_fn):
    """
    Greedy 1-to-1 matching:
      - returns: matched_pairs (list of (llm_idx, gold_idx, gold_weight)),
                 unmatched_llm (set of llm idx),
                 unmatched_gold (set of gold idx)
    """
    matched_pairs = []
    used_gold = set()
    unmatched_llm = set(range(len(llm_annotations)))

    for li, llm in enumerate(llm_annotations):
        for gi, gold in enumerate(gold_annotations):
            if gi in used_gold:
                continue
            if match_fn(llm, gold):
                matched_pairs.append((li, gi, get_gold_weight(gold)))
                used_gold.add(gi)
                unmatched_llm.discard(li)
                break

    unmatched_gold = set(i for i in range(len(gold_annotations)) if i not in {g for _, g, _ in matched_pairs})
    return matched_pairs, unmatched_llm, unmatched_gold

def compare_article_weighted(llm_annotations, gold_annotations, llm_title=None, gold_title=None):
    """
    Weighted article-level metric (span overlap logic):
      - rewards agreement with high-confidence gold
      - penalizes misses in proportion to gold confidence
      - keeps FP cost unweighted
    """
    matched_pairs, unmatched_llm, unmatched_gold = greedy_weighted_match(
        llm_annotations, gold_annotations, lambda l, g: match_annotation(l, g, llm_title, gold_title)
    )
    TP_w = sum(w for _, _, w in matched_pairs)
    FP = len(unmatched_llm)
    Gold_w = sum(get_gold_weight(g) for g in gold_annotations)

    # Guard rails
    weighted_precision = TP_w / (TP_w + FP) if (TP_w + FP) > 0 else 0.0
    weighted_recall = TP_w / Gold_w if Gold_w > 0 else 0.0
    weighted_f1 = (2 * weighted_precision * weighted_recall / (weighted_precision + weighted_recall)
                   if (weighted_precision + weighted_recall) > 0 else 0.0)

    return {
        "precision": round(weighted_precision, 3),
        "recall": round(weighted_recall, 3),
        "f1": round(weighted_f1, 3),
        "tp_weight": round(TP_w, 3),
        "total_gold_weight": round(Gold_w, 3),
        "fp": FP,
        "matched": len(matched_pairs),
        "total_llm": len(llm_annotations),
        "total_gold": len(gold_annotations),
    }

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
                if not isinstance(ann, dict):
                    continue
                article_map[title].append(
                    {
                        "text": ann.get("text", ""),
                        "category": ann.get("category", ""),
                        "subcategory": ann.get("subcategory", ""),
                        "confidence": ann.get("confidence"),
                    }
                )

    # Case 2: list of full article objects
    elif isinstance(gold_json, list):
        for article in gold_json:
            title = article.get("title", "UNKNOWN_TITLE")
            anns = article.get("annotations", [])
            for ann in anns:
                if not isinstance(ann, dict):
                    continue
                article_map[title].append(
                    {
                        "text": ann.get("text", ""),
                        "category": ann.get("category", ""),
                        "subcategory": ann.get("subcategory", ""),
                        "confidence": ann.get("confidence"),
                    }
                )
    else:
        raise TypeError("Unexpected gold dataset format.")

    return article_map


# ------------------------
# Comparison helpers
# ------------------------
def num_of_overlap(llm_ann, gold_ann, llm_title=None, gold_title=None):
    """Compare annotations for a single article and return number of matching spans."""
    correct = 0
    used_gold = set()
    for llm in llm_ann:
        for i, gold in enumerate(gold_ann):
            if i in used_gold:
                continue
            if match_annotation(llm, gold, llm_title, gold_title):
                correct += 1
                used_gold.add(i)
                break
    return correct


def compare_article(llm_annotations, gold_annotations, llm_title=None, gold_title=None):
    """Compare annotations for a single article and return metrics."""
    correct = 0
    used_gold = set()
    for llm in llm_annotations:
        for i, gold in enumerate(gold_annotations):
            if i in used_gold:
                continue
            if match_annotation(llm, gold, llm_title, gold_title):
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


def compare_category(llm_annotations, gold_annotations, llm_title=None, gold_title=None):
    """Compare annotations for a single article (category/subcategory only)."""
    total_shared = num_of_overlap(llm_annotations, gold_annotations, llm_title, gold_title)
    correct = 0
    used_gold = set()

    for llm in llm_annotations:
        for i, gold in enumerate(gold_annotations):
            if i in used_gold:
                continue
            if match_category(llm, gold, llm_title, gold_title):
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

def normalize_title(title):
    return re.sub(r"[^\w\s]", "", title).strip().lower()


# ------------------------
# Aggregate Comparison
# ------------------------
def compare_all(llm_json, gold_json):
    # Flatten
    llm_map_raw = flatten_llm(llm_json)
    gold_map_raw = flatten_gold(gold_json)

    # Normalize gold titles by removing "ARTICLE_" prefix if present
    cleaned_gold_map = {}
    for title, anns in gold_map_raw.items():
        normalized_title = title
        if title.startswith("ARTICLE_"):
            normalized_title = title.replace("ARTICLE_", "", 1).strip()
        cleaned_gold_map[normalized_title] = anns
    gold_map_raw = cleaned_gold_map

    # Build mapping from normalized title -> original title
    llm_norm_to_title = {normalize_title(k): k for k in llm_map_raw.keys()}
    gold_norm_to_title = {normalize_title(k): k for k in gold_map_raw.keys()}

    llm_norm_titles = set(llm_norm_to_title.keys())
    gold_norm_titles = set(gold_norm_to_title.keys())

    shared_norm_titles = llm_norm_titles & gold_norm_titles

    # If nothing overlaps at all, use your existing fallback mode
    if not shared_norm_titles:
        print("⚠️ No direct title matches found. Using fallback comparison mode.")
        all_results = {}
        total_correct_article = total_llm = total_gold = 0
        total_correct_cat = total_shared = 0
        sum_TP_w = 0.0
        sum_FP = 0
        sum_Gold_w = 0.0

        for g_title, g_anns in gold_map_raw.items():
            for l_title, l_anns in llm_map_raw.items():
                result = compare_article(l_anns, g_anns, l_title, g_title)
                cat_result = compare_category(l_anns, g_anns, l_title, g_title)
                w_result = compare_article_weighted(l_anns, g_anns, l_title, g_title)

                all_results[f"{g_title} ↔ {l_title}"] = {
                    "article_match": result,
                    "category_match": cat_result,
                    "weighted_article_match": w_result,
                }

                total_correct_article += result["correct_matches"]
                total_llm += result["total_llm"]
                total_gold += result["total_gold"]
                total_correct_cat += cat_result["correct_matches"]
                total_shared += cat_result["total_matches"]
                sum_TP_w += w_result["tp_weight"]
                sum_FP += w_result["fp"]
                sum_Gold_w += w_result["total_gold_weight"]

        precision_article = total_correct_article / total_llm if total_llm else 0
        recall_article = total_correct_article / total_gold if total_gold else 0
        f1_article = (2 * precision_article * recall_article /
                      (precision_article + recall_article)) if (precision_article + recall_article) else 0

        precision_cat = total_correct_cat / total_shared if total_shared else 0
        recall_cat = total_correct_cat / total_shared if total_shared else 0
        f1_cat = (2 * precision_cat * recall_cat /
                  (precision_cat + recall_cat)) if (precision_cat + recall_cat) else 0

        overall_wp = (sum_TP_w / (sum_TP_w + sum_FP)) if (sum_TP_w + sum_FP) > 0 else 0.0
        overall_wr = (sum_TP_w / sum_Gold_w) if sum_Gold_w > 0 else 0.0
        overall_wf1 = (2 * overall_wp * overall_wr / (overall_wp + overall_wr)
                       if (overall_wp + overall_wr) > 0 else 0.0)

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
                "weighted_article_match": {
                    "precision": round(overall_wp, 3),
                    "recall": round(overall_wr, 3),
                    "f1": round(overall_wf1, 3),
                    "tp_weight": round(sum_TP_w, 3),
                    "total_gold_weight": round(sum_Gold_w, 3),
                    "fp": sum_FP,
                },
            },
            "per_article": all_results,
        }

    # -------- New: warn & restrict strictly to shared titles --------
    missing_in_llm = gold_norm_titles - llm_norm_titles
    missing_in_gold = llm_norm_titles - gold_norm_titles

    for norm in sorted(missing_in_llm):
        print(f"⚠️ Skipping '{gold_norm_to_title[norm]}' — exists in GOLD but not in LLM.")

    for norm in sorted(missing_in_gold):
        print(f"⚠️ Skipping '{llm_norm_to_title[norm]}' — exists in LLM but not in GOLD.")

    # If after filtering there are no articles left, bail out with zeros
    if not shared_norm_titles:
        print("⚠️ After removing unmatched titles, no articles remain for comparison.")
        return {
            "overall": {
                "article_match": {"precision": 0, "recall": 0, "f1": 0},
                "category_match": {"precision": 0, "recall": 0, "f1": 0},
                "weighted_article_match": {"precision": 0, "recall": 0, "f1": 0},
            },
            "per_article": {},
        }

    # Now restrict maps to shared titles only
    # (THIS is what ensures missing articles can't affect totals)
    llm_map = {
        llm_norm_to_title[norm]: llm_map_raw[llm_norm_to_title[norm]]
        for norm in shared_norm_titles
    }
    gold_map = {
        gold_norm_to_title[norm]: gold_map_raw[gold_norm_to_title[norm]]
        for norm in shared_norm_titles
    }

    # --- Normal case: direct matches exist on shared articles ---
    all_results = {}
    total_correct_article = total_llm = total_gold = 0
    total_correct_cat = total_shared = 0
    sum_TP_w = 0.0
    sum_FP = 0
    sum_Gold_w = 0.0

    for norm in sorted(shared_norm_titles):
        llm_title = llm_norm_to_title[norm]
        gold_title = gold_norm_to_title[norm]

        l_anns = llm_map[llm_title]
        g_anns = gold_map[gold_title]

        result = compare_article(l_anns, g_anns, llm_title, gold_title)
        cat_result = compare_category(l_anns, g_anns, llm_title, gold_title)
        w_result = compare_article_weighted(l_anns, g_anns, llm_title, gold_title)

        all_results[llm_title] = {
            "article_match": result,
            "category_match": cat_result,
            "weighted_article_match": w_result,
        }

        total_correct_article += result["correct_matches"]
        total_llm += result["total_llm"]
        total_gold += result["total_gold"]
        total_correct_cat += cat_result["correct_matches"]
        total_shared += cat_result["total_matches"]
        sum_TP_w += w_result["tp_weight"]
        sum_FP += w_result["fp"]
        sum_Gold_w += w_result["total_gold_weight"]

    precision_article = total_correct_article / total_llm if total_llm else 0
    recall_article = total_correct_article / total_gold if total_gold else 0
    f1_article = (2 * precision_article * recall_article /
                  (precision_article + recall_article)) if (precision_article + recall_article) else 0

    precision_cat = total_correct_cat / total_shared if total_shared else 0
    recall_cat = total_correct_cat / total_shared if total_shared else 0
    f1_cat = (2 * precision_cat * recall_cat /
              (precision_cat + recall_cat)) if (precision_cat + recall_cat) else 0

    overall_wp = (sum_TP_w / (sum_TP_w + sum_FP)) if (sum_TP_w + sum_FP) > 0 else 0.0
    overall_wr = (sum_TP_w / sum_Gold_w) if sum_Gold_w > 0 else 0.0
    overall_wf1 = (2 * overall_wp * overall_wr / (overall_wp + overall_wr)
                   if (overall_wp + overall_wr) > 0 else 0.0)

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
            "weighted_article_match": {
                "precision": round(overall_wp, 3),
                "recall": round(overall_wr, 3),
                "f1": round(overall_wf1, 3),
                "tp_weight": round(sum_TP_w, 3),
                "total_gold_weight": round(sum_Gold_w, 3),
                "fp": sum_FP,
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
    output_file = OUTPUT_PATH

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
    print(f"Confidence weighting enabled: {USE_CONFIDENCE_WEIGHTING}")
    print("Article Match:", results["overall"]["article_match"])
    print("Category Match:", results["overall"]["category_match"])
    print("Weighted Article Match:", results["overall"]["weighted_article_match"])
    print(f"\nDetailed results saved to {output_file}")
