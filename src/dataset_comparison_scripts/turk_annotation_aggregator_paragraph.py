import json
import re
from collections import defaultdict, Counter

# ------------------------
# Manual input/output path
# ------------------------
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "../mturk_results/1-8HIT_2026_01.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "../mturk_results/1-8_hit_gold_standard_output.json")

# ------------------------
# Constants
# ------------------------
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

# Minimum number of annotators required to keep an annotation (1, 2, or 3).
MIN_SUPPORTERS_TO_SAVE = 2

# ------------------------
# Text Utility Functions
# ------------------------
def normalize(text):
    # keep all characters, only lowercase and strip whitespace
    return text.lower().strip()

def tokenize(text):
    # split only on whitespace, don't remove punctuation
    return text.lower().split()

def normalize_title_string(title):
    return re.sub(r"[^\w\s]", "", title or "").strip().lower()

def non_stopword_overlap(span1, span2):
    tokens1 = set(tokenize(span1)) - STOP_WORDS
    tokens2 = set(tokenize(span2)) - STOP_WORDS
    return len(tokens1 & tokens2) >= 2

def spans_match(span1, span2, title1=None, title2=None, para1=None, para2=None):
    # Require title equality if both provided
    if title1 is not None and title2 is not None:
        if normalize_title_string(title1) != normalize_title_string(title2):
            return False
    # Require paragraph equality if both provided
    if para1 is not None and para2 is not None and para1 != para2:
        return False
    norm1 = normalize(span1)
    norm2 = normalize(span2)
    return (norm1 in norm2 or norm2 in norm1) and non_stopword_overlap(span1, span2)

def extract_intersection_with_padding(span1, span2, pad=2):
    tokens1 = normalize(span1).split()
    tokens2 = normalize(span2).split()
    overlap = [token for token in tokens1 if token in tokens2]
    if not overlap:
        return None

    def find_window(tokens, overlap_tokens):
        indices = [i for i, tok in enumerate(tokens) if tok in overlap_tokens]
        if not indices:
            return None
        start = max(0, indices[0] - pad)
        end = min(len(tokens), indices[-1] + pad + 1)
        return ' '.join(tokens[start:end])

    padded1 = find_window(tokens1, overlap)
    padded2 = find_window(tokens2, overlap)

    if padded1 and padded2:
        return padded1 if len(padded1) <= len(padded2) else padded2
    return padded1 or padded2 or ' '.join(overlap)

def compute_confidence(num_supporters, label_consistent):
    if num_supporters == 3:
        return 1.0
    elif num_supporters == 2 and label_consistent:
        return 0.67
    elif num_supporters == 2:
        return 0.5
    else:
        return 0.33

def is_no_polarizing_annotation(ann: dict) -> bool:
    cat = (ann.get("category") or "").strip().lower()
    sub = (ann.get("subcategory") or "").strip().lower()
    return cat == "no_polarizing_language" or sub == "no polarizing language" or sub == "no polarizing language".lower()

def compute_no_polarizing_confidence(num_supporters: int, total_workers: int) -> float:
    if total_workers <= 0:
        return 0.0
    # Use a direct agreement fraction for "No Polarizing Language".
    # This yields e.g. 0.67 for 2/3 and 0.33 for 1/3.
    return round(num_supporters / total_workers, 2)

# ------------------------
# Gold Standard Builder
# ------------------------
from collections import Counter, defaultdict

# ------------------------
# Gold Standard Builder
# ------------------------
from collections import Counter, defaultdict

def build_gold_standard_with_intersection(
    annotations_by_article,
    database_record=None,  # full record OR top-level dict
    workers_by_article_para=None,
    no_polarizing_workers_by_article_para=None,
    pad=2
):
    """
    Builds a gold-standard annotations set grouped by overlapping spans.
    Adds article titles using the provided database structure.

    Parameters
    ----------
    annotations_by_article : dict
        {article_id: [ {text, category, subcategory, ...}, ... ]}
    database_record : dict, optional
        The full record that may include "articleTitles".
    pad : int
        Padding used when extracting intersections.
    """
    gold_standard = defaultdict(list)

    # --- STEP 1: Extract {id: title} mapping robustly ---
    article_titles = {}

    if database_record:
        # Case 1: direct record with "articleTitles"
        if "articleTitles" in database_record:
            for entry in database_record["articleTitles"]:
                # Ensure string keys since annotation IDs may be strings
                article_titles[str(entry["id"])] = entry["title"]

        # Case 2: upper-level dict with multiple records
        else:
            for key, value in database_record.items():
                if isinstance(value, dict) and "articleTitles" in value:
                    for entry in value["articleTitles"]:
                        article_titles[str(entry["id"])] = entry["title"]

    # Debugging: show extracted mapping
    print("\n--- Title Mapping Extracted ---")
    for k, v in article_titles.items():
        print(f"{k} → {v}")
    print("-------------------------------\n")

    # --- STEP 2: Build gold standard ---
    for article_id, spans in annotations_by_article.items():
        grouped = []
        used = set()
        title_for_article = article_titles.get(str(article_id)) or article_titles.get(int(article_id)) or ""

        for i, span1 in enumerate(spans):
            if i in used:
                continue
            group = [span1]
            used.add(i)
            for j in range(i + 1, len(spans)):
                if j in used:
                    continue
                span2 = spans[j]
                # Enforce title match as precondition before span comparison
                if spans_match(
                    span1.get("text", ""),
                    span2.get("text", ""),
                    title_for_article,
                    title_for_article,
                    span1.get("paragraphIndex"),
                    span2.get("paragraphIndex"),
                ):
                    group.append(span2)
                    used.add(j)
            grouped.append(group)

        for group in grouped:
            if not group:
                continue

            categories = [g["category"] for g in group]
            subcategories = [g["subcategory"] for g in group]

            base = group[0]
            text = base["text"]
            for other in group[1:]:
                text = extract_intersection_with_padding(text, other["text"], pad=pad) or text

            most_common_cat = Counter(categories).most_common(1)[0][0]
            most_common_subcat = Counter(subcategories).most_common(1)[0][0]
            paragraph_index = group[0].get("paragraphIndex")

            label_consistent = len(set(categories)) == 1 and len(set(subcategories)) == 1
            worker_ids = {g.get("worker") for g in group if g.get("worker") is not None}
            missing_workers = [g for g in group if g.get("worker") is None]
            if missing_workers:
                print(
                    f"Warning: {len(missing_workers)} annotations missing worker IDs "
                    f"(article_id={article_id}, paragraphIndex={paragraph_index})."
                )

            # For "No Polarizing Language", confidence and supporter counts should be paragraph-based:
            # num_supporters = number of workers who selected "no polarizing language" for that paragraph.
            if str(most_common_cat).strip().lower() == "no_polarizing_language":
                total_workers = 0
                if workers_by_article_para is not None:
                    total_workers = len(workers_by_article_para.get((str(article_id), paragraph_index), set()))
                npl_workers = set()
                if no_polarizing_workers_by_article_para is not None:
                    npl_workers = no_polarizing_workers_by_article_para.get((str(article_id), paragraph_index), set())
                num_supporters = len(npl_workers) if npl_workers else (len(worker_ids) if worker_ids else len(group))
                confidence = compute_no_polarizing_confidence(num_supporters, total_workers) if total_workers else compute_confidence(num_supporters, label_consistent)
                label_consistent = bool(total_workers) and num_supporters == total_workers
                # Canonicalize the span text/subcategory for NPL.
                most_common_subcat = "no polarizing language"
                text = "no polarizing language selected"
            else:
                num_supporters = len(worker_ids) if worker_ids else len(group)
                confidence = compute_confidence(num_supporters, label_consistent)

            # Lookup title — check both int and string
            title = (
                article_titles.get(str(article_id))
                or article_titles.get(int(article_id))
                or "UNKNOWN_TITLE"
            )

            gold_standard[article_id].append({
                "text": text,
                "category": most_common_cat,
                "subcategory": most_common_subcat,
                "confidence": confidence,
                "num_supporters": num_supporters,
                "label_consistent": label_consistent,
                "title": title,
                "paragraphIndex": paragraph_index,
            })

    # --- STEP 3: Keep only the strongest annotation per paragraph ---
    for article_id, anns in list(gold_standard.items()):
        by_para = defaultdict(list)
        for ann in anns:
            pidx = ann.get("paragraphIndex")
            if isinstance(pidx, int):
                by_para[pidx].append(ann)

        pruned: list[dict] = []
        for pidx, items in by_para.items():
            if not items:
                continue
            items = [
                a for a in items
                if int(a.get("num_supporters") or 0) >= MIN_SUPPORTERS_TO_SAVE
            ]
            if not items:
                # Fall back to a no-polarizing placeholder when nothing meets the threshold.
                pruned.append({
                    "text": "no polarizing language selected",
                    "category": "No_Polarizing_Language",
                    "subcategory": "no polarizing language",
                    "confidence": 0.33,
                    "num_supporters": 0,
                    "label_consistent": False,
                    "title": anns[0].get("title", "UNKNOWN_TITLE"),
                    "paragraphIndex": pidx,
                })
                continue
            max_support = max(int(a.get("num_supporters") or 0) for a in items)
            tied = [a for a in items if int(a.get("num_supporters") or 0) == max_support]
            npl = [a for a in tied if is_no_polarizing_annotation(a)]
            candidates = npl if npl else tied
            # Break remaining ties with confidence, then longer span.
            keep = max(
                candidates,
                key=lambda a: (
                    float(a.get("confidence") or 0.0),
                    len(str(a.get("text", ""))),
                ),
            )
            pruned.append(keep)

        gold_standard[article_id] = pruned

    return gold_standard

# ------------------------
# Main Function
# ------------------------
def process_annotation_file(input_path, output_path):
    import os, json
    from collections import defaultdict

    with open(input_path, "r") as f:
        raw_data = json.load(f)

    annotated_spans = defaultdict(list)
    workers_by_article_para = defaultdict(set)  # (article_id, paragraphIndex) -> set(worker_id)
    no_polarizing_workers_by_article_para = defaultdict(set)  # (article_id, paragraphIndex) -> set(worker_id)
    polarizing_workers_by_article_para = defaultdict(set)  # (article_id, paragraphIndex) -> set(worker_id)

    for worker_id, entry in raw_data.items():
        ta = entry.get("textAnnotations")

        if not ta:
            continue

        # Case 1: textAnnotations is a dict (normal case)
        if isinstance(ta, dict):
            for article_id, annotations in ta.items():
                if not isinstance(annotations, list):
                    continue
                for ann in annotations:
                    if not isinstance(ann, dict):
                        continue
                    pidx = ann.get("paragraphIndex")
                    if isinstance(pidx, int):
                        workers_by_article_para[(str(article_id), pidx)].add(worker_id)
                        if is_no_polarizing_annotation(ann):
                            no_polarizing_workers_by_article_para[(str(article_id), pidx)].add(worker_id)
                        else:
                            polarizing_workers_by_article_para[(str(article_id), pidx)].add(worker_id)
                    text = ann.get("text", "")
                    annotated_spans[str(article_id)].append({
                        "text": text,
                        "category": ann.get("category"),
                        "subcategory": ann.get("subcategory"),
                        "worker": worker_id,
                        "paragraphIndex": ann.get("paragraphIndex"),
                    })

        # Case 2: textAnnotations is a list (some later entries)
        elif isinstance(ta, list):
            for i, annotations in enumerate(ta):
                if not annotations or not isinstance(annotations, list):
                    continue
                # Some entries don't have IDs; we can use index as fallback
                article_id = str(i)
                for ann in annotations:
                    if not isinstance(ann, dict):
                        continue
                    pidx = ann.get("paragraphIndex")
                    if isinstance(pidx, int):
                        workers_by_article_para[(str(article_id), pidx)].add(worker_id)
                        if is_no_polarizing_annotation(ann):
                            no_polarizing_workers_by_article_para[(str(article_id), pidx)].add(worker_id)
                        else:
                            polarizing_workers_by_article_para[(str(article_id), pidx)].add(worker_id)
                    text = ann.get("text", "")
                    annotated_spans[article_id].append({
                        "text": text,
                        "category": ann.get("category"),
                        "subcategory": ann.get("subcategory"),
                        "worker": worker_id,
                        "paragraphIndex": ann.get("paragraphIndex"),
                    })

    # Warn if any worker both selected no-polarizing and also provided polarizing annotations in the same paragraph.
    for key, npl_workers in no_polarizing_workers_by_article_para.items():
        overlap = npl_workers & polarizing_workers_by_article_para.get(key, set())
        if overlap:
            article_id, pidx = key
            print(
                f"Warning: {len(overlap)} worker(s) have both no-polarizing and polarizing annotations "
                f"for the same paragraph (article_id={article_id}, paragraphIndex={pidx})."
            )

    gold_standard = build_gold_standard_with_intersection(
        annotated_spans,
        database_record=raw_data,  # pass the full MTurk file so title mapping works
        workers_by_article_para=workers_by_article_para,
        no_polarizing_workers_by_article_para=no_polarizing_workers_by_article_para,
        )

    # --- Convert gold_standard dict to list-of-articles format for LLM comparison ---
    output_list = []
    for article_id, anns in gold_standard.items():
        if not anns:
            continue
        title = anns[0].get("title", f"ARTICLE_{article_id}")
        title = title.strip().title()
        output_list.append({
            "title": title,
            "annotations": [
            {
                "text": ann["text"],
                "category": ann["category"].replace("_", " "),
                "subcategory": ann["subcategory"].replace("_", " "),
                "confidence": ann.get("confidence"),
                "num_supporters": ann.get("num_supporters"),
                "label_consistent": ann.get("label_consistent"),
                "paragraphIndex": ann.get("paragraphIndex"),
            }
  for ann in anns
]
        })

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output_list, f, indent=2)

    print(f"Gold standard saved to: {OUTPUT_FILE}")

# ------------------------
# Execute
# ------------------------
if __name__ == "__main__":
    process_annotation_file(INPUT_FILE, OUTPUT_FILE)
