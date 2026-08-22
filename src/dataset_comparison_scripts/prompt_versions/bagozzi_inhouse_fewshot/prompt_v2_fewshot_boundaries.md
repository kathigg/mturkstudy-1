Prompt V2: few-shot boundaries

Use these examples to calibrate span selection.

Positive examples:
- "Amazon crushes small companies" -> Inflammatory Language / demonization
- "Recognize the BuzzFeed Union!!" -> Persuasive Propaganda / slogans
- "Baby Trump" -> Inflammatory Language / name-calling
- "skyrocketing health insurance costs" -> Persuasive Propaganda / exaggeration
- "private corporations to make billions of dollars in profits off Americans' health care" -> Persuasive Propaganda / exaggeration
- "some low-life" -> Inflammatory Language / name-calling

Negative examples:
- "Trump lashed out at Pelosi" is not enough by itself; it reports an action.
- "they have got to talk to the needs of the working class" is not enough by itself; it is ordinary political framing unless paired with stronger persuasive pressure.
- "she'd rather see him voted out of office and in prison" should not be marked unless the exact selected wording is being used as inflammatory language in context.
- "what may be incalculable damage" should not be marked unless the paragraph uses it as explicit exaggeration rather than reporting a speaker's claim.

Decision rule:
- If a candidate span resembles a negative example more than a positive example, do not annotate it.
- If only part of a sentence is polarizing, select only the polarizing phrase.

