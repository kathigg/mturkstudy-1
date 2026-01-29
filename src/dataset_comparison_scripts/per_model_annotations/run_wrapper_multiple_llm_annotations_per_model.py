"""
Per-Model LLM Annotations (No Adjudication)

This script runs the same 3 annotators as `run_wrapper_multiple_llm_annotations.py`
(A=OpenAI, B=Gemini, C=OpenAI), but saves *all* model outputs without any
adjudication/committee consolidation.

Output format (JSON):
[
  {
    "title": ...,
    "topic": ...,
    "source": ...,
    "rating": ...,
    "annotator_A": { ... full annotation object ... },
    "annotator_B": { ... full annotation object ... },
    "annotator_C": { ... full annotation object ... }
  },
  ...
]

Paragraph handling:
- We apply the \"min-one\" paragraph policy to each annotator output so every
  paragraph has at least one annotation, while preserving multiple polarizing
  annotations per paragraph when they exist.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd
from tqdm.auto import tqdm

# When invoked as a script (python path/to/script.py), the repo root is not
# guaranteed to be on sys.path. Add it so we can import the shared base module.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

import src.dataset_comparison_scripts.run_wrapper_multiple_llm_annotations as base  # noqa: E402


# Apply minimum-one-per-paragraph to each model output, while keeping multiple
# annotations per paragraph when present.
PER_MODEL_PARAGRAPH_POLICY = "min-one"


def run_pipeline_per_model(
    df: pd.DataFrame,
    *,
    openai_model: str,
    gemini_model: str,
    temperature: float,
    max_retries: int,
    dry_run: bool,
) -> list[dict]:
    base._require_keys(unless_dry_run=dry_run)

    openai_client = None
    gemini_client = None
    if not dry_run:
        openai_client = base._openai_client()
        gemini_client = base._gemini_client()

    outputs: list[dict] = []

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Annotating (per-model)"):
        title, topic, source, rating, body, article_block = base.build_article_text(row.to_dict())

        if dry_run:
            obj_a, _ = base.annotate_dry_run(title, topic, source, rating, body)
            obj_b, _ = base.annotate_dry_run(title, topic, source, rating, body)
            obj_c, _ = base.annotate_dry_run(title, topic, source, rating, body)
        else:
            obj_a, _ = base.annotate_with_openai(
                openai_client,
                "You are Annotator A, a political communication scholar. Strictly follow the codebook and JSON schema. Be conservative: if unsure, choose No Polarizing language.",
                article_block,
                title,
                topic,
                source,
                rating,
                body=body,
                model=openai_model,
                temperature=temperature,
                max_retries=max_retries,
            )

            obj_b, _ = base.annotate_with_gemini(
                gemini_client,
                "You are Annotator B, a linguistics/discourse analyst. Your strength is correct subcategory selection. Be conservative: avoid over-labeling; if unsure, choose No Polarizing language.",
                article_block,
                title,
                topic,
                source,
                rating,
                body=body,
                model=gemini_model,
                max_retries=max_retries,
            )

            obj_c, _ = base.annotate_with_openai(
                openai_client,
                "You are Annotator C, a conservative/high-precision media psychology expert. Be conservative: only label when explicit; if unsure, choose No Polarizing language.",
                article_block,
                title,
                topic,
                source,
                rating,
                body=body,
                model=openai_model,
                temperature=temperature,
                max_retries=max_retries,
            )

        obj_a = base.apply_paragraph_policy(obj_a, body=body, paragraph_policy=PER_MODEL_PARAGRAPH_POLICY)
        obj_b = base.apply_paragraph_policy(obj_b, body=body, paragraph_policy=PER_MODEL_PARAGRAPH_POLICY)
        obj_c = base.apply_paragraph_policy(obj_c, body=body, paragraph_policy=PER_MODEL_PARAGRAPH_POLICY)

        # Validate after applying per-model paragraph policy.
        for name, obj in (("A", obj_a), ("B", obj_b), ("C", obj_c)):
            ok, err = base.validate_annotation(obj)
            if not ok:
                raise ValueError(f"Annotator {name} output failed schema validation after paragraph policy: {err}")

        outputs.append(
            {
                "title": title,
                "topic": topic,
                "source": source,
                "rating": rating,
                "annotator_A": obj_a,
                "annotator_B": obj_b,
                "annotator_C": obj_c,
            }
        )

    return outputs


def main(argv: list[str] | None = None) -> int:
    base._load_dotenv_if_present()

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="src/dataset_comparison_scripts/twelve_article_set.csv")
    parser.add_argument(
        "--per-model-json",
        default="src/llm_annotation_results/per_model_annotations/per_model_annotations_3models.json",
        help="Where to write the per-model (A/B/C) annotations JSON.",
    )
    parser.add_argument("--openai-model", default="gpt-5.1")
    parser.add_argument("--gemini-model", default="gemini-3-pro-preview")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true", help="No network calls; emits placeholder outputs.")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    df = pd.read_csv(input_path)
    outputs = run_pipeline_per_model(
        df,
        openai_model=args.openai_model,
        gemini_model=args.gemini_model,
        temperature=args.temperature,
        max_retries=args.max_retries,
        dry_run=args.dry_run,
    )

    out_path = Path(args.per_model_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(outputs, f, indent=2, ensure_ascii=False)

    print(f"Wrote per-model JSON: {out_path}")
    print(f"Per-model paragraph policy: {PER_MODEL_PARAGRAPH_POLICY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
