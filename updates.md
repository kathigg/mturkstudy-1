# Updates.md
Written by Kathleen Higgins, begun on January 8th (though I've been working on the project for a year and a half, now) to include recent updates so I can go back and check what I did. 

## January 28th, 12:31pm:
- Revised to have a second version of the original LLM and Turk aggregation scripts to support multiple annotations. Reorganization for simplification still needed of the codebase. 

## January 25th, latest two runs (1-8 HIT vs. in-house, same 12 articles):
- Both runs enforce one annotation per paragraph, so precision == recall at the article-match level.
- 1-8 HIT (MTurk):
```
Confidence weighting enabled: True
Article Match: {'precision': 0.579, 'recall': 0.579, 'f1': 0.579, 'correct_matches': 22, 'total_llm': 38, 'total_gold': 38}
Category Match: {'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'correct_matches': 22, 'total_matches': 22}
Weighted Article Match: {'precision': 0.428, 'recall': 0.553, 'f1': 0.483, 'tp_weight': 11.98, 'total_gold_weight': 21.65, 'fp': 16}
```
- In-house (same twelve articles):
```
[12:26 PM]=== Overall Results ===Confidence weighting enabled: TrueArticle Match: {'precision': 0.842, 'recall': 0.842, 'f1': 0.842, 'correct_matches': 32, 'total_llm': 38, 'total_gold': 38}Category Match: {'precision': 0.969, 'recall': 0.969, 'f1': 0.969, 'correct_matches': 31, 'total_matches': 32}Weighted Article Match: {'precision': 0.807, 'recall': 0.867, 'f1': 0.836, 'tp_weight': 25.1, 'total_gold_weight': 28.95, 'fp': 6} (edited) [12:27 PM]
```
- Bottom line: article-match F1 is 0.579 (MTurk) vs. 0.842 (in-house), a +0.263 absolute difference (~26.3 percentage points).

## January 25th, 9:54am:
```
Category Info: compared the latest in‑house annotations to the LLM output using one annotation per paragraph, yielding 38 annotations each. There were 32/38 matches. Of those matches, 31/32 were “no polarizing language.” The single non‑no‑polarizing match was a category disagreement: in‑house labeled it “inflammatory language,” while the LLM labeled it “persuasive propaganda.”For the 6 mismatches, the disagreement types were evenly split:2/6 (33.33%): LLM marked “no polarizing,” in‑house marked polarizing.2/6 (33.33%): LLM marked polarizing, in‑house marked “no polarizing.”2/6 (33.33%): both marked polarizing, but chose different snippets/categories within the paragraph.The category match rate for inflammatory language and persuasive propaganda is 0%, since the only annotation not for "no polarizing language" the in-house and LLM disagreed on category. In summary, most all matches come from shared judgments that the paragraph contains no polarizing language. the remaining disagreements are evenly distributed across the three mismatch types. (edited) Kathleen Higgins  [9:15 AM]Let me know what more data and questions you have. Essentially, because 86.84% of total annotations are for no polarizing language, it's basically become a binary yes/no for no polarizing language task.Kathleen Higgins  [9:22 AM]The dominance of no polarizing language annotations for both humans and LLMs also is a result of the current data processing that emphasizes conservatism. The LLM prompting emphasizes carefulness ("if unsure, choose no polarizing language") and the current aggregation of the human annotations requires 2/3 annotators to agree for the annotation to be saved---which cuts out the junk of random poor annotations, but will save the annotation as "no polarizing language" if that 2/3 standard isn't met---reducing the variance of the human annotations.[9:22 AM]Additionally, currently a one-annotation-per-paragraph rule is being enforced.Kathleen Higgins  [9:47 AM]It's also hard to over emphasize how much of an impact data processing has on the final scores. Here is a diagram of the current data processing. The current structure emphasizes agreement and conservatism. If there's an interest in seeing scores with no enforcement of one annotation per paragraph or 2/3 Turker agreement, I can rewrite the processing scripts.
```

## January 23rd, 12:30pm:
- Bro.
```
[12:26 PM]=== Overall Results ===Confidence weighting enabled: TrueArticle Match: {'precision': 0.842, 'recall': 0.842, 'f1': 0.842, 'correct_matches': 32, 'total_llm': 38, 'total_gold': 38}Category Match: {'precision': 0.969, 'recall': 0.969, 'f1': 0.969, 'correct_matches': 31, 'total_matches': 32}Weighted Article Match: {'precision': 0.807, 'recall': 0.867, 'f1': 0.836, 'tp_weight': 25.1, 'total_gold_weight': 28.95, 'fp': 6} (edited) [12:27 PM]
```
- Em so I suppose we have our answer. Literally a >20 percentage point difference between the Turkers (57.9% agreement with LLM) and our in-house annotations (84.2% agreement with our LLM). 
- So this is good, in terms of it confirming my hypothesis, but it does mean that we'll have to take this into account into how we restructure the project.

## January 17th, 4:17pm:
- I kept mixing up which JSON files were right and which ones were out of date, so I 

## January 13th, 11:54pm:
To-Do List (post-meeting):
- Send JSON file for the interns to annotate. 
- Send JSON to Varun of the finished LLM annotations. 

***To-Do List***
## January 8th, 8:00pm:
- Realized I was doing something mad stupid, and I didn't update the comparison script to work with the per-paragraph LLM json. 
```
Confidence weighting enabled: True
Article Match: {'precision': 0.579, 'recall': 0.579, 'f1': 0.579, 'correct_matches': 22, 'total_llm': 38, 'total_gold': 38}
Category Match: {'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'correct_matches': 22, 'total_matches': 22}
Weighted Article Match: {'precision': 0.428, 'recall': 0.553, 'f1': 0.483, 'tp_weight': 11.98, 'total_gold_weight': 21.65, 'fp': 16}
```

## January 8th, 5:31pm:
- Added the first bit of data from the most recent HIT. 
