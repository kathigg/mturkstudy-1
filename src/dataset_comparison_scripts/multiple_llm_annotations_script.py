"""
Multiple LLM Annotations Script (Python CLI)

Canonical, runnable script. See:
`src/dataset_comparison_scripts/multiple_llm_annotations_script(1).py`
for the actual implementation.
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> int:
    script = Path(__file__).with_name("run_wrapper_multiple_llm_annotations.py")
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
