# Sensify Lab: Community Comms Project, MTurk Survey Tool

**Principal Developer:** Kathleen Higgins (Summer 2025)
**Principal Investigator:** Prerana Khatiwada (PhD) and Professor Matthew Mauriello

## Repository Design
```
mturkstudy-3/
├─ README.md
├─ updates.md
├─ package.json
├─ package-lock.json
├─ public/
├─ src/
│  ├─ website_management/                 # React annotation tool (UI)
│  │  ├─ pages/
│  │  ├─ components/
│  │  └─ helper_scripts/
│  │
│  ├─ dataset_comparison_scripts/         # Core pipelines + evaluation
│  │  ├─ run_wrapper_multiple_llm_annotations.py
│  │  ├─ run_wrapper_multiple_llm_annotations_flexible.py
│  │  ├─ paragraph_llm_human_comparison.py
│  │  ├─ paragraph_turk_annotation_aggregator.py
│  │  ├─ multiple_llm_annotations_script.py
│  │  ├─ requirements_llm_notebook.txt
│  │  ├─ per_model_annotations/
│  │  │  └─ run_wrapper_multiple_llm_annotations_per_model.py
│  │  ├─ statistical_analysis/
│  │  │  └─ inter_annotator_agreement_1_8.py
│  │  └─ archived_comparison_scripts/
│  │
│  ├─ helper_scripts/                     # Figures / analysis helpers
│  │  ├─ visualize_llm_vs_raw_mturk_subcategory_confusion_matrix_pooled.py
│  │  ├─ visualize_precision_recall_llm_vs_raw_mturk_by_category_severity.py
│  │  └─ gold_standard_visualizations/
│  │     ├─ visualize_llm_vs_gold_subcategory_confusion_matrix.py
│  │     └─ visualize_precision_recall_by_category_severity.py
│  │
│  ├─ llm_annotation_results/             # LLM outputs (current + archived)
│  │  ├─ final_annotations_3annotators.json
│  │  ├─ multi_llm_annotations/
│  │  ├─ per_model_annotations/
│  │  └─ archived_llm_annotations/
│  │
│  ├─ mturk_results/                      # MTurk outputs (current + archived)
│  │  ├─ 1-20_hit_gold_standard_output.json
│  │  ├─ archived_mturk_results/
│  │  │  └─ 1-8/
│  │  │     ├─ 1-8HIT.json
│  │  │     └─ 1-8HIT_2026_01.json
│  │  └─ ...
│  │
│  └─ data_visualizations/                # Saved plots (PNG) + mpl cache
│     └─ ...
└─ annotation_comparison_results.json
```

This project is divided into several sections. 

Table of Contents: 
- News Annotation Platform
- Annotation Aggregation Scripts 
- LLM Scripts
- LLM vs Turker Comparison Process 

## Important Files Description

This script (run_wrapper_multiple_llm_annotations.py ) is a multi-LLM annotation pipeline for news articles. It reads a CSV of articles, sends each article to three annotators (two OpenAI-style roles and one Gemini/OpenAI annotator), then sends their outputs to an OpenAI adjudicator to produce one final annotation set.
It also does a lot of cleanup and validation: it enforces the JSON schema, normalizes labels, repairs missing fields, assigns paragraph indices, and applies a paragraph policy like exactly one annotation per paragraph or minimum one annotation per paragraph. Finally, it saves the raw annotator outputs to a CSV and the final adjudicated annotations to JSON, with resume/checkpoint support so long runs do not get lost.   

This script ( /run_wrapper_multiple_llm_annotations_per_model.py) runs three LLM annotators (A, B, C) on the same set of articles but does NOT combine or adjudicate their outputs. Instead, it saves each model’s annotations separately so you can analyze model disagreement and variability. It also enforces a minimum-one-per-paragraph policy, ensuring every paragraph has at least one annotation while still allowing multiple annotations when present.


This script (multiple_llm_annotations_script)  is just a wrapper/launcher, it doesn’t do any annotation or processing itself.
Its only job is to run another script (run_wrapper_multiple_llm_annotations.py) using runpy. So when we execute this file, it simply forwards execution to the main annotation pipeline.


This script (llm_human_comparison.py) compares LLM-generated annotations with gold-standard human annotations. It matches spans and labels between the two, then computes precision, recall, and F1 scores to measure how well the LLM performed. It also supports confidence-weighted evaluation, where higher-confidence gold annotations are given more importance, and outputs both overall metrics and per-article results.

 This script ( turk_annotation_aggregator.py ) builds a gold-standard annotation file from the MTurk annotations. It groups together overlapping spans across annotators, chooses the most common category/subcategory for each group, computes a confidence score based on how many annotators supported it and whether their labels were consistent, and then saves the result in a clean article-level JSON format for later comparison with LLM annotations. It also carries over article titles and extracts a shared overlap-based text span to represent each grouped annotation.   
 
The script (in_house_density_and_agreement.py ) analyzes our in-house annotation dataset to compute overall statistics and agreement. It measures things like label distribution (density), span overlap between annotators, and inter-annotator reliability (agreement, Cohen’s kappa, Krippendorff’s alpha) at binary, category, and subcategory levels. It also includes one-vs-rest analysis for specific labels to understand how consistently each type of propaganda is identified.  

This script (in_house_overlap_restricted_reliability.py) computes inter-annotator reliability (IRR) for the dataset in two ways: on the full dataset and on overlap-restricted subsets. It filters to cases where all annotators marked polarizing content (and even shared overlapping spans), then recalculates agreement (kappa, alpha, etc.) to see if disagreement is due to different span selection vs actual label disagreement. It outputs both a JSON file and a readable Markdown report with interpretation.

This script ( paragraph_llm_human_comparison.py ) compares LLM annotations and human gold-standard annotations at the article + paragraph level. It matches spans only when they come from the same article and same paragraph, then computes precision, recall, F1, category/subcategory performance, and confidence-weighted metrics to evaluate how well the LLM agrees with the gold labels.
It also supports a few extra evaluation options: we can enforce one annotation per paragraph for stricter apples-to-apples comparison, print matched pairs for a specific article for debugging, and optionally compute bootstrap confidence intervals for the overall metrics. In short, it is a more advanced comparison/evaluation script for measuring LLM-vs-human annotation performance under different settings.

This script (paragraph_turk_annotation_aggregator) builds a human gold-standard annotation file from the MTurk data, but in a more flexible way. It groups overlapping annotations within the same article and paragraph, computes a confidence score based on how many annotators supported each label, and then saves only annotations that meet a chosen minimum supporter threshold.
It also supports two modes: exact-one, where it keeps only the single best annotation per paragraph, and min-one, where it can keep multiple qualifying polarizing annotations per paragraph and only uses a No Polarizing Language placeholder when needed. In short, this is a more advanced gold-standard builder that lets you control how strict or permissive the final human reference file should be.


## News Annotation Platform 

This is a browser-based annotation platform for labeling persuasive propaganda, inflammatory language, and misleading content in news articles. Designed for MTurk and human-subject studies.

### Location: 
/mturkstudy/src/website_management

### Features

- Highlight text and apply structured labels
- Customizable categories and survey questions
- Supports article-by-article surveys
- JSON export or Firebase integration
- “Thank You” screen with MTurk code

### Customization via `config.js`

To adapt the tool for your own study, edit `config.js`:

- `articles`: your article text and titles
- `categoryOptions`: tags available to annotators
- `surveyQuestions`: Likert-style post-annotation questions

## Getting Started

1. Clone this repo
2. Run `npm install`
3. Update `config.js`
4. Run locally: `npm start`
5. Optionally deploy on Vercel, Netlify, or Firebase

### Example Output

At the end of the task, all annotations and survey responses are saved as structured JSON and can optionally be uploaded to Firebase.

## Scheduled Firebase Sync

The repo now includes a scheduled GitHub Actions workflow at
`.github/workflows/firebase-daily-sync.yml` that exports these Firebase
Realtime Database nodes:

`src/mturk_results/live/cisc475database-default-rtdb-submissions-export.json`
`src/llm_annotation_results/live/cisc475database-default-rtdb-LLMAnnotations-export.json`

The export is performed by
`src/website_management/helper_scripts/export_firebase_snapshot.mjs`.

Setup requirements:
- Add a GitHub Actions secret named `FIREBASE_SERVICE_ACCOUNT_JSON`.
- Paste in the full contents of your local `serviceAccountKey.json`.
- The workflow runs every morning at `9:00 AM` in `America/New_York`.

Implementation note:
- GitHub Actions cron is UTC, so the workflow schedules both `13:00` and `14:00` UTC and only proceeds when the runner's local New York hour is `09`. That keeps the run aligned with daylight saving time.

Local manual export example:

```bash
node src/website_management/helper_scripts/export_firebase_snapshot.mjs \
  --serviceAccount serviceAccountKey.json \
  --output src/mturk_results/live/cisc475database-default-rtdb-submissions-export.json
```

### Notes: `in_house_live_validation_three_way_split_clusters.csv`

- File: `src/dataset_comparison_scripts/statistical_analysis/live/in_house_live_validation_three_way_split_clusters.csv`
- This is an adjudication-focused CSV built from the live `InHouse-Annotations` validation data after overlapping same-subcategory proposals are consolidated into clusters.
- Each row is a consolidated cluster with an exact 3-vote split pattern of `2-1` or `1-2`, meaning one validator disagreed with the other two about whether that annotation should be kept.
- We made it so the hard in-house cases can be re-reviewed in a second agree/disagree pass instead of re-validating the entire dataset.
- The CSV includes the article title, paragraph index, vote pattern, category, subcategory, representative span text, representative annotator, and the underlying clustered span texts/metas.
- It is meant to function as a working notes/adjudication sheet for improving the final approved human set and, if needed, raising validation agreement metrics like Krippendorff’s alpha.

### Designed For Research

This tool was created for a human-subject study but is reusable across research domains involving:
- Misinformation
- Bias detection
- Media literacy

## License

MIT License

## Annotation Aggregation Scripts 

### Location: 
/mturkstudy/src/gold_standard_dataset

### About:
Contains code that aggregates the work of different annotators into a single dataset that contains confidence scores that can be compared to LLMs. 
