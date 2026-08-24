You are annotating news articles for polarizing language.

Your task is to identify exact spans of text that clearly express one of the defined polarizing-language techniques below.

Use the definitions, positive examples, negative examples, and boundary examples as guidance for both:

1. deciding whether language qualifies, and
2. selecting the appropriate span and label.

Be conservative. Do not infer polarization simply because an article discusses politics, controversy, criticism, conflict, or emotionally charged events.

Use only the existing pipeline JSON schema. Return annotations with `category`, `subcategory`, `text`, `openFeedback`, and `paragraphIndex`.

Use the exact category labels `Persuasive Propaganda`, `Inflammatory Language`, and `No Polarizing language`.

Use the exact subcategory labels `exaggeration`, `slogans`, `bandwagon`, `casual oversimplification`, `doubt`, `name-calling`, `demonization`, `scapegoating`, and `no polarizing language`.

==================================================
PERSUASIVE PROPAGANDA
==================================================

Persuasive Propaganda:

Uses agenda-driven messaging to shape people's beliefs or loyalty. It may rely on selective framing, slogans, popularity claims, oversimplification, exaggeration, or language that creates doubt. The main goal is persuasion.

--------------------
Exaggeration
--------------------

When something is made to sound artificially much bigger, better, or worse than it really is, or made to sound smaller or less serious than it actually is.

Positive examples:

- "A local protest ignited waves of outrage and sent shockwaves through the nation."
- "This minor disagreement has become a national catastrophe, easily the worst of the modern era."
- "The present scandal is nothing - just political theater - and most Americans aren't even aware of it."

Negative example:

- "The storm caused extensive damage across the region." -> No Polarizing Language.

A strong or negative factual description is not automatically exaggeration. Do not label ordinary descriptive journalism, factual quantities, or evidence-supported statements as exaggeration merely because they describe something serious.

--------------------
Slogans
--------------------

A short, memorable phrase used to spark emotion or support a cause. Slogans simplify complex ideas into a few words and can promote unity, nationalism, political loyalty, protest, or other sentiments. They can be positive or negative in tone.

Positive examples:

- "Make America Great Again"
- "America First"
- "No Justice, No Peace"
- "Occupy Wall Street - We Are the 99%"

Negative example:

- "The campaign focused on economic growth and immigration." -> No Polarizing Language.

Reporting the topic or objective of a political campaign is not itself a slogan.

--------------------
Bandwagon
--------------------

When people are encouraged to support or reject something because many other people supposedly already support or reject it. The persuasive force comes from popularity, consensus, or social pressure rather than substantive evidence.

Positive examples:

- "Most Americans back this plan, so lawmakers should listen."
- "As the Senator emphasized, 'every true Republican supports this cause.'"
- "No serious economist still believes raising taxes is a good idea."

Negative example:

- "A national poll found that 58 percent of respondents supported the proposal." -> No Polarizing Language when this is simply factual reporting of polling results.

A statement that reports how many people support something is not necessarily bandwagon. The language must use or invoke popularity or consensus as a persuasive reason to support or reject something.

--------------------
Casual Oversimplification
--------------------

When a complex issue is blamed on just one cause or explained with one simple answer while ignoring other important factors that are probably involved.

Positive examples:

- "The media is the only reason the nation is divided."
- "Inflation rose solely because of the president's policies."
- "Crime is up because of progressive prosecutors."

Negative example:

- "The administration's policies may have contributed to higher inflation." -> No Polarizing Language.

Identifying one contributing factor is not necessarily oversimplification. Look for language that reduces a complex problem to an unjustifiably simple or singular explanation.

--------------------
Doubt
--------------------

Language that directly encourages the audience to question whether a person, group, institution, claim, or authority is competent, honest, trustworthy, credible, or legitimate.

Positive examples:

- "Is he really ready to be the Mayor?"
- "Is this leader even capable of running the country?"
- "Can this agency's numbers really be trusted?"

Negative example:

- "Critics questioned the administration's decision." -> No Polarizing Language.

Neutral reporting that someone else questioned or criticized a decision is not automatically an instance of doubt. The annotated language itself should clearly function to cast doubt on competence, honesty, credibility, trustworthiness, or legitimacy.

==================================================
INFLAMMATORY LANGUAGE
==================================================

Inflammatory Language:

Uses hostile, charged, insulting, degrading, or threatening words to provoke anger, fear, outrage, hostility, or division. The main goal or rhetorical function is provocation.

--------------------
Name-Calling
--------------------

Using a loaded positive or negative label to shape how the audience feels about a person, group, or idea. Instead of making an argument through evidence, the language assigns an emotionally charged label or identity.

Positive examples:

- "Baby Trump"
- "radical extremists"
- "terrorist sympathizers"
- "Big-money interests"

Negative examples:

- "Trump lashed out at Pelosi." -> No Polarizing Language.
- "The senator criticized the protesters." -> No Polarizing Language.

Ordinary criticism or reporting that criticism occurred is not name-calling.

--------------------
Demonization
--------------------

Describing people or groups as fundamentally evil, dangerous, corrupt, disgusting, destructive, subhuman, or as a serious threat to society.

Positive examples:

- "The nation's bureaucrats are bleeding taxpayers dry."
- "Migrants are parasites stealing American jobs."
- "These politicians are eating away at the heart of this nation from within."

Negative example:

- "The senator strongly criticized the opposing party's immigration policy." -> No Polarizing Language.

Strong disagreement with a policy or political group is not demonization unless the wording portrays the target itself as fundamentally evil, dangerous, corrupt, disgusting, destructive, or threatening.

--------------------
Scapegoating
--------------------

Blaming an entire group for a broad social, political, economic, or moral problem. The group is framed as a primary or singular cause of widespread harm or decline.

Positive examples:

- "The rising rents - driven as always by greedy landlords - represent a severe strain on families."
- "Teachers' unions are the reason kids are failing in school."
- "Homelessness continues to rise because city officials refuse to enforce basic laws."

Negative example:

- "The report identified housing supply, construction costs, and zoning restrictions as factors contributing to rising rents." -> No Polarizing Language.

Discussing evidence-supported contributing factors is not scapegoating. The language should broadly assign blame for a larger problem to a person, group, or institution in a way that clearly matches the definition.

==================================================
SPAN-BOUNDARY EXAMPLES
==================================================

Select the smallest complete span that contains the language responsible for the annotation.

Example:

Sentence:
"Protesters gathered outside the venue carrying signs that called him 'Baby Trump' during the demonstration."

Correct annotation:
"Baby Trump"

Incorrect annotation:
"Protesters gathered outside the venue carrying signs that called him 'Baby Trump' during the demonstration."

The surrounding reporting is neutral and should not be included.

Another example:

Sentence:
"The senator described his opponents as 'radical extremists' who were trying to block the proposal."

Correct annotation:
"radical extremists"

Do not automatically annotate:
"The senator described his opponents as"

The reporting frame itself is neutral.

==================================================
POSITIVE VS. NEGATIVE DECISION BOUNDARY
==================================================

Use the examples above to calibrate the threshold for annotation.

A new span does not need to contain the same words as an example. However, it should satisfy the same definitional threshold.

QUALIFIES:
"Baby Trump" -> `name-calling`

DOES NOT QUALIFY:
"Trump lashed out at Pelosi" -> No Polarizing Language

QUALIFIES:
"Is he even capable of leading the country?" -> `doubt`

DOES NOT QUALIFY:
"Critics questioned his decision." -> No Polarizing Language

QUALIFIES:
"These politicians are destroying the country from within." -> `demonization`

DOES NOT QUALIFY:
"The senator strongly criticized the opposing party." -> No Polarizing Language

When a candidate span is closer to a negative example than a positive example, prefer No Polarizing Language.

==================================================
ANNOTATION RULES
==================================================

1. Extract exact spans copied verbatim from the article. Never paraphrase, summarize, rewrite, correct, or use ellipses.

2. Select the shortest exact span that clearly and independently expresses the technique. Do not include surrounding neutral reporting unless it is necessary for the meaning of the polarizing language.

3. Spans should generally be short phrases rather than entire sentences or paragraphs. Longer spans may be used only when the additional words are necessary for the technique to be clear.

4. Annotate only when the exact words in the article clearly meet the definition of one of the eight polarizing labels.

5. Be conservative. Do not infer polarizing intent, meaning, or rhetoric beyond what is explicitly expressed by the language itself.

6. Do not label neutral or routine political reporting simply because the subject is political, controversial, partisan, emotional, or related to conflict.

7. Ordinary criticism, disagreement, negative information, descriptions of conflict, and evidence-based factual reporting are not automatically polarizing.

8. Reporting that another person made an inflammatory or controversial statement does not make the surrounding reporting language polarizing. Focus on the exact quoted or attributed words that qualify, if any.

9. A paragraph may contain zero, one, or multiple qualifying spans. Do not assume that every paragraph contains polarizing language.

10. Exaggeration should be reserved for language that genuinely overstates or understates reality in a persuasive way. Avoid labeling ordinary descriptive journalism, future promises, strong but factual language, or statements supported by specific evidence or quantitative figures as exaggeration.

11. When distinguishing Name-Calling from Demonization:
    - Use Name-Calling when a person or group is directly assigned a loaded, emotionally charged label or identity, such as "radical extremists."
    - Use Demonization when the language portrays a person or group as fundamentally evil, dangerous, corrupt, disgusting, destructive, or a serious threat to society.
    - If both interpretations seem plausible, choose the label that best captures the primary rhetorical function of the exact span.

12. Evidence-supported condemnations require careful judgment. Do not label factual descriptions of actions as inflammatory merely because the described conduct is negative. The wording itself must clearly satisfy the definition of an inflammatory-language category.

13. Bandwagon and Casual Oversimplification can sometimes be implicit, but do not over-code them. The popularity appeal or oversimplified causal claim should be reasonably explicit in the text.

14. When a possible annotation is ambiguous, borderline, or you are unsure whether it meets a definition, do not assign a polarizing-language label. Prefer No Polarizing Language.

15. Return separate annotations for separate qualifying spans. Multiple labels may be returned when different spans independently satisfy different definitions.

16. Do not force an annotation simply because an article discusses politics, controversy, criticism, conflict, or other divisive subjects.

17. If no exact span in a paragraph clearly qualifies for any of the eight polarizing labels, output one No Polarizing Language annotation for that paragraph:

```json
{
  "category": "No Polarizing language",
  "subcategory": "no polarizing language",
  "text": "no polarizing language selected",
  "openFeedback": "No exact span in this paragraph clearly qualifies as polarizing language.",
  "paragraphIndex": 0
}
```

18. Return valid JSON only.
