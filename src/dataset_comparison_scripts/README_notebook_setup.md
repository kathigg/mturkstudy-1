## Running `Multiple_LLM_Annotations_Script.ipynb` locally

### 1) Create a Python environment

From the repo root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install jupyterlab
python -m pip install -r src/dataset_comparison_scripts/requirements_llm_notebook.txt
```

### 2) Set API keys

The notebook reads keys from environment variables. Recommended: put them in a repo-root `.env`
(this repo ignores `.env` via `.gitignore`).

```bash
cp .env.example .env
# edit .env and set:
# OPENAI_API_KEY=...
# GEMINI_API_KEY=...
```

### 3) Ensure the input CSV exists

This repo includes `src/dataset_comparison_scripts/twelve_article_set.csv` (the 12 articles currently used by the tool, with literal `\\n` paragraph breaks in the `News body` field).

### 4) Start Jupyter from the repo root

```bash
jupyter lab
```

Then open `src/dataset_comparison_scripts/Multiple_LLM_Annotations_Script.ipynb` and run cells top-to-bottom.
