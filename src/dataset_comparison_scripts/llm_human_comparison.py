import json
import re
from pathlib import Path

# WHAT THE SCRIPT DOES:
# The script compares annotations from an LLM to human annotations 
# (in this case, annotations made by MTurk workers and consolidated into
# a gold standard data set). It computes precision, recall, and F1 score. 😃

# Paths for the JSON files
BASE_DIR = Path(__file__).resolve().parent.parent  # goes up to /src
LLM_PATH = BASE_DIR / "llm_annotation_results/test_chatgpt.json"
GOLD_PATH = BASE_DIR / "mturk_results/gold_standard_output.json"

def load_json(path):
    with open(path, "r") as f:
        content = f.read().strip()
        if not content:
            raise ValueError(f"Files {path} is empty.")
        return json.loads(content)
    
# ------------------------
# Utility functions
# ------------------------
def normalize(text):
    """Lowercase, remove punctuation, strip."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

def tokenize(text):
    return normalize(text).split()

def overlap(span1, span2, min_overlap=2):
    """Check if there are at least min_overlap shared non-stopwords."""
    tokens1 = set(tokenize(span1))
    tokens2 = set(tokenize(span2))
    return len(tokens1 & tokens2) >= min_overlap

def match_annotation(llm_ann, gold_ann):
    """Return True if annotations overlap and category/subcategory match."""
    if not overlap(llm_ann["text"], gold_ann["text"]):
        return False
    return (llm_ann["category"] == gold_ann["category"] 
            and llm_ann["subcategory"] == gold_ann["subcategory"])

# ------------------------
# Main comparison
# ------------------------
def compare_annotations(llm_json, gold_json):
    # Flatten LLM annotations
    llm_annotations = []
    for ann in llm_json:
        llm_annotations.append({
            "text": ann["text"],
            "category": ann["category"],
            "subcategory": ann["subcategory"]
        })

    # Flatten gold annotations
    gold_annotations = []
    for _, anns in gold_json.items():
        for ann in anns:
            gold_annotations.append({
                "text": ann["text"],
                "category": ann["category"],
                "subcategory": ann["subcategory"]
            })

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
        "total_gold": len(gold_annotations)
    }

def load_json(path):
    with open(path, "r") as f:
        content = f.read().strip()
        if not content:
            raise ValueError(f"File {path} is empty.")
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}")

if __name__ == "__main__":
    llm_json = load_json(LLM_PATH)
    gold_json = load_json(GOLD_PATH)
    output_file = "annotation_comparison_results.json"
    
    # Compare
    results = compare_annotations(llm_json, gold_json)

    # Save results
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to {output_file}")