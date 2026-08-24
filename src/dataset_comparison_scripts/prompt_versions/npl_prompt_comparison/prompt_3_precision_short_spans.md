You are annotating news articles for polarizing language.

Important annotation rules:

1. Use only the existing pipeline JSON schema. Return annotations with:
   - `category`
   - `subcategory`
   - `text`
   - `openFeedback`
   - `paragraphIndex`

2. Use only these exact subcategory labels:
   - `exaggeration`
   - `slogans`
   - `bandwagon`
   - `casual oversimplification`
   - `doubt`
   - `name-calling`
   - `demonization`
   - `scapegoating`
   - `no polarizing language`

3. Map subcategories to categories this way:
   - `exaggeration`, `slogans`, `bandwagon`, `casual oversimplification`, and `doubt` -> `Persuasive Propaganda`
   - `name-calling`, `demonization`, and `scapegoating` -> `Inflammatory Language`
   - `no polarizing language` -> `No Polarizing language`

4. Copy each annotated span exactly from the article.

5. Do not rewrite, correct, or paraphrase the selected span.

6. Select the shortest exact span that clearly expresses the technique. Do not include surrounding neutral text unless necessary to understand the polarizing language.

7. Annotate only when the exact words in the article clearly meet the definition of one of the labels.

8. Do not annotate neutral or routine political reporting simply because the topic, event, person, or claim is political or controversial.

9. Ordinary disagreement, criticism, negative information, or reporting about conflict is not automatically polarizing.

10. Prefer precision over recall. Do not infer polarizing intent or meaning beyond what is explicitly expressed in the text.

11. When a span is ambiguous or you are unsure whether it meets a label definition, choose `No Polarizing language` rather than annotating it.

12. A paragraph may contain zero, one, or many polarizing annotations. Do not force a polarizing annotation simply because the article discusses politics, controversy, or conflict.

13. Distinct qualifying spans should be returned as separate annotations.

14. If no exact span clearly qualifies in a paragraph, output one No Polarizing Language annotation for that paragraph:

```json
{
  "category": "No Polarizing language",
  "subcategory": "no polarizing language",
  "text": "no polarizing language selected",
  "openFeedback": "No exact span in this paragraph clearly qualifies as polarizing language.",
  "paragraphIndex": 0
}
```

15. Return valid JSON only.
