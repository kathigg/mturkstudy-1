# Bagozzi 27-Article LLM Comparison

## Scope

This run compares the Dr. Bagozzi Firebase annotations for the 27-article subset against the existing 27-article LLM annotation output already stored in the repo.

Inputs:

- Human source: [cisc475database-default-rtdb-Bagozzi-Annotations-export.json](../../../mturk_results/live/cisc475database-default-rtdb-Bagozzi-Annotations-export.json)
- Aggregated human gold: [bagozzi_27_human_min_one_gold_standard_output.json](./bagozzi_27_human_min_one_gold_standard_output.json)
- LLM source: [2-20_llm_min_one_final_annotations_3annotators.json](../../../llm_annotation_results/2-20/2-20_llm_min_one_final_annotations_3annotators.json)
- Comparison output: [bagozzi_27_llm_vs_human_min_one_results.json](./bagozzi_27_llm_vs_human_min_one_results.json)

## Method

Used the same two scripts as the prior human-vs-LLM runs:

1. `src/dataset_comparison_scripts/paragraph_turk_annotation_aggregator.py`
2. `src/dataset_comparison_scripts/paragraph_llm_human_comparison.py`

Commands:

```bash
python3 src/dataset_comparison_scripts/paragraph_turk_annotation_aggregator.py \
  --input src/mturk_results/live/cisc475database-default-rtdb-Bagozzi-Annotations-export.json \
  --output src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/bagozzi_27_human_min_one_gold_standard_output.json \
  --min-supporters-to-save 1

python3 src/dataset_comparison_scripts/paragraph_llm_human_comparison.py \
  --llm-path src/llm_annotation_results/2-20/2-20_llm_min_one_final_annotations_3annotators.json \
  --gold-path src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/bagozzi_27_human_min_one_gold_standard_output.json \
  --output src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/bagozzi_27_llm_vs_human_min_one_results.json
```

Notes:

- The Firebase export contains `27` article entries and `163` raw Dr. Bagozzi span annotations.
- Using the same aggregation logic as prior runs, those raw annotations became `157` gold annotations after overlap consolidation.
- The LLM file contains `27` matching article titles and `221` final annotations.

## Results

Overall metrics:

| Metric | Value |
| --- | ---: |
| Article-match precision | 0.466 |
| Article-match recall | 0.656 |
| Article-match F1 | 0.545 |
| Category-match precision | 0.835 |
| Category-match recall | 0.835 |
| Category-match F1 | 0.835 |
| Weighted article-match precision | 0.314 |
| Weighted article-match recall | 0.688 |
| Weighted article-match F1 | 0.432 |

Breakdown:

- Matched spans: `103`
- Category+subcategory agreement on matched spans: `86`
- LLM-only spans: `118`
- Human-only spans: `54`

Per-category agreement on matched spans:

| Category | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| No polarizing language | 1.000 | 1.000 | 1.000 | 30 |
| Inflammatory language | 0.791 | 0.919 | 0.850 | 37 |
| Persuasive propaganda | 0.900 | 0.750 | 0.818 | 36 |

Selected subcategory results:

| Subcategory | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| No polarizing language | 1.000 | 1.000 | 1.000 | 30 |
| Slogans | 1.000 | 0.857 | 0.923 | 7 |
| Name-calling | 0.778 | 0.778 | 0.778 | 27 |
| Exaggeration | 0.786 | 0.647 | 0.710 | 17 |
| Doubt | 1.000 | 0.444 | 0.615 | 9 |
| Demonization | 0.400 | 0.750 | 0.522 | 8 |
| Casual oversimplification | 0.400 | 0.667 | 0.500 | 3 |
| Bandwagon | 0.000 | 0.000 | 0.000 | 0 |
| Scapegoating | 0.000 | 0.000 | 0.000 | 2 |

Largest error concentrations:

- LLM-only categories: `Inflammatory language` (`9`), `Persuasive propaganda` (`3`)
- Human-only categories: `Persuasive propaganda` (`9`), `Inflammatory language` (`3`)
- LLM-only subcategories: `Demonization` (`9`), `Name-calling` (`6`)
- Human-only subcategories: `Exaggeration` (`6`), `Name-calling` (`6`), `Doubt` (`5`)

Article outlier:

- The Meghan Markle article had `0` matched spans.

## Comparison To Prior 2-20 Human-vs-LLM Run

Compared with the existing 2-20 aggregated-human result file, the Dr. Bagozzi comparison is higher:

| Metric | Prior 2-20 Human Gold | Dr. Bagozzi Gold |
| --- | ---: | ---: |
| Article-match precision | 0.344 | 0.466 |
| Article-match recall | 0.628 | 0.656 |
| Article-match F1 | 0.444 | 0.545 |
| Category-match F1 | 0.671 | 0.835 |
| Weighted article-match F1 | 0.372 | 0.432 |

This is not a strict apples-to-apples change in model quality, because the gold standard changed from the earlier aggregated human set to a single-annotator Dr. Bagozzi set.

## Caveats

- One Dr. Bagozzi paragraph contains both `No_Polarizing_Language` and a polarizing annotation:
  - Article: `GOP lawmaker suggests Colin Kaepernick move to a different country`
  - Paragraph index: `2`
- The saved `2-20` LLM JSON is the canonical prior LLM output in the repo, but the JSON itself does not embed provider metadata. The repo’s generation pipeline is the existing multi-annotator/adjudicator wrapper, so this run reused the stored 27-article LLM output rather than regenerating new model annotations.
