# 2-20 LLM vs Human + In-House IRR Round Summary

## 1) Per-class Label Performance (LLM vs Human, min-one matching)

| Class | Precision | Recall | F1 | Support | TP | FP | FN | Disagreement (1-F1) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no polarizing language | 1.000 | 1.000 | 1.000 | 29 | 29 | 0 | 0 | 0.000 |
| persuasive propaganda | 0.760 | 0.704 | 0.731 | 27 | 19 | 6 | 8 | 0.269 |
| inflammatory language | 0.636 | 0.700 | 0.667 | 20 | 14 | 8 | 6 | 0.333 |

## 2) Per-subclass Label Performance (LLM vs Human, min-one matching)

| Subclass | Precision | Recall | F1 | Support | TP | FP | FN | Disagreement (1-F1) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no polarizing language | 1.000 | 1.000 | 1.000 | 29 | 29 | 0 | 0 | 0.000 |
| slogans | 1.000 | 0.800 | 0.889 | 5 | 4 | 0 | 1 | 0.111 |
| name-calling | 0.538 | 0.700 | 0.609 | 10 | 7 | 6 | 3 | 0.391 |
| demonization | 0.625 | 0.455 | 0.526 | 11 | 5 | 3 | 6 | 0.474 |
| exaggeration | 0.417 | 0.556 | 0.476 | 9 | 5 | 7 | 4 | 0.524 |
| doubt | 0.500 | 0.333 | 0.400 | 6 | 2 | 2 | 4 | 0.600 |
| bandwagon | 0.500 | 0.250 | 0.333 | 4 | 1 | 1 | 3 | 0.667 |
| casual oversimplification | 0.000 | 0.000 | 0.000 | 1 | 0 | 4 | 1 | 1.000 |
| scapegoating | 0.000 | 0.000 | 0.000 | 1 | 0 | 0 | 1 | 1.000 |

## 3) Alignment / Disagreement Highlights

| View | Most aligned class | Highest disagreement class |
|---|---|---|
| Category | no polarizing language (F1=1.000) | inflammatory language (F1=0.667) |
| Subcategory (support>=3) | no polarizing language (F1=1.000) | bandwagon (F1=0.333) |

## 4) In-house IRR Across Rounds

| Round | Scope | Units | Pairwise agreement | Krippendorff alpha | Exact consensus | Cohen (weighted mean) | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| 1_initial_collection | paragraph-level open-form (binary) | 97 | 0.498 | -0.020 | 0.247 | 0.190 | 97 paragraph units, 3 raters each |
| 1_initial_collection | paragraph-level open-form (category) | 97 | 0.375 | 0.035 | 0.144 | 0.101 | same units as above |
| 1_initial_collection | paragraph-level open-form (subcategory) | 97 | 0.268 | 0.033 | 0.082 | 0.076 | same units as above |
| 2_validation_tool | proposal-level accept/deny (tool voting) | 495 | 0.662 | 0.311 | 0.493 | n/a | 495 vote-eligible rows from live validation node |
| 3_manual_group_resolution | adjudicated subset accept/deny (final cleaned set) | 106 | 0.516 | -0.317 | 0.274 | n/a | 106 retained rows after discussion (77x2-1, 29x3-0) |
| 3_manual_group_resolution_projected | paragraph-level binary (projected onto same 97 units) | 97 | 0.512 | -0.016 | 0.268 | 0.065 | Reconstructed post-adjudication binary votes on original 97 paragraph units |

### Comparability note
- Round 1 is paragraph-level open-form labeling; Rounds 2-3 are accept/deny adjudication votes over candidate spans, so trend direction is informative but not a strict apples-to-apples IRR comparison.
