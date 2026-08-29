# Bagozzi 27-Article ChatGPT Rerun

## Inputs

- Article CSV: [2-20_selected_articles.csv](../../2-20/2-20_selected_articles.csv)
- Human gold: [bagozzi_27_human_min_one_gold_standard_output.json](./bagozzi_27_human_min_one_gold_standard_output.json)
- New LLM JSON: [2-20_bagozzi_prompt_chatgpt_min_one_final_annotations_3annotators.json](../../../llm_annotation_results/2-20/2-20_bagozzi_prompt_chatgpt_min_one_final_annotations_3annotators.json)
- New comparison JSON: [bagozzi_27_llm_vs_human_min_one_results_rerun.json](./bagozzi_27_llm_vs_human_min_one_results_rerun.json)

## Run Configuration

Used the updated Dr. Bagozzi-aligned prompt in [run_wrapper_multiple_llm_annotations.py](../../run_wrapper_multiple_llm_annotations.py).

Command:

```bash
python3 src/dataset_comparison_scripts/run_wrapper_multiple_llm_annotations.py \
  --input src/dataset_comparison_scripts/2-20/2-20_selected_articles.csv \
  --results-csv src/dataset_comparison_scripts/2-20/2-20_bagozzi_prompt_chatgpt_results_3annotators.csv \
  --final-json src/llm_annotation_results/2-20/2-20_bagozzi_prompt_chatgpt_min_one_final_annotations_3annotators.json \
  --final-jsonl src/llm_annotation_results/2-20/2-20_bagozzi_prompt_chatgpt_min_one_final_annotations_3annotators.jsonl \
  --paragraph-policy min-one \
  --annotator-b-provider openai \
  --checkpoint-every 1
```

Notes:

- This rerun used `openai` for Annotator A, Annotator B, Annotator C, and the adjudicator.
- The wrapper needed two robustness fixes during the run:
  - accept a valid JSON object followed by stray trailing text
  - accept responses that return bare annotation objects / bare annotation-object sequences instead of a full wrapper

## New Results

Dataset size:

- Articles: `27`
- Final LLM annotations: `208`
- Human gold annotations: `157`

Overall metrics:

| Metric | Value |
| --- | ---: |
| Article-match precision | 0.423 |
| Article-match recall | 0.561 |
| Article-match F1 | 0.482 |
| Category-match precision | 0.693 |
| Category-match recall | 0.693 |
| Category-match F1 | 0.693 |
| Weighted article-match precision | 0.255 |
| Weighted article-match recall | 0.523 |
| Weighted article-match F1 | 0.343 |

Counts:

- Matched spans: `88`
- Category+subcategory agreements on matched spans: `61`
- LLM-only spans: `120`
- Human-only spans: `69`

## Comparison To Prior Reused 2-20 LLM File

Earlier comparison file:

- [bagozzi_27_llm_vs_human_min_one_results.json](./bagozzi_27_llm_vs_human_min_one_results.json)

Difference:

| Metric | Prior Reused LLM | New ChatGPT Rerun | Delta |
| --- | ---: | ---: | ---: |
| Article-match precision | 0.466 | 0.423 | -0.043 |
| Article-match recall | 0.656 | 0.561 | -0.095 |
| Article-match F1 | 0.545 | 0.482 | -0.063 |
| Category-match F1 | 0.835 | 0.693 | -0.142 |
| Weighted article-match F1 | 0.432 | 0.343 | -0.089 |

## Quick Read

- The rerun completed successfully with the updated prompt and all-OpenAI configuration.
- On this Dr. Bagozzi gold comparison, the new rerun performed worse than the earlier reused `2-20` LLM file.
- The new rerun also produced fewer total LLM annotations (`208` vs `221`) and fewer matched spans (`88` vs `103`).
