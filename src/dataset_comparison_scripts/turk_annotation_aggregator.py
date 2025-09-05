import json
import re
from collections import defaultdict, Counter

# ------------------------
# Manual input/output path
# ------------------------
INPUT_FILE = "../mturk_results/cisc475database-default-rtdb-submissions-export.json"
OUTPUT_FILE = "/Users/kathleenhiggins/mturkstudy/src/mturk_results/gold_standard_output.json"

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
    text = re.sub(r'[^\w\s]', '', text)
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

# ------------------------
# Gold Standard Builder
# ------------------------
def build_gold_standard_with_intersection(annotations_by_article, pad=2):
    gold_standard = defaultdict(list)

    for article_id, spans in annotations_by_article.items():
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

            gold_standard[article_id].append({
                "text": text,
                "category": most_common_cat,
                "subcategory": most_common_subcat,
                "confidence": confidence,
                "num_supporters": num_supporters,
                "label_consistent": label_consistent
            })

    return gold_standard

# ------------------------
# Main Function
# ------------------------
def process_annotation_file(input_path, output_path):
    with open(input_path, "r") as f:
        raw_data = json.load(f)

    annotated_spans = defaultdict(list)
    for worker_id, entry in raw_data.items():
        for article_id, annotations in entry["textAnnotations"].items():
            for ann in annotations:
                if ann["text"] == "No bias selected":
                    continue
                annotated_spans[article_id].append({
                    "text": ann["text"],
                    "category": ann["category"],
                    "subcategory": ann["subcategory"],
                    "worker": worker_id
                })

    gold_standard = build_gold_standard_with_intersection(annotated_spans)

    with open(output_path, "w") as f:
        json.dump(gold_standard, f, indent=2)

    print(f"✅ Gold standard saved to: {output_path}")

# ------------------------
# Execute
# ------------------------
if __name__ == "__main__":
    process_annotation_file(INPUT_FILE, OUTPUT_FILE)