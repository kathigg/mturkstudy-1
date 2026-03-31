# Overlap-Restricted Reliability

## Clarification

- The raw annotation file contains explicit `No_Polarizing_Language` annotations. The IRR code is not inventing NPL when a row is absent; the paragraph-level comparison is reading those explicit NPL annotations from the saved data.

## Unit Counts

- Paragraph units in full dataset: `97`
- Paragraph units with exactly 3 raters: `97`
- Paragraph units where all 3 raters marked polarizing spans: `17`
- Shared 3-way overlapping span instances: `10`

## Full Dataset

- Binary: agreement `0.498`, exact consensus `0.247`, Cohen `0.19`, Fleiss `-0.022`, alpha `-0.02`
- Category: agreement `0.375`, exact consensus `0.144`, Cohen `0.101`, Fleiss `0.033`, alpha `0.035`
- Subcategory: agreement `0.278`, exact consensus `0.072`, Cohen `0.071`, Fleiss `-0.036`, alpha `-0.034`

## Overlap-Restricted Paragraphs

- Restriction: only paragraph units with exactly 3 raters where each rater marked at least one polarizing span.
- Category: agreement `0.608`, exact consensus `0.412`, Cohen `-0.1`, Fleiss `0.201`, alpha `0.208`
- Subcategory: agreement `0.255`, exact consensus `0.0`, Cohen `0.244`, Fleiss `-0.113`, alpha `-0.102`

## Explicit Shared-Span Instances

- Restriction: only connected overlap components where all 3 raters marked the same polarizing instance.
- Category: agreement `0.733`, exact consensus `0.6`, Cohen `0.333`, Fleiss `0.464`, alpha `0.473`
- Subcategory: agreement `0.4`, exact consensus `0.3`, Cohen `0.333`, Fleiss `0.301`, alpha `0.312`

## Interpretation

- If overlap-restricted alpha/kappa are higher than full-dataset alpha/kappa, that supports the idea that coverage disagreement is depressing the headline paragraph-level IRR.
- The shared-span view is the cleanest estimate of label agreement after span-selection disagreement has already been removed.

