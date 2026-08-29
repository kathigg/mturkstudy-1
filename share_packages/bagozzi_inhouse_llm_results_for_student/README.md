# Bagozzi/In-House LLM Results Package

Created: 2026-08-27

This archive collects the current manuscript-facing results for the Dr. Bagozzi plus in-house annotation comparison work.

## What Is Included

- `analysis_outputs/bagozzi_27/`: gold/reference datasets, comparison summaries, tables, figures, decision-point adjudication outputs, and plotting/table scripts.
- `llm_outputs/2-20/`: final LLM annotation outputs for the 27-article runs, including single-model, original adjudication, prompt-comparison, and decision-point outputs.
- `repro_scripts/`: core scripts used for matching, decision-point adjudication, and NPL-inclusive metric computation.

## Key Files

- `analysis_outputs/bagozzi_27/model_prompt_overall_f1_table_npl_inclusive.csv`: ranked model/prompt table with polarization, category, and subcategory precision/recall/F1.
- `analysis_outputs/bagozzi_27/model_prompt_overall_f1_table_npl_inclusive.md`: readable Markdown version of the same table.
- `analysis_outputs/bagozzi_27/figures/model_gold_miss_heatmap_npl_inclusive_overall_ranked.png`: heatmap ranked by overall NPL-inclusive polarization F1.
- `analysis_outputs/bagozzi_27/figures/model_misses_vs_gold_by_severity_npl_inclusive.png`: simpler severity-vs-misses diagram using a linear scale.
- `analysis_outputs/bagozzi_27/consolidated_bagozzi_inhouse_overlap_gold_with_conservative_npl_paragraph_spans.json`: final consolidated gold reference with conservative NPL paragraph spans.
- `analysis_outputs/bagozzi_27/decision_point_adjudication_v1/ablation_summary.csv`: decision-point ablation metrics.

## Current Main Result

Using the NPL-inclusive comparison method on the consolidated Dr. Bagozzi plus in-house intersection gold set, the best overall configuration is:

- `Decision point binary filter`
- Polarization F1: `0.628`
- Category F1: `0.560`
- Subcategory F1: `0.531`

The strongest plain single-model result is:

- `GPT-5 mini + P5 human aligned`
- Polarization F1: `0.602`

## Metric Note

The main metric table uses NPL-inclusive matching. Polarizing spans are matched using the existing span-overlap logic; no-polarizing-language annotations are matched at the paragraph level.
