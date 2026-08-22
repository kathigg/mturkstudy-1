Prompt V3: high-precision adjudicated target

Optimize for agreement with a final adjudicated human/expert gold set.

Selection threshold:
- A valid polarizing span should be specific, quotable, and independently recognizable as persuasive propaganda or inflammatory language.
- Avoid broad context windows. Do not select a full sentence if a shorter phrase contains the actual polarizing wording.
- Prefer missing a weak span over adding a questionable span.

Subcategory boundaries:
- Exaggeration: use only for inflated intensity, scale, certainty, or moral stakes. Do not use for ordinary strong disagreement.
- Doubt: use only when wording actively undermines trust or credibility without direct evidence.
- Casual oversimplification: use only when a complex issue is reduced to a misleadingly simple cause, fix, or blame claim.
- Bandwagon: use only when the span appeals to popularity, collective demand, or social pressure.
- Slogans: use only for compact repeated campaign-like or rally-like language.
- Name-calling: use for loaded labels aimed at a person, institution, or group.
- Demonization: use for portraying a target as dangerous, corrupt, evil, predatory, or a threat.
- Scapegoating: use only when a group is blamed for a broader social problem.

Adjudication preference:
- Keep a span only if at least two careful human annotators would likely agree that the exact selected words are problematic.
- If the model is uncertain about the span boundary or subcategory, output No Polarizing language for that paragraph.
