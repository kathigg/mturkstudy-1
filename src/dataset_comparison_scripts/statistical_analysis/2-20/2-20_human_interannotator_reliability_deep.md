# 2-20 Deep Interannotator Reliability Audit

## Design Choices

- Fixed unit of analysis: paragraph within article.
- All paragraph units in the raw `2-20` file have exactly 3 raters, so Fleiss' kappa is valid on the full paragraph-level dataset.
- Category and subcategory analyses collapse multi-label paragraphs into explicit `multiple ...` classes, and one-vs-rest results are included to check whether that collapse is hiding label-specific behavior.
- Span overlap is reported separately from paragraph-level chance-corrected reliability because span selection and label assignment are different reliability problems.

## Dataset Summary

- Workers: `93`
- Articles: `27`
- Paragraph units: `97`
- Raters per paragraph unit: `3`
- Raw annotations: `515`

## Paragraph-Level Agreement

### Binary

- Pairwise percent agreement: `0.498` with 95% bootstrap CI `[0.443, 0.560]`
- Exact 3-rater consensus rate: `0.247` with 95% bootstrap CI `[0.165, 0.340]`
- Weighted mean pairwise Cohen's kappa: `0.19` with 95% bootstrap CI `[0.158, 0.315]`
- Fleiss' kappa: `-0.022` with 95% bootstrap CI `[-0.137, 0.095]`
- Krippendorff's alpha (nominal): `-0.02` with 95% bootstrap CI `[-0.131, 0.088]`
- Label counts: `{'polarizing language': 165, 'no polarizing language': 126}`

### Category

- Pairwise percent agreement: `0.375` with 95% bootstrap CI `[0.323, 0.433]`
- Exact 3-rater consensus rate: `0.144` with 95% bootstrap CI `[0.082, 0.216]`
- Weighted mean pairwise Cohen's kappa: `0.101` with 95% bootstrap CI `[0.063, 0.218]`
- Fleiss' kappa: `0.033` with 95% bootstrap CI `[-0.053, 0.113]`
- Krippendorff's alpha (nominal): `0.035` with 95% bootstrap CI `[-0.057, 0.113]`
- Label counts: `{'persuasive propaganda': 97, 'no polarizing language': 126, 'inflammatory language': 68}`

### Subcategory

- Pairwise percent agreement: `0.278` with 95% bootstrap CI `[0.230, 0.326]`
- Exact 3-rater consensus rate: `0.072` with 95% bootstrap CI `[0.031, 0.124]`
- Weighted mean pairwise Cohen's kappa: `0.071` with 95% bootstrap CI `[0.054, 0.161]`
- Fleiss' kappa: `-0.036` with 95% bootstrap CI `[-0.096, 0.020]`
- Krippendorff's alpha (nominal): `-0.034` with 95% bootstrap CI `[-0.094, 0.022]`
- Label counts: `{'multiple polarizing subcategories': 95, 'no polarizing language': 126, 'doubt': 10, 'exaggeration': 14, 'demonization': 12, 'slogans': 8, 'name-calling': 15, 'bandwagon': 2, 'casual oversimplification': 6, 'scapegoating': 3}`

## Span-Level Reliability

- Dice/F1 including `no polarizing language`: macro `0.299`, micro `0.272`
- Dice/F1 polarizing-only: macro `0.167`, micro `0.204`
- Among matched polarizing spans, category agreement: micro `0.74`, subcategory agreement: micro `0.481`

## Article-Level Binary Reliability

### Lowest Fleiss' Kappa

- `11` Missouri's only abortion clinic to remain open after judge's injunction holds: Fleiss `-0.5`, alpha `-0.438`, agreement `0.333`, paragraphs `4`
- `1` 'pathetic rout,' 'tragic mistake' and 'painful' john mccain holds little back in describing helsinki: Fleiss `-0.5`, alpha `-0.417`, agreement `0.333`, paragraphs `3`
- `3` Four top residencies now offered to local artists, thanks to Oolite: Fleiss `-0.35`, alpha `-0.275`, agreement `0.333`, paragraphs `3`
- `8` rosemount recreation center plan gets positive response so far: Fleiss `-0.35`, alpha `-0.275`, agreement `0.333`, paragraphs `3`
- `12` BuzzFeed Journalists Protest in Push for Union Recognition: Fleiss `-0.35`, alpha `-0.275`, agreement `0.333`, paragraphs `3`

### Highest Fleiss' Kappa

- `2` phoenix chief says police response to incident with 4-year-old is 'unacceptable': Fleiss `1.0`, alpha `1.0`, agreement `1.0`, paragraphs `4`
- `22` 'if you're directly complicit in spreading hate, consider dining at home': restaurant owner who kicked sarah sanders out last year defends chicago server who spat on eric trump in a cocktail bar: Fleiss `0.314`, alpha `0.343`, agreement `0.667`, paragraphs `4`
- `19` donald trump's criminal justice reform shows results: Fleiss `0.196`, alpha `0.223`, agreement `0.6`, paragraphs `5`
- `7` Ex-Posen mayor pleads guilty to embezzling village funds: Fleiss `0.111`, alpha `0.148`, agreement `0.667`, paragraphs `4`
- `4` Protesters Want All Philadelphia Police Officers Connected To Alleged Racist Social Media Posts To Be Removed From Streets: Fleiss `0.1`, alpha `0.15`, agreement `0.556`, paragraphs `3`

## Interpretation Notes

- If percent agreement is moderate but kappa/alpha stay near zero or below, that usually means prevalence and label imbalance are dominating the chance-corrected metrics.
- If span overlap is low but matched-span subcategory agreement is higher, the main disagreement is span selection rather than taxonomy understanding.
- Rare one-vs-rest labels can show high agreement but unstable alpha because nearly everyone marks them absent.

