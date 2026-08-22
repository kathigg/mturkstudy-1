# In-House Raw Annotation Round Exports

This folder contains raw Firebase-export data for the in-house human annotation rounds before final consolidation/adjudication.

## Files

- `round1_raw_inhouse_open_form_submissions_pre_consolidation.json`
  - Source: `src/mturk_results/2-20/cisc475database-default-rtdb-submissions-export.json`
  - Meaning: original in-house open-form span annotations before consolidation/adjudication.
  - Structure: Firebase submissions keyed by submission id. Each submission contains `articleTitles`, `surveyResponses`, `textAnnotations`, and `timestamp`.
  - Quick check: 81 submissions across 27 article ids; 500 raw text annotation records.

- `round2_raw_inhouse_validation_votes_accept_deny.json`
  - Source: `src/mturk_results/live/cisc475database-default-rtdb-InHouse-Annotations-export.json`
  - Meaning: validation round where in-house annotators accepted/denied each other's candidate spans.
  - Structure: list of 27 article blocks; each block contains span clusters; each candidate span row includes `accept`, `deny`, `meta`, `span`, and `subcategory`.
  - Quick check: 27 article blocks, 97 span clusters, 516 candidate span rows.

- `round2_inhouse_validation_submission_metadata.json`
  - Source: `src/mturk_results/live/cisc475database-default-rtdb-InHouse-Submissions-export.json`
  - Meaning: metadata/completion-code records for the validation round. This file does not contain the accept/deny span judgments themselves; those are in `round2_raw_inhouse_validation_votes_accept_deny.json`.
  - Structure: Firebase submissions keyed by submission id with `articleTitles`, `code`, `surveyResponses`, and `timestamp`.

## Note

These are raw copied exports, not cleaned, consolidated, majority-voted, or final-adjudicated datasets.
