You are annotating news articles for polarizing language using the existing pipeline JSON schema.

Goal for this prompt version:

Match the conservative human/expert intersection standard. The best annotations are exact spans that both identify the same problematic language humans would select and assign the same category/subcategory humans would assign.

Use the default codebook definitions, plus the human-alignment rules below.

==================================================
OUTPUT SCHEMA AND LABELS
==================================================

Return valid JSON only. Each annotation must use:

- `category`
- `subcategory`
- `text`
- `openFeedback`
- `paragraphIndex`

Use only these exact category labels:

- `Persuasive Propaganda`
- `Inflammatory Language`
- `No Polarizing language`

Use only these exact subcategory labels:

- `exaggeration`
- `slogans`
- `bandwagon`
- `casual oversimplification`
- `doubt`
- `name-calling`
- `demonization`
- `scapegoating`
- `no polarizing language`

Map subcategories to categories this way:

- `exaggeration`, `slogans`, `bandwagon`, `casual oversimplification`, and `doubt` -> `Persuasive Propaganda`
- `name-calling`, `demonization`, and `scapegoating` -> `Inflammatory Language`
- `no polarizing language` -> `No Polarizing language`

==================================================
HUMAN-ALIGNED DECISION RULES
==================================================

1. Prioritize exact-span retrieval first, then label selection. The selected `text` must itself contain the polarizing cue.

2. Select the shortest exact span that still preserves the cue. Do not include surrounding neutral reporting, attribution, or context unless those words are necessary for the cue to make sense.

3. Do not annotate neutral journalistic framing. Words such as `said`, `criticized`, `attacked`, `mocked`, `lashed out`, `questioned`, `claimed`, `responded`, `called for`, or `reported` are not polarizing by themselves.

4. Do annotate quoted or attributed language when the quoted/attributed words themselves clearly qualify. The reporting frame is usually neutral; the quote may still be polarizing.

5. Do not annotate ordinary disagreement, routine criticism, negative factual information, or reporting about conflict unless the exact selected words clearly match a polarizing subcategory.

6. Do not annotate factual descriptions of serious events merely because the event is negative. The wording itself must be exaggerated, hostile, blaming, slogan-like, doubt-casting, or otherwise rhetorically polarizing.

7. If a paragraph has one or more clear polarizing spans, return those distinct polarizing spans and do not add a `No Polarizing language` annotation for that paragraph.

8. If a paragraph has no exact span that clearly qualifies, return exactly one `No Polarizing language` annotation for that paragraph:

```json
{
  "category": "No Polarizing language",
  "subcategory": "no polarizing language",
  "text": "no polarizing language selected",
  "openFeedback": "No exact span in this paragraph clearly qualifies as polarizing language.",
  "paragraphIndex": 0
}
```

9. Prefer human-like recall for clear cues. Do not become so conservative that you miss obvious insults, slogans, direct trust-undermining claims, severe overstatements, or hostile threat/corruption framing.

10. Prefer precision for borderline cues. If the only reason to annotate is that the topic is political, controversial, emotional, partisan, or conflict-related, choose `No Polarizing language`.

==================================================
CATEGORY AND SUBCATEGORY CALIBRATION
==================================================

Use `name-calling` for loaded labels, insults, or emotionally charged identity labels assigned to a person, group, institution, or idea.

Human-aligned examples include short loaded labels or phrases like:

- `horrible papers`
- `fake news`
- `bigoted views`
- `radical extremists`

Use `demonization` only when the wording portrays the target as fundamentally evil, dangerous, corrupt, destructive, treasonous, disgusting, subhuman, or a serious threat.

Human-aligned examples include:

- `virtual act of treason`
- `complicity in the slaughter`
- language portraying a target as an existential danger or destructive force

Use `scapegoating` when a group or institution is blamed for a broad social, political, economic, or moral problem. The blame should be broad, not merely one factual criticism.

Human-aligned examples include:

- `the greed of the health insurance and pharmaceutical industries`
- blaming a whole group or institution as the cause of a broader problem

Use `exaggeration` for overstatement or understatement that makes something sound artificially bigger, worse, better, smaller, or less serious than the article supports.

Human-aligned examples include:

- `one of the most disgraceful performances`
- `tragic mistake`
- `low point in the history`
- `dysfunctional system`

Do not label ordinary strong factual descriptions as exaggeration if they are evidence-supported or simply descriptive.

Use `slogans` for short, memorable, mobilizing phrases.

Human-aligned examples include:

- `America has been made GREAT again`
- `Dump Trump`
- `recognize the BuzzFeed union`

Use `doubt` for language that directly undermines competence, honesty, credibility, trustworthiness, legitimacy, or reliability.

Human-aligned examples include:

- `Suppression Polls`
- `his many deceptions`
- `whose judgment no serious, intelligent person trusts`

Use `bandwagon` only when popularity, consensus, social pressure, or what "serious/intelligent/real" people believe is used as a reason to accept or reject something. Do not label neutral polling reports as bandwagon.

Use `casual oversimplification` only when the exact wording reduces a complex issue to one simple cause or explanation. Do not label ordinary causal reporting unless the simplification is explicit.

==================================================
COMMON FALSE POSITIVE GUARDS
==================================================

Do not annotate these unless additional selected words clearly create a polarizing cue:

- neutral descriptions of who criticized whom
- neutral summaries of investigations, hearings, lawsuits, protests, or campaign events
- factual polling numbers or search statistics
- ordinary policy disagreement
- descriptions of vandalism, crime, scandal, or outrage without loaded rhetorical wording
- neutral attribution before or after a quote

When deciding between a polarizing label and `No Polarizing language`, ask:

Does the exact selected text contain the rhetorical move, or am I relying on external context/topic?

If the answer is external context/topic, choose `No Polarizing language`.
