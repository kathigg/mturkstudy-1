import json
import re
from pathlib import Path
from collections import defaultdict
import random

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

def paragraphs_match(p1, p2):
    if p1 is None or p2 is None:
        return True
    return p1 == p2

def titles_match(title1, title2):
    t1 = re.sub(r"[^\w\s]", "", title1 or "").strip().lower()
    t2 = re.sub(r"[^\w\s]", "", title2 or "").strip().lower()
    return t1 == t2

def non_stopword_overlap(span1, span2):
    tokens1 = set(tokenize_span(span1)) - STOP_WORDS
    tokens2 = set(tokenize_span(span2)) - STOP_WORDS
    return len(tokens1 & tokens2) >= 2

def spans_match(span1, span2, title1=None, title2=None, para1=None, para2=None):
    if title1 is not None and title2 is not None and not titles_match(title1, title2):
        return False
    if not paragraphs_match(para1, para2):
        return False
    norm1 = normalize_span(span1)
    norm2 = normalize_span(span2)
    return (norm1 in norm2 or norm2 in norm1) and non_stopword_overlap(span1, span2)

# ------------------------ß
# Paths for JSON files
# ------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
# LLM_PATH = BASE_DIR / "llm_annotation_results/1-20/1-20_llm_exact_one_final_annotations_3annotators.json"
# GOLD_PATH = BASE_DIR / "mturk_results/1-20/1-20_human_exact_one_gold_standard_output.json"
LLM_PATH = BASE_DIR / "llm_annotation_results/1-20/1-20_llm_min_one_final_annotations_3annotators.json"
GOLD_PATH = BASE_DIR / "mturk_results/1-20/1-20_human_min_one_gold_standard_output.json"
DEBUG_TITLE = None  # Set to a string to print matched pairs for one title.

# Toggle confidence-weighted metrics (True = use gold confidence weights; False = treat all gold weights as 1.0).
USE_CONFIDENCE_WEIGHTING = True

# If True, force exactly one annotation per paragraph on both sides (for apples-to-apples comparison).
# If False, allow multiple annotations per paragraph (matching remains paragraph-indexed).
ENFORCE_ONE_ANNOTATION_PER_PARAGRAPH = False

# Bootstrap confidence intervals (article-level resampling).
ENABLE_BOOTSTRAP_CIS = False
BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 0

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

def _group_by_paragraph_index(annotations):
    by_para = defaultdict(list)
    for ann in annotations:
        pidx = ann.get("paragraphIndex")
        if isinstance(pidx, int):
            by_para[pidx].append(ann)
    return by_para

def _pick_best_llm_annotation(items):
    # Prefer a polarizing annotation if present; otherwise keep an NPL placeholder.
    polarizing = [a for a in items if not is_no_polarizing(a)]
    candidates = polarizing if polarizing else items
    # Prefer longer spans as a proxy for specificity; keep stable ordering on ties.
    return max(enumerate(candidates), key=lambda item: (len(str(item[1].get("text", ""))), -item[0]))[1]

def _pick_best_gold_annotation(items):
    # Match turk aggregation tie-breaking: max supporters, then (conservatively) prefer NPL if tied,
    # then confidence, then longer span.
    max_support = max(int(a.get("num_supporters") or 0) for a in items)
    tied = [a for a in items if int(a.get("num_supporters") or 0) == max_support]
    npl = [a for a in tied if is_no_polarizing(a)]
    candidates = npl if npl else tied
    return max(
        enumerate(candidates),
        key=lambda item: (
            float(item[1].get("confidence") or 0.0),
            len(str(item[1].get("text", ""))),
            -item[0],
        ),
    )[1]

def maybe_enforce_one_annotation_per_paragraph(llm_annotations, gold_annotations):
    if not ENFORCE_ONE_ANNOTATION_PER_PARAGRAPH:
        return llm_annotations, gold_annotations

    llm_by_para = _group_by_paragraph_index(llm_annotations)
    gold_by_para = _group_by_paragraph_index(gold_annotations)

    llm_reduced = [_pick_best_llm_annotation(llm_by_para[pidx]) for pidx in sorted(llm_by_para.keys())]
    gold_reduced = [_pick_best_gold_annotation(gold_by_para[pidx]) for pidx in sorted(gold_by_para.keys())]
    return llm_reduced, gold_reduced

def match_annotation(llm_ann, gold_ann, llm_title=None, gold_title=None):
    """Return True if titles match and annotations overlap (or both say no polarizing language)."""
    if llm_title is not None and gold_title is not None and not titles_match(llm_title, gold_title):
        return False
    return spans_match(
        llm_ann.get("text", ""),
        gold_ann.get("text", ""),
        llm_title,
        gold_title,
        llm_ann.get("paragraphIndex"),
        gold_ann.get("paragraphIndex"),
    )


def match_category(llm_ann, gold_ann, llm_title=None, gold_title=None):
    """Return True if titles match and category/subcategory match (and overlap)."""
    if llm_title is not None and gold_title is not None and not titles_match(llm_title, gold_title):
        return False
    if spans_match(
        llm_ann.get("text", ""),
        gold_ann.get("text", ""),
        llm_title,
        gold_title,
        llm_ann.get("paragraphIndex"),
        gold_ann.get("paragraphIndex"),
    ):
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
                    "paragraphIndex": ann.get("paragraphIndex"),
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

# ------------------------
# Flatten helpers
# ------------------------
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
                        "paragraphIndex": ann.get("paragraphIndex"),
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
                        "paragraphIndex": ann.get("paragraphIndex"),
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

def init_class_counts():
    return defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "support": 0})

def update_class_counts(counts, pred_label, gold_label):
    if pred_label == gold_label:
        counts[gold_label]["tp"] += 1
        counts[gold_label]["support"] += 1
    else:
        counts[pred_label]["fp"] += 1
        counts[gold_label]["fn"] += 1
        counts[gold_label]["support"] += 1
        counts[pred_label]["support"] += 0

def merge_class_counts(dest, src):
    for label, c in src.items():
        dest[label]["tp"] += c["tp"]
        dest[label]["fp"] += c["fp"]
        dest[label]["fn"] += c["fn"]
        dest[label]["support"] += c["support"]

def finalize_class_metrics(counts):
    metrics = {}
    for label in sorted(counts.keys()):
        c = counts[label]
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        metrics[label] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": c["support"],
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
    return metrics

def compute_per_class_metrics(matched_pairs, llm_annotations, gold_annotations, label_key):
    counts = init_class_counts()
    for li, gi, _ in matched_pairs:
        pred_label = normalize_label(llm_annotations[li].get(label_key, "")) or "unknown"
        gold_label = normalize_label(gold_annotations[gi].get(label_key, "")) or "unknown"
        update_class_counts(counts, pred_label, gold_label)
    return finalize_class_metrics(counts), counts

def normalize_title(title):
    return re.sub(r"[^\w\s]", "", title).strip().lower()

def print_matched_pairs_for_title(llm_json, gold_json, title_query):
    if not title_query:
        return

    llm_map = flatten_llm(llm_json)
    gold_map = flatten_gold(gold_json)

    llm_norm_to_title = {normalize_title(k): k for k in llm_map.keys()}
    gold_norm_to_title = {normalize_title(k): k for k in gold_map.keys()}
    norm = normalize_title(title_query)

    if norm not in llm_norm_to_title or norm not in gold_norm_to_title:
        print(f"⚠️ Title not found in both datasets: '{title_query}'")
        return

    llm_title = llm_norm_to_title[norm]
    gold_title = gold_norm_to_title[norm]
    l_anns, g_anns = maybe_enforce_one_annotation_per_paragraph(
        llm_map[llm_title],
        gold_map[gold_title],
    )

    matched_pairs, _, _ = greedy_weighted_match(
        l_anns, g_anns, lambda l, g: match_annotation(l, g, llm_title, gold_title)
    )

    print(f"\n=== MATCHED PAIRS FOR: {llm_title} ===")
    if not matched_pairs:
        print("No matched pairs found.")
        return

    for li, gi, _ in matched_pairs:
        l = l_anns[li]
        g = g_anns[gi]
        print("- LLM:", l)
        print("  GOLD:", g)


# ------------------------
# Aggregate Comparison
# ------------------------
def _aggregate_overall_from_article_summaries(
    per_article_summaries: dict[str, dict],
):
    total_correct_article = 0
    total_llm = 0
    total_gold = 0

    total_correct_cat = 0
    total_shared = 0

    sum_TP_w = 0.0
    sum_FP = 0
    sum_Gold_w = 0.0

    overall_cat_counts = init_class_counts()
    overall_subcat_counts = init_class_counts()

    for summary in per_article_summaries.values():
        a = summary["article_match"]
        c = summary["category_match"]
        w = summary["weighted_article_match"]

        total_correct_article += int(a.get("correct_matches", 0))
        total_llm += int(a.get("total_llm", 0))
        total_gold += int(a.get("total_gold", 0))

        total_correct_cat += int(c.get("correct_matches", 0))
        total_shared += int(c.get("total_matches", 0))

        sum_TP_w += float(w.get("tp_weight", 0.0))
        sum_FP += int(w.get("fp", 0))
        sum_Gold_w += float(w.get("total_gold_weight", 0.0))

        # Per-class summaries are already "finalized" dicts. Reconstruct counts by tp/fp/fn/support.
        # This keeps bootstrap aggregation consistent with the per-article computation basis (matched pairs only).
        for label, entry in (summary.get("category_match_per_class") or {}).items():
            overall_cat_counts[label]["tp"] += int(entry.get("tp", 0))
            overall_cat_counts[label]["fp"] += int(entry.get("fp", 0))
            overall_cat_counts[label]["fn"] += int(entry.get("fn", 0))
            overall_cat_counts[label]["support"] += int(entry.get("support", 0))
        for label, entry in (summary.get("subcategory_match_per_class") or {}).items():
            overall_subcat_counts[label]["tp"] += int(entry.get("tp", 0))
            overall_subcat_counts[label]["fp"] += int(entry.get("fp", 0))
            overall_subcat_counts[label]["fn"] += int(entry.get("fn", 0))
            overall_subcat_counts[label]["support"] += int(entry.get("support", 0))

    precision_article = total_correct_article / total_llm if total_llm else 0.0
    recall_article = total_correct_article / total_gold if total_gold else 0.0
    f1_article = (2 * precision_article * recall_article / (precision_article + recall_article)) if (precision_article + recall_article) else 0.0

    precision_cat = total_correct_cat / total_shared if total_shared else 0.0
    recall_cat = total_correct_cat / total_shared if total_shared else 0.0
    f1_cat = (2 * precision_cat * recall_cat / (precision_cat + recall_cat)) if (precision_cat + recall_cat) else 0.0

    overall_wp = (sum_TP_w / (sum_TP_w + sum_FP)) if (sum_TP_w + sum_FP) > 0 else 0.0
    overall_wr = (sum_TP_w / sum_Gold_w) if sum_Gold_w > 0 else 0.0
    overall_wf1 = (2 * overall_wp * overall_wr / (overall_wp + overall_wr)) if (overall_wp + overall_wr) > 0 else 0.0

    return {
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
        "category_match_per_class": finalize_class_metrics(overall_cat_counts),
        "subcategory_match_per_class": finalize_class_metrics(overall_subcat_counts),
        "weighted_article_match": {
            "precision": round(overall_wp, 3),
            "recall": round(overall_wr, 3),
            "f1": round(overall_wf1, 3),
            "tp_weight": round(sum_TP_w, 3),
            "total_gold_weight": round(sum_Gold_w, 3),
            "fp": sum_FP,
        },
    }


def compare_shared_titles(llm_map_raw, gold_map_raw, shared_norm_titles, llm_norm_to_title, gold_norm_to_title):
    """
    Compare only the provided set of shared_norm_titles.
    Returns:
      overall (dict) and per_article (dict).
    """
    per_article = {}

    for norm in sorted(shared_norm_titles):
        llm_title = llm_norm_to_title[norm]
        gold_title = gold_norm_to_title[norm]

        l_anns, g_anns = maybe_enforce_one_annotation_per_paragraph(
            llm_map_raw[llm_title],
            gold_map_raw[gold_title],
        )

        result = compare_article(l_anns, g_anns, llm_title, gold_title)
        cat_result = compare_category(l_anns, g_anns, llm_title, gold_title)
        w_result = compare_article_weighted(l_anns, g_anns, llm_title, gold_title)
        matched_pairs, _, _ = greedy_weighted_match(
            l_anns, g_anns, lambda l, g: match_annotation(l, g, llm_title, gold_title)
        )
        cat_per_class, _ = compute_per_class_metrics(
            matched_pairs, l_anns, g_anns, "category"
        )
        subcat_per_class, _ = compute_per_class_metrics(
            matched_pairs, l_anns, g_anns, "subcategory"
        )

        per_article[llm_title] = {
            "article_match": result,
            "category_match": cat_result,
            "weighted_article_match": w_result,
            "category_match_per_class": cat_per_class,
            "subcategory_match_per_class": subcat_per_class,
        }

    overall = _aggregate_overall_from_article_summaries(per_article)
    return overall, per_article


def bootstrap_article_level_cis(llm_json, gold_json, *, n_bootstrap: int, seed: int):
    """
    Article-level bootstrap:
      - Sample articles with replacement from the shared-title set
      - Recompute overall metrics for each sample
      - Report percentile CIs (2.5%, 97.5%)
    """
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

    llm_norm_to_title = {normalize_title(k): k for k in llm_map_raw.keys()}
    gold_norm_to_title = {normalize_title(k): k for k in gold_map_raw.keys()}

    shared_norm_titles = sorted(set(llm_norm_to_title.keys()) & set(gold_norm_to_title.keys()))
    if not shared_norm_titles:
        raise ValueError("No shared titles found; cannot bootstrap.")

    rng = random.Random(seed)

    def _get_scalar(overall, key1, key2):
        return float(overall[key1][key2])

    samples = {
        "article_precision": [],
        "article_recall": [],
        "article_f1": [],
        "weighted_precision": [],
        "weighted_recall": [],
        "weighted_f1": [],
        "category_precision": [],
        "category_recall": [],
        "category_f1": [],
    }

    for _ in range(n_bootstrap):
        drawn = [rng.choice(shared_norm_titles) for _ in range(len(shared_norm_titles))]
        overall, _ = compare_shared_titles(llm_map_raw, gold_map_raw, drawn, llm_norm_to_title, gold_norm_to_title)

        samples["article_precision"].append(_get_scalar(overall, "article_match", "precision"))
        samples["article_recall"].append(_get_scalar(overall, "article_match", "recall"))
        samples["article_f1"].append(_get_scalar(overall, "article_match", "f1"))

        samples["weighted_precision"].append(_get_scalar(overall, "weighted_article_match", "precision"))
        samples["weighted_recall"].append(_get_scalar(overall, "weighted_article_match", "recall"))
        samples["weighted_f1"].append(_get_scalar(overall, "weighted_article_match", "f1"))

        samples["category_precision"].append(_get_scalar(overall, "category_match", "precision"))
        samples["category_recall"].append(_get_scalar(overall, "category_match", "recall"))
        samples["category_f1"].append(_get_scalar(overall, "category_match", "f1"))

    def _pct(values, p):
        if not values:
            return 0.0
        values_sorted = sorted(values)
        k = (len(values_sorted) - 1) * p
        f = int(k)
        c = min(f + 1, len(values_sorted) - 1)
        if f == c:
            return float(values_sorted[f])
        d0 = values_sorted[f] * (c - k)
        d1 = values_sorted[c] * (k - f)
        return float(d0 + d1)

    cis = {}
    for key, values in samples.items():
        cis[key] = {
            "low": round(_pct(values, 0.025), 3),
            "high": round(_pct(values, 0.975), 3),
        }

    return {
        "n_articles": len(shared_norm_titles),
        "n_bootstrap": n_bootstrap,
        "seed": seed,
        "cis": cis,
    }


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
        overall_cat_counts = init_class_counts()
        overall_subcat_counts = init_class_counts()

        for g_title, g_anns in gold_map_raw.items():
            for l_title, l_anns in llm_map_raw.items():
                l_anns, g_anns = maybe_enforce_one_annotation_per_paragraph(l_anns, g_anns)
                result = compare_article(l_anns, g_anns, l_title, g_title)
                cat_result = compare_category(l_anns, g_anns, l_title, g_title)
                w_result = compare_article_weighted(l_anns, g_anns, l_title, g_title)
                matched_pairs, _, _ = greedy_weighted_match(
                    l_anns, g_anns, lambda l, g: match_annotation(l, g, l_title, g_title)
                )
                cat_per_class, cat_counts = compute_per_class_metrics(
                    matched_pairs, l_anns, g_anns, "category"
                )
                subcat_per_class, subcat_counts = compute_per_class_metrics(
                    matched_pairs, l_anns, g_anns, "subcategory"
                )
                merge_class_counts(overall_cat_counts, cat_counts)
                merge_class_counts(overall_subcat_counts, subcat_counts)

                all_results[f"{g_title} ↔ {l_title}"] = {
                    "article_match": result,
                    "category_match": cat_result,
                    "weighted_article_match": w_result,
                    "category_match_per_class": cat_per_class,
                    "subcategory_match_per_class": subcat_per_class,
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
                "category_match_per_class": finalize_class_metrics(overall_cat_counts),
                "subcategory_match_per_class": finalize_class_metrics(overall_subcat_counts),
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
                "category_match_per_class": {},
                "subcategory_match_per_class": {},
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
    overall, per_article = compare_shared_titles(
        llm_map, gold_map, shared_norm_titles, llm_norm_to_title, gold_norm_to_title
    )
    return {"overall": overall, "per_article": per_article}

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
    print_matched_pairs_for_title(llm_json, gold_json, DEBUG_TITLE)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print("=== Overall Results ===")
    print(f"Confidence weighting enabled: {USE_CONFIDENCE_WEIGHTING}")
    print(f"Enforce one annotation per paragraph: {ENFORCE_ONE_ANNOTATION_PER_PARAGRAPH}")
    print("Article Match:", results["overall"]["article_match"])
    print("Category Match:", results["overall"]["category_match"])
    print("Weighted Article Match:", results["overall"]["weighted_article_match"])
    print(f"\nDetailed results saved to {output_file}")

    if ENABLE_BOOTSTRAP_CIS:
        boot = bootstrap_article_level_cis(llm_json, gold_json, n_bootstrap=BOOTSTRAP_N, seed=BOOTSTRAP_SEED)
        print("\n=== Bootstrap 95% CIs (Article-Level) ===")
        print(f"n_articles={boot['n_articles']} n_bootstrap={boot['n_bootstrap']} seed={boot['seed']}")
        cis = boot["cis"]
        print("Article precision CI:", cis["article_precision"])
        print("Article recall CI:", cis["article_recall"])
        print("Article F1 CI:", cis["article_f1"])
        print("Weighted precision CI:", cis["weighted_precision"])
        print("Weighted recall CI:", cis["weighted_recall"])
        print("Weighted F1 CI:", cis["weighted_f1"])
        print("Category precision CI:", cis["category_precision"])
        print("Category recall CI:", cis["category_recall"])
        print("Category F1 CI:", cis["category_f1"])
