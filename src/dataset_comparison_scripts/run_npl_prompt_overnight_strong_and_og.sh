#!/usr/bin/env bash
set +e
set -u -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 1

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
PROMPT_DIR="src/dataset_comparison_scripts/prompt_versions/npl_prompt_comparison"
INPUT_CSV="src/dataset_comparison_scripts/2-20/2-20_selected_articles.csv"
GOLD_JSON="src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/consolidated_bagozzi_inhouse_overlap_gold_with_conservative_npl_paragraph_spans.json"

STRONG_OUTPUT_BASE="src/llm_annotation_results/2-20/npl_prompt_comparison"
STRONG_ANALYSIS_BASE="src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/npl_prompt_comparison"
OG_OUTPUT_ROOT="src/llm_annotation_results/2-20/npl_prompt_comparison/adjudication_prompt_1_to_5"
OG_ANALYSIS_ROOT="src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/npl_prompt_comparison/adjudication_prompt_1_to_5"

STRONG_ATTEMPTS="${STRONG_ATTEMPTS:-3}"
OG_ATTEMPTS="${OG_ATTEMPTS:-2}"
SLEEP_BETWEEN_ATTEMPTS="${SLEEP_BETWEEN_ATTEMPTS:-60}"

OPENAI_MODEL="${OPENAI_MODEL:-gpt-5.1}"
OPENAI_LABEL="${OPENAI_LABEL:-GPT-5.1}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.1-pro-preview}"
GEMINI_LABEL="${GEMINI_LABEL:-Gemini 3.1 Pro Preview}"
CLAUDE_MODEL="${CLAUDE_MODEL:-claude-sonnet-5}"
CLAUDE_LABEL="${CLAUDE_LABEL:-Claude Sonnet 5}"
CLAUDE_ADJUDICATOR_MODEL="${CLAUDE_ADJUDICATOR_MODEL:-claude-opus-4-8}"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

check_strong_complete() {
  local output_root="$1"
  "$PYTHON_BIN" - "$output_root" "$OPENAI_MODEL" "$GEMINI_MODEL" "$CLAUDE_MODEL" <<'PY'
import csv
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
openai_model, gemini_model, claude_model = sys.argv[2:]

def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")

run_ids = [
    f"openai_{slug(openai_model)}",
    f"gemini_{slug(gemini_model)}",
    f"claude_{slug(claude_model)}",
]
ok = True
for run_id in run_ids:
    raw = root / run_id / "raw_results.csv"
    meta = root / run_id / "metadata.json"
    rows = 0
    if raw.exists():
        rows = sum(1 for _ in csv.DictReader(raw.open(encoding="utf-8")))
    status = None
    if meta.exists():
        status = json.load(meta.open(encoding="utf-8")).get("status")
    print(f"  {run_id}: rows={rows}/27 status={status}")
    if rows != 27 or status != "complete":
        ok = False
sys.exit(0 if ok else 1)
PY
}

check_og_complete() {
  "$PYTHON_BIN" - "$OG_OUTPUT_ROOT" "$PROMPT_DIR" <<'PY'
import csv
import sys
from pathlib import Path

output_root = Path(sys.argv[1])
prompt_dir = Path(sys.argv[2])
ok = True
for prompt_file in sorted(prompt_dir.glob("prompt_*.md")):
    run_id = f"{prompt_file.stem}_temp0p0_run1"
    raw = output_root / run_id / "raw_results.csv"
    final_json = output_root / run_id / "final_annotations.json"
    rows = 0
    if raw.exists():
        rows = sum(1 for _ in csv.DictReader(raw.open(encoding="utf-8")))
    print(f"  {run_id}: rows={rows}/27 final={final_json.exists()}")
    if rows != 27 or not final_json.exists():
        ok = False
sys.exit(0 if ok else 1)
PY
}

echo "[$(timestamp)] Starting overnight NPL prompt runs"
echo "[$(timestamp)] Repo: $REPO_ROOT"
echo "[$(timestamp)] Prompt dir: $PROMPT_DIR"
echo "[$(timestamp)] Gold: $GOLD_JSON"

for prompt_file in "$PROMPT_DIR"/prompt_*.md; do
  prompt_stem="$(basename "$prompt_file" .md)"
  output_root="$STRONG_OUTPUT_BASE/${prompt_stem}_strong_single_models"
  analysis_root="$STRONG_ANALYSIS_BASE/${prompt_stem}_strong_single_models"
  mkdir -p "$output_root" "$analysis_root"

  echo "[$(timestamp)] Strong single-model prompt: $prompt_stem"
  for attempt in $(seq 1 "$STRONG_ATTEMPTS"); do
    echo "[$(timestamp)] Strong attempt $attempt/$STRONG_ATTEMPTS for $prompt_stem"
    "$PYTHON_BIN" src/dataset_comparison_scripts/run_bagozzi_intersection_single_models.py \
      --providers openai,gemini,claude \
      --prompt-file "$prompt_file" \
      --gold-json "$GOLD_JSON" \
      --output-root "$output_root" \
      --analysis-root "$analysis_root" \
      --openai-model "$OPENAI_MODEL" \
      --openai-label "$OPENAI_LABEL" \
      --gemini-model "$GEMINI_MODEL" \
      --gemini-label "$GEMINI_LABEL" \
      --claude-model "$CLAUDE_MODEL" \
      --claude-label "$CLAUDE_LABEL" \
      --temperature 0 \
      --max-retries 8 \
      --request-timeout-s 240 \
      --resume
    strong_rc=$?
    echo "[$(timestamp)] Strong command exit code for $prompt_stem attempt $attempt: $strong_rc"

    if check_strong_complete "$output_root"; then
      echo "[$(timestamp)] Strong complete for $prompt_stem"
      break
    fi

    echo "[$(timestamp)] Strong incomplete for $prompt_stem; sleeping ${SLEEP_BETWEEN_ATTEMPTS}s before resume"
    sleep "$SLEEP_BETWEEN_ATTEMPTS"
  done
done

echo "[$(timestamp)] OG adjudication all prompts"
for attempt in $(seq 1 "$OG_ATTEMPTS"); do
  echo "[$(timestamp)] OG adjudication attempt $attempt/$OG_ATTEMPTS"
  "$PYTHON_BIN" src/dataset_comparison_scripts/run_bagozzi_inhouse_prompt_sweep.py \
    --input "$INPUT_CSV" \
    --prompt-dir "$PROMPT_DIR" \
    --output-root "$OG_OUTPUT_ROOT" \
    --analysis-root "$OG_ANALYSIS_ROOT" \
    --gold-json "$GOLD_JSON" \
    --openai-model "$OPENAI_MODEL" \
    --gemini-model "$GEMINI_MODEL" \
    --claude-model "$CLAUDE_MODEL" \
    --annotator-c-provider anthropic \
    --adjudicator-provider anthropic \
    --claude-adjudicator-model "$CLAUDE_ADJUDICATOR_MODEL" \
    --temperatures 0 \
    --resume \
    --checkpoint-every 1 \
    --max-retries 8 \
    --wrapper-attempts 10
  og_rc=$?
  echo "[$(timestamp)] OG adjudication command exit code attempt $attempt: $og_rc"

  if check_og_complete; then
    echo "[$(timestamp)] OG adjudication complete"
    break
  fi

  echo "[$(timestamp)] OG adjudication incomplete; sleeping ${SLEEP_BETWEEN_ATTEMPTS}s before resume"
  sleep "$SLEEP_BETWEEN_ATTEMPTS"
done

echo "[$(timestamp)] Overnight NPL prompt runs finished"
