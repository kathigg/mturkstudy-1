#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

PYTHON="${PYTHON:-.venv/bin/python}"
INPUT="public/article_dataset_versions/test3_encoding_fixed_300_700_words_paragraphs.csv"
GOLD="src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/consolidated_bagozzi_inhouse_overlap_gold_with_conservative_npl_paragraph_spans.json"

RESULT_ROOT="src/llm_annotation_results/full_551/decision_point_adjudication_v1"
ANALYSIS_ROOT="src/dataset_comparison_scripts/statistical_analysis/full_551/decision_point_adjudication_v1"
NPL_ROOT="src/llm_annotation_results/full_551/npl_prompt_comparison"
NPL_ANALYSIS_ROOT="src/dataset_comparison_scripts/statistical_analysis/full_551/npl_prompt_comparison"
PROMPT_DIR="src/dataset_comparison_scripts/prompt_versions/npl_prompt_comparison"

run_with_retries() {
  local attempts="$1"
  shift
  local attempt=1
  while true; do
    echo "[full-551] attempt ${attempt}/${attempts}: $*"
    if "$@"; then
      return 0
    fi
    if [ "$attempt" -ge "$attempts" ]; then
      return 1
    fi
    sleep $((attempt * 30))
    attempt=$((attempt + 1))
  done
}

COMMON_SINGLE_ARGS=(
  --input "$INPUT"
  --gold-json "$GOLD"
  --temperature 0
  --max-retries 4
  --request-timeout-s 300
  --resume
  --no-previous-adjudicated
)

run_with_retries 8 "$PYTHON" src/dataset_comparison_scripts/run_bagozzi_intersection_single_models.py \
  "${COMMON_SINGLE_ARGS[@]}" \
  --prompt-file "$PROMPT_DIR/prompt_5_human_aligned_precision_recall.md" \
  --output-root "$NPL_ROOT/prompt_5_human_aligned_precision_recall_single_models" \
  --analysis-root "$NPL_ANALYSIS_ROOT/prompt_5_human_aligned_precision_recall_single_models"

run_with_retries 8 "$PYTHON" src/dataset_comparison_scripts/run_bagozzi_intersection_single_models.py \
  "${COMMON_SINGLE_ARGS[@]}" \
  --providers openai \
  --prompt-file "$PROMPT_DIR/prompt_4_boundary_examples_precision.md" \
  --output-root "$NPL_ROOT/prompt_4_boundary_examples_precision_single_models" \
  --analysis-root "$NPL_ANALYSIS_ROOT/prompt_4_boundary_examples_precision_single_models"

run_with_retries 8 "$PYTHON" src/dataset_comparison_scripts/run_bagozzi_inhouse_prompt_sweep.py \
  --input "$INPUT" \
  --prompt-dir "$PROMPT_DIR" \
  --output-root "$NPL_ROOT/adjudication_prompt_1_to_5" \
  --analysis-root "$NPL_ANALYSIS_ROOT/adjudication_prompt_1_to_5" \
  --gold-json "$GOLD" \
  --prompt-version prompt_2_dr_bagozzi \
  --temperatures 0 \
  --max-retries 4 \
  --checkpoint-every 1 \
  --wrapper-attempts 5 \
  --resume

run_with_retries 8 "$PYTHON" src/dataset_comparison_scripts/run_bagozzi_inhouse_prompt_sweep.py \
  --input "$INPUT" \
  --prompt-dir "$PROMPT_DIR" \
  --output-root "$NPL_ROOT/adjudication_prompt_1_to_5" \
  --analysis-root "$NPL_ANALYSIS_ROOT/adjudication_prompt_1_to_5" \
  --gold-json "$GOLD" \
  --prompt-version prompt_4_boundary_examples_precision \
  --temperatures 0 \
  --max-retries 4 \
  --checkpoint-every 1 \
  --wrapper-attempts 5 \
  --resume

run_with_retries 3 "$PYTHON" src/dataset_comparison_scripts/run_decision_point_adjudication.py \
  --input "$INPUT" \
  --gold-json "$GOLD" \
  --output-root "$RESULT_ROOT" \
  --analysis-root "$ANALYSIS_ROOT" \
  --fixed-threshold \
  --threshold 0.5 \
  --candidate-source "gpt5mini_prompt5=$NPL_ROOT/prompt_5_human_aligned_precision_recall_single_models/openai_gpt_5_mini/final_annotations.json:1.1" \
  --candidate-source "gemini_flash_prompt5=$NPL_ROOT/prompt_5_human_aligned_precision_recall_single_models/gemini_gemini_3_1_flash_lite/final_annotations.json:1.0" \
  --candidate-source "claude_haiku_prompt5=$NPL_ROOT/prompt_5_human_aligned_precision_recall_single_models/claude_claude_haiku_4_5/final_annotations.json:0.7" \
  --candidate-source "adjudicated_prompt2=$NPL_ROOT/adjudication_prompt_1_to_5/prompt_2_dr_bagozzi_temp0p0_run1/final_annotations.json:1.1" \
  --label-source "gpt5mini_prompt4_labeler=$NPL_ROOT/prompt_4_boundary_examples_precision_single_models/openai_gpt_5_mini/final_annotations.json:1.2" \
  --label-source "adjudicated_prompt4_labeler=$NPL_ROOT/adjudication_prompt_1_to_5/prompt_4_boundary_examples_precision_temp0p0_run1/final_annotations.json:1.2" \
  --resume
