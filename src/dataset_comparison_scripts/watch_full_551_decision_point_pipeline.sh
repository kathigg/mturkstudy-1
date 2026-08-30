#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

PYTHON="${PYTHON:-.venv/bin/python}"
PIPELINE="src/dataset_comparison_scripts/run_full_551_decision_point_pipeline.sh"
FINAL_JSON="src/llm_annotation_results/full_551/decision_point_adjudication_v1/final_annotations.json"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

ts() {
  date '+%Y-%m-%d %H:%M:%S %Z'
}

json_count() {
  local path="$1"
  if [ ! -f "$path" ]; then
    echo 0
    return 0
  fi
  "$PYTHON" -c 'import json,sys; print(len(json.load(open(sys.argv[1], encoding="utf-8"))))' "$path" 2>/dev/null || echo 0
}

pipeline_running() {
  pgrep -f "run_full_551_decision_point_pipeline\\.sh" >/dev/null 2>&1
}

while true; do
  count="$(json_count "$FINAL_JSON")"
  if [ "$count" -ge 551 ]; then
    echo "[$(ts)] final decision-point output is complete: $count/551"
    exit 0
  fi

  if pipeline_running; then
    echo "[$(ts)] pipeline already running; final output $count/551"
  else
    run_log="$LOG_DIR/full_551_decision_point_watchdog_run_$(date '+%Y%m%d_%H%M%S').log"
    echo "[$(ts)] pipeline not running; restarting with resume -> $run_log"
    bash -x "$PIPELINE" >> "$run_log" 2>&1 &
  fi

  sleep 300
done
