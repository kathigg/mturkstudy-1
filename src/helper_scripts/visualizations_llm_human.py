import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# ------------------------------
# Load Data
# ------------------------------

with open("src/mturk_results/v3_2nd_hit_gold_standard_output.json", "r") as f:
    human = json.load(f)

with open("src/llm_annotation_results/final_annotations_3annotators (1).json", "r") as f:
    llm = json.load(f)

# ------------------------------
# Convert Human Data to DataFrame
# ------------------------------

human_rows = []
for article in human:
    title = article["title"]
    for ann in article["annotations"]:
        human_rows.append({
            "title": title,
            "category": ann["category"],
            "subcategory": ann["subcategory"],
            "text": ann["text"]
        })

df_human = pd.DataFrame(human_rows)

# ------------------------------
# Convert LLM Data to DataFrame
# ------------------------------

llm_rows = []
for article in llm:
    title = article["title"]
    for ann in article["annotations"]:
        llm_rows.append({
            "title": title,
            "category": ann["category"],
            "subcategory": ann["subcategory"],
            "text": ann["text"]
        })

df_llm = pd.DataFrame(llm_rows)

# ------------------------------
# Category Counts
# ------------------------------

human_cat_counts = df_human["category"].value_counts()
llm_cat_counts = df_llm["category"].value_counts()

# ------------------------------
# Span Count Per Article
# ------------------------------

human_spans = df_human.groupby("title").size()
llm_spans = df_llm.groupby("title").size()

# Align indices
span_compare = pd.DataFrame({
    "human_spans": human_spans,
    "llm_spans": llm_spans
}).fillna(0)

span_compare["difference"] = span_compare["human_spans"] - span_compare["llm_spans"]

# ------------------------------
# Visualization 1:
# Bar chart – Human category frequencies
# ------------------------------

plt.figure(figsize=(10, 6))
human_cat_counts.plot(kind="bar", color="steelblue")
plt.title("Human Annotation Category Frequencies")
plt.ylabel("Count")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# ------------------------------
# Visualization 2:
# Bar chart – LLM category frequencies
# ------------------------------

plt.figure(figsize=(10, 6))
llm_cat_counts.plot(kind="bar", color="darkorange")
plt.title("LLM Annotation Category Frequencies")
plt.ylabel("Count")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# ------------------------------
# Visualization 3:
# Bar chart – Spans per article (Human vs LLM)
# ------------------------------

plt.figure(figsize=(12, 6))
span_compare[["human_spans", "llm_spans"]].plot(kind="bar", figsize=(12, 6))
plt.title("Number of Spans per Article: Human vs LLM")
plt.ylabel("Span Count")
plt.xticks(rotation=60)
plt.tight_layout()
plt.show()

# ------------------------------
# Visualization 4:
# Scatter plot – Human vs LLM span counts
# ------------------------------

plt.figure(figsize=(8, 6))
plt.scatter(span_compare["human_spans"], span_compare["llm_spans"], s=100, alpha=0.7)
plt.title("Human Spans vs LLM Spans per Article")
plt.xlabel("Human Span Count")
plt.ylabel("LLM Span Count")

# Add y = x reference line
max_val = max(span_compare.max())
plt.plot([0, max_val], [0, max_val], 'r--')

plt.tight_layout()
plt.show()

# ------------------------------
# Visualization 5:
# Histogram – Distribution of annotation differences
# (Human minus LLM spans)
# ------------------------------

plt.figure(figsize=(8, 6))
plt.hist(span_compare["difference"], bins=range(int(span_compare["difference"].min()),
                                               int(span_compare["difference"].max()) + 2),
         color="purple", edgecolor="black")
plt.title("Distribution of Annotation Differences (Human - LLM)")
plt.xlabel("Difference in Number of Spans")
plt.ylabel("Number of Articles")
plt.tight_layout()
plt.show()

# ------------------------------
# Print Summary Stats
# ------------------------------

print("\n=== SUMMARY STATISTICS ===")
print("Total Human Spans:", df_human.shape[0])
print("Total LLM Spans:", df_llm.shape[0])
print("\nAverage Human Spans per Article:", human_spans.mean())
print("Average LLM Spans per Article:", llm_spans.mean())
print("\nAverage Under-Annotation (Human - LLM):", span_compare["difference"].mean())
print("\nArticles with LLM = 0 spans:\n", span_compare[span_compare["llm_spans"] == 0])