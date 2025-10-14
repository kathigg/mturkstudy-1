import json
import re
import os
from collections import defaultdict, Counter

# ------------------------
# Manual input/output path
# ------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "../mturk_results/mturkhit2.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "../mturk_results/v2_2nd_hit_gold_standard_output.json")

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

# ------------------------
# Text Utility Functions
# ------------------------
def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()

def tokenize(text):
    return normalize(text).split()

def non_stopword_overlap(span1, span2):
    tokens1 = set(tokenize(span1)) - STOP_WORDS
    tokens2 = set(tokenize(span2)) - STOP_WORDS
    return len(tokens1 & tokens2) >= 2

def spans_match(span1, span2):
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
        return " ".join(tokens[start:end])

    padded1 = find_window(tokens1, overlap)
    padded2 = find_window(tokens2, overlap)
    if padded1 and padded2:
        return padded1 if len(padded1) <= len(padded2) else padded2
    return padded1 or padded2 or " ".join(overlap)

def compute_confidence(num_supporters, label_consistent):
    if num_supporters == 3:
        return 1.0
    elif num_supporters == 2 and label_consistent:
        return 0.67
    elif num_supporters == 2:
        return 0.5
    else:
        return 0.33


# ------------------------
# Gold Standard Builder (with title saving)
# ------------------------
def build_gold_standard_with_intersection(annotations_by_title, pad=2):
    """
    Builds a gold-standard annotations set grouped by overlapping spans,
    using article titles (not numeric IDs) as keys.
    """
    gold_standard = defaultdict(list)

    for title, spans in annotations_by_title.items():
        grouped = []
        used = set()

        for i, span1 in enumerate(spans):
            if i in used:
                continue
            group = [span1]
            used.add(i)
            for j in range(i + 1, len(spans)):
                if j in used:
                    continue
                span2 = spans[j]
                if spans_match(span1["text"], span2["text"]):
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
            label_consistent = len(set(categories)) == 1 and len(set(subcategories)) == 1
            num_supporters = len(group)
            confidence = compute_confidence(num_supporters, label_consistent)

            gold_standard[title].append({
                "text": text,
                "category": most_common_cat,
                "subcategory": most_common_subcat,
                "confidence": confidence,
                "num_supporters": num_supporters,
                "label_consistent": label_consistent,
                "title": title
            })

    return gold_standard


# ------------------------
# Main Function
# ------------------------
def process_annotation_file(input_path, output_path):
    with open(input_path, "r") as f:
        raw_data = json.load(f)

    annotations_by_title = defaultdict(list)

    for worker_id, entry in raw_data.items():
        # Map IDs to article titles
        titles_map = {}
        if "articleTitles" in entry:
            for t in entry["articleTitles"]:
                titles_map[str(t["id"])] = t["title"]

        ta = entry.get("textAnnotations")
        if not ta:
            continue

        # Case 1: Dict format (standard)
        if isinstance(ta, dict):
            for article_id, annotations in ta.items():
                title = titles_map.get(str(article_id), f"{article_id}")
                if not isinstance(annotations, list):
                    continue
                for ann in annotations:
                    if not isinstance(ann, dict):
                        continue
                    text = ann.get("text", "").strip()
                    if not text:
                        continue
                    annotations_by_title[title].append({
                        "text": text,
                        "category": ann.get("category", ""),
                        "subcategory": ann.get("subcategory", ""),
                        "worker": worker_id
                    })

        # Case 2: List format (rare entries)
        elif isinstance(ta, list):
            for i, annotations in enumerate(ta):
                title = titles_map.get(str(i), f"ARTICLE_{i}")
                if not annotations or not isinstance(annotations, list):
                    continue
                for ann in annotations:
                    if not isinstance(ann, dict):
                        continue
                    text = ann.get("text", "").strip()
                    if not text:
                        continue
                    annotations_by_title[title].append({
                        "text": text,
                        "category": ann.get("category", ""),
                        "subcategory": ann.get("subcategory", ""),
                        "worker": worker_id
                    })

    gold_standard = build_gold_standard_with_intersection(annotations_by_title)

    with open(output_path, "w") as f:
        json.dump(gold_standard, f, indent=2, ensure_ascii=False)

    print(f"\nGold standard saved to: {output_path}")
    print(f"Total articles processed: {len(gold_standard)}")
    print("Sample article titles:", list(gold_standard.keys())[:5])


# ------------------------
# Execute
# ------------------------
if __name__ == "__main__":
    process_annotation_file(INPUT_FILE, OUTPUT_FILE)