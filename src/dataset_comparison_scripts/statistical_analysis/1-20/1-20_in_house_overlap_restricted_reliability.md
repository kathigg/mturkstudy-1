# Overlap-Restricted Reliability

## Clarification

- The raw annotation file contains explicit `No_Polarizing_Language` annotations. The IRR code is not inventing NPL when a row is absent; the paragraph-level comparison is reading those explicit NPL annotations from the saved data.

## Unit Counts

- Paragraph units in full dataset: `38`
- Paragraph units with exactly 3 raters: `35`
- Paragraph units where all 3 raters marked polarizing spans: `6`
- Shared 3-way overlapping span instances: `1`

## Full Dataset

- Binary: agreement `0.642`, exact consensus `0.474`, Cohen `0.229`, Fleiss `n/a`, alpha `0.239`
- Category: agreement `0.618`, exact consensus `0.447`, Cohen `0.205`, Fleiss `n/a`, alpha `0.224`
- Subcategory: agreement `0.504`, exact consensus `0.342`, Cohen `0.147`, Fleiss `n/a`, alpha `0.139`

## Overlap-Restricted Paragraphs

- Restriction: only paragraph units with exactly 3 raters where each rater marked at least one polarizing span.
- Category: agreement `0.889`, exact consensus `0.833`, Cohen `1.0`, Fleiss `0.437`, alpha `0.453`
- Subcategory: agreement `0.333`, exact consensus `0.167`, Cohen `0.0`, Fleiss `0.15`, alpha `0.173`

## Explicit Shared-Span Instances

- Restriction: only connected overlap components where all 3 raters marked the same polarizing instance.
- Category: agreement `0.333`, exact consensus `0.0`, Cohen `n/a`, Fleiss `-0.5`, alpha `-0.25`
- Subcategory: agreement `0.0`, exact consensus `0.0`, Cohen `n/a`, Fleiss `-0.5`, alpha `-0.25`

## Interpretation

- If overlap-restricted alpha/kappa are higher than full-dataset alpha/kappa, that supports the idea that coverage disagreement is depressing the headline paragraph-level IRR.
- The shared-span view is the cleanest estimate of label agreement after span-selection disagreement has already been removed.

