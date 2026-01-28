"""
Wrapper script for the multi-LLM annotation pipeline.

This preserves the original behavior in `run_wrapper_multiple_llm_annotations.py` while providing
a convenient entrypoint that defaults to a flexible paragraph policy:
  - Keep all polarizing annotations per paragraph (if any)
  - Otherwise, keep exactly one "No Polarizing language" placeholder
  - Always ensure at least one annotation per paragraph

Equivalent to running:
  python src/dataset_comparison_scripts/run_wrapper_multiple_llm_annotations.py --paragraph-policy min-one
"""

from __future__ import annotations

import sys

from run_wrapper_multiple_llm_annotations import main


def _inject_defaults(argv: list[str]) -> list[str]:
    out = list(argv)
    if "--paragraph-policy" not in out:
        out += ["--paragraph-policy", "min-one"]
    if "--final-json" not in out:
        out += ["--final-json", "src/llm_annotation_results/multi_llm_annotations/multi_final_annotations_3annotators.json"]
    if "--results-csv" not in out:
        out += ["--results-csv", "src/dataset_comparison_scripts/annotated_results_3annotators_multi.csv"]
    return out


if __name__ == "__main__":
    raise SystemExit(main(_inject_defaults(sys.argv[1:])))
