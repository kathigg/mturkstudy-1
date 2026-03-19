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
