# Updates.md
Written by Kathleen Higgins, begun on January 8th (though I've been working on the project for a year and a half, now) to include recent updates so I can go back and check what I did. 

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