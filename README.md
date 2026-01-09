# Sensify Lab: Community Comms Project, MTurk Survey Tool

**Principal Developer:** Kathleen Higgins (Summer 2025)
**Principal Investigator:** Prerana Khatiwada (PhD) and Professor Matthew Mauriello

This project is divided into several sections. 

Table of Contents: 
- News Annotation Platform
- Annotation Aggregation Scripts 
- LLM Scripts
- LLM vs Turker Comparison Process 


# News Annotation Platform 

This is a browser-based annotation platform for labeling persuasive propaganda, inflammatory language, and misleading content in news articles. Designed for MTurk and human-subject studies.

## Location: 
/mturkstudy/src/website_management

## Features

- Highlight text and apply structured labels
- Customizable categories and survey questions
- Supports article-by-article surveys
- JSON export or Firebase integration
- “Thank You” screen with MTurk code

## Customization via `config.js`

To adapt the tool for your own study, edit `config.js`:

- `articles`: your article text and titles
- `categoryOptions`: tags available to annotators
- `surveyQuestions`: Likert-style post-annotation questions

## Getting Started

1. Clone this repo
2. Run `npm install`
3. Update `config.js`
4. Run locally: `npm start`
5. Optionally deploy on Vercel, Netlify, or Firebase

## Example Output

At the end of the task, all annotations and survey responses are saved as structured JSON and can optionally be uploaded to Firebase.

## Designed For Research

This tool was created for a human-subject study but is reusable across research domains involving:
- Misinformation
- Bias detection
- Media literacy

## License

MIT License

# Annotation Aggregation Scripts 

## Location: 
/mturkstudy/src/gold_standard_dataset

## About:
Contains code that aggregates the work of different annotators into a single dataset that contains confidence scores that can be compared to LLMs. 
