# Updates.md
Written by Kathleen Higgins, begun on January 8th (though I've been working on the project for a year and a half, now) to include recent updates so I can go back and check what I did. 

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