"""
Multiple LLM Annotations Script (Python CLI)

This is a cleaned, runnable version of the Colab notebook export.
It:
  - Reads a CSV of articles (Headline, News body, Topic, News Source, Rating)
  - Runs 3 annotators (OpenAI A, Gemini B, OpenAI C) + an OpenAI adjudicator
  - Saves per-article raw JSON strings to a CSV
  - Saves final adjudicated annotations to a JSON file

Requirements:
  pip install -r src/dataset_comparison_scripts/requirements_llm_notebook.txt

Environment variables:
  OPENAI_API_KEY, GEMINI_API_KEY (required unless --dry-run)

Example:
  python "src/dataset_comparison_scripts/multiple_llm_annotations_script (1).py" \
    --input src/dataset_comparison_scripts/twelve_article_set.csv \
    --results-csv src/dataset_comparison_scripts/annotated_results_3annotators.csv \
    --final-json src/llm_annotation_results/paragraph_final_annotations_3annotators.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from jsonschema import ValidationError, validate
from tqdm.auto import tqdm

def _load_dotenv_if_present() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dotenv_path = repo_root / ".env"
    if not dotenv_path.exists():
        return

    # Prefer python-dotenv if available, but fall back to a tiny parser so this
    # script still works without extra dependencies.
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            # Strip optional surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            os.environ.setdefault(key, value)
        return

    load_dotenv(dotenv_path=dotenv_path, override=False)


SYSTEM_INSTRUCTIONS = """
You are tasked with detecting inflammatory language and persuasive propaganda in news articles.
Annotate the article using ONLY the categories and subcategories defined below.

=====================
INFLAMMATORY LANGUAGE
=====================

1. Name-Calling
Definition: Using a loaded positive or negative label to shape how the audience feels about a person, group, or idea.
Instead of providing evidence, the speaker uses emotionally charged wording to discredit or glorify.

2. Demonization
Definition: Describing people or groups as evil, dangerous, corrupt, disgusting, or less than human.
The goal is to turn the audience against the target by making them sound like a threat to society.

3. Scapegoating
Definition: Blaming an entire group for a broad problem or crisis. The group is framed as the main cause of widespread harm or decline.

=========================
PERSUASIVE PROPAGANDA
=========================

1. Exaggeration
2. Slogans
3. Bandwagon
4. Causal Oversimplification
5. Doubt

=====================
ANNOTATION RULES
=====================
- Extract exact spans (4–25 words) — no ellipses or paraphrasing.
- Annotate per paragraph.
- Be conservative: only label Persuasive Propaganda / Inflammatory Language when the language is explicit and clearly matches a definition; if unsure, choose No Polarizing language.
- When there is no polarizing language in a given paragraph, output one annotation for that paragraph:
  {
    "text": "no polarizing language selected",
    "category": "No Polarizing language",
    "subcategory": "no polarizing language",
    "paragraphIndex": <int>
  }
- Every paragraph should have at minimum one annotation.
- The first paragraph is paragraph 0.
- Return valid JSON ONLY; no backticks, no extra prose.
"""


ANNOTATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "topic": {"type": "string"},
        "source": {"type": "string"},
        "rating": {"type": "string"},
        "annotations": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["Persuasive Propaganda", "Inflammatory Language", "No Polarizing language"],
                    },
                    "subcategory": {
                        "type": "string",
                        "enum": [
                            "exaggeration",
                            "slogans",
                            "bandwagon",
                            "causal oversimplification",
                            "casual oversimplification",
                            "doubt",
                            "name-calling",
                            "demonization",
                            "scapegoating",
                            "no polarizing language",
                        ],
                    },
                    "text": {"type": "string", "minLength": 4, "maxLength": 600},
                    "openFeedback": {"type": "string", "minLength": 1},
                    "paragraphIndex": {"type": "integer"},
                },
                "required": ["category", "subcategory", "text", "openFeedback", "paragraphIndex"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "topic", "source", "rating", "annotations"],
    "additionalProperties": False,
}


def validate_annotation(obj: dict[str, Any]) -> tuple[bool, str | None]:
    try:
        validate(instance=obj, schema=ANNOTATION_SCHEMA)
        return True, None
    except ValidationError as exc:
        return False, str(exc)


def extract_json_from_text(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    return text[start : end + 1]


def normalize_annotation_enums(obj: dict[str, Any]) -> dict[str, Any]:
    if "annotations" not in obj or not isinstance(obj.get("annotations"), list):
        return obj

    valid_categories = {
        "persuasive propaganda": "Persuasive Propaganda",
        "inflammatory language": "Inflammatory Language",
        "no polarizing language": "No Polarizing language",
        "no polarizing": "No Polarizing language",
    }
    valid_subcategories = {
        "exaggeration": "exaggeration",
        "slogans": "slogans",
        "slogan": "slogans",
        "bandwagon": "bandwagon",
        # Tool/gold uses 'Casual Oversimplification' (note: casual, not causal).
        "causal oversimplification": "casual oversimplification",
        "causal_oversimplification": "casual oversimplification",
        "casual oversimplification": "casual oversimplification",
        "casual_oversimplification": "casual oversimplification",
        "doubt": "doubt",
        "name-calling": "name-calling",
        "name calling": "name-calling",
        "demonization": "demonization",
        "scapegoating": "scapegoating",
        "no polarizing language": "no polarizing language",
        "no polarizing": "no polarizing language",
    }
    subcategory_to_category = {
        "exaggeration": "Persuasive Propaganda",
        "slogans": "Persuasive Propaganda",
        "bandwagon": "Persuasive Propaganda",
        "causal oversimplification": "Persuasive Propaganda",
        "casual oversimplification": "Persuasive Propaganda",
        "doubt": "Persuasive Propaganda",
        "name-calling": "Inflammatory Language",
        "demonization": "Inflammatory Language",
        "scapegoating": "Inflammatory Language",
        "no polarizing language": "No Polarizing language",
    }

    for ann in obj.get("annotations", []):
        if not isinstance(ann, dict):
            continue

        # Normalize subcategory first (models often vary casing)
        sub = ann.get("subcategory")
        if isinstance(sub, str):
            sub_key = sub.strip().lower()
            if sub_key in valid_subcategories:
                ann["subcategory"] = valid_subcategories[sub_key]

        # Normalize category (models sometimes put a subcategory here)
        cat = ann.get("category")
        if isinstance(cat, str):
            cat_key = cat.strip().lower()
            if cat_key in valid_categories:
                ann["category"] = valid_categories[cat_key]
            elif cat_key in valid_subcategories:
                # If a model mistakenly put a subcategory in category, recover.
                ann["subcategory"] = valid_subcategories[cat_key]
                ann["category"] = subcategory_to_category.get(ann["subcategory"], ann.get("category"))

        # If category is still invalid but subcategory is valid, infer category from subcategory.
        cat = ann.get("category")
        sub = ann.get("subcategory")
        if isinstance(cat, str) and isinstance(sub, str):
            if cat not in ("Persuasive Propaganda", "Inflammatory Language", "No Polarizing language"):
                inferred = subcategory_to_category.get(sub.strip().lower())
                if inferred:
                    ann["category"] = inferred

        # Standardize "no polarizing language" placeholder text.
        # If the paragraph label is "No Polarizing language", ensure the text is the canonical placeholder
        # so downstream matching logic can align on it.
        if ann.get("category") == "No Polarizing language":
            ann["subcategory"] = "no polarizing language"
            ann["text"] = "no polarizing language selected"

    return obj


def repair_annotation_object(obj: dict[str, Any], *, body: str | None = None) -> dict[str, Any]:
    """
    Best-effort repair to satisfy schema requirements when models omit fields.
    This keeps the pipeline running while still producing schema-valid output.
    """
    anns = obj.get("annotations")
    if not isinstance(anns, list):
        return obj

    paragraphs = split_paragraphs_from_body(body) if body is not None else None
    max_para = (len(paragraphs) - 1) if paragraphs is not None else None

    for i, ann in enumerate(anns):
        if not isinstance(ann, dict):
            continue

        # Some models omit openFeedback; keep it short but non-empty.
        fb = ann.get("openFeedback")
        if not isinstance(fb, str) or not fb.strip():
            cat = ann.get("category", "")
            sub = ann.get("subcategory", "")
            ann["openFeedback"] = f"Auto-filled: {cat} / {sub}".strip()

        # Ensure paragraphIndex exists; if missing, default to 0 but warn.
        pidx = ann.get("paragraphIndex")
        if pidx is None:
            print(
                f"Warning: missing paragraphIndex for annotation {i}; defaulting to 0.",
                file=sys.stderr,
            )
            pidx = 0

        # If we have paragraph text, prefer assigning by locating the span inside a paragraph.
        if paragraphs is not None:
            inferred = infer_paragraph_index(str(ann.get("text", "")), paragraphs)
            if inferred is not None:
                pidx = inferred

            # Clamp out-of-range indices.
            if isinstance(pidx, int) and max_para is not None:
                if pidx < 0:
                    pidx = 0
                elif pidx > max_para:
                    pidx = max_para

        ann["paragraphIndex"] = pidx

    return obj


def decode_literal_newlines(body: str) -> str:
    # Our CSV may store paragraph breaks as the literal two-character sequence "\\n".
    return (body or "").replace("\\n", "\n")

def split_paragraphs_from_body(body: str) -> list[str]:
    text = decode_literal_newlines(body)
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if paragraphs:
        return paragraphs
    return [text.strip()] if text.strip() else [""]

def _norm_for_match(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())

def infer_paragraph_index(span_text: str, paragraphs: list[str]) -> int | None:
    needle = _norm_for_match(span_text)
    if not needle:
        return None
    best_idx = None
    best_overlap = 0
    needle_tokens = set(needle.split())

    for idx, para in enumerate(paragraphs):
        hay = _norm_for_match(para)
        if needle in hay:
            return idx

        hay_tokens = set(hay.split())
        overlap = len(needle_tokens & hay_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_idx = idx

    # Require at least 2 shared tokens to avoid random matches.
    if best_idx is not None and best_overlap >= 2:
        return best_idx
    return None


def _is_no_polarizing(ann: dict[str, Any]) -> bool:
    return ann.get("category") == "No Polarizing language"


def _dedupe_annotations(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, int]] = set()
    out: list[dict[str, Any]] = []
    for ann in annotations:
        cat = str(ann.get("category", ""))
        sub = str(ann.get("subcategory", ""))
        txt = str(ann.get("text", ""))
        pidx = ann.get("paragraphIndex")
        if not isinstance(pidx, int):
            continue
        key = (cat, sub, txt, pidx)
        if key in seen:
            continue
        seen.add(key)
        out.append(ann)
    return out


def enforce_paragraph_no_polarizing_policy(obj: dict[str, Any], *, body: str) -> dict[str, Any]:
    """
    Enforce paragraph-level rules:
      - Exactly ONE annotation per paragraph.
      - If a paragraph has ANY Inflammatory/Persuasive annotations, keep only the best polarizing annotation.
      - Otherwise, keep exactly one "No Polarizing language" placeholder annotation.
      - Ensure paragraphIndex values are in-range and prefer inferring from span text.
    """
    anns = obj.get("annotations")
    if not isinstance(anns, list):
        return obj

    paragraphs = split_paragraphs_from_body(body)
    max_para = max(0, len(paragraphs) - 1)

    normalized: list[dict[str, Any]] = []
    for ann in anns:
        if not isinstance(ann, dict):
            continue

        pidx = ann.get("paragraphIndex")
        if not isinstance(pidx, int):
            pidx = 0

        inferred = infer_paragraph_index(str(ann.get("text", "")), paragraphs)
        if inferred is not None:
            pidx = inferred

        pidx = min(max(pidx, 0), max_para)
        ann["paragraphIndex"] = pidx
        normalized.append(ann)

    normalized = _dedupe_annotations(normalized)

    by_para: dict[int, list[dict[str, Any]]] = {i: [] for i in range(max_para + 1)}
    for ann in normalized:
        by_para[ann["paragraphIndex"]].append(ann)

    def _pick_best_annotation(annotations: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not annotations:
            return None
        # Prefer longer spans as a simple proxy for specificity; keep stable ordering on ties.
        return max(enumerate(annotations), key=lambda item: (len(str(item[1].get("text", ""))), -item[0]))[1]

    final: list[dict[str, Any]] = []
    for pidx in range(max_para + 1):
        items = by_para.get(pidx, [])
        no = [a for a in items if _is_no_polarizing(a)]
        other = [a for a in items if not _is_no_polarizing(a)]

        if other:
            # If there's any polarizing annotation, keep only the best one for that paragraph.
            keep = _pick_best_annotation(other)
            if keep is not None:
                keep["paragraphIndex"] = pidx
                final.append(keep)
            continue

        # Otherwise, ensure exactly one no-polarizing annotation.
        if no:
            keep = _pick_best_annotation(no)
        else:
            keep = {
                "category": "No Polarizing language",
                "subcategory": "no polarizing language",
                "text": "no polarizing language selected",
                "openFeedback": "No polarizing language detected in this paragraph.",
                "paragraphIndex": pidx,
            }

        # Canonicalize the placeholder fields.
        keep["category"] = "No Polarizing language"
        keep["subcategory"] = "no polarizing language"
        keep["text"] = "no polarizing language selected"
        if not isinstance(keep.get("openFeedback"), str) or not keep["openFeedback"].strip():
            keep["openFeedback"] = "No polarizing language detected in this paragraph."
        keep["paragraphIndex"] = pidx
        final.append(keep)

    obj["annotations"] = _dedupe_annotations(final)
    return obj


def paragraph_count_from_body(body: str) -> int:
    txt = decode_literal_newlines(body)
    parts = [p.strip() for p in txt.split("\n") if p.strip()]
    return max(1, len(parts))


def build_article_text(row: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    title = str(row.get("Headline", ""))
    body = decode_literal_newlines(str(row.get("News body", "")))
    topic = str(row.get("Topic", ""))
    source = str(row.get("News Source", ""))
    rating = str(row.get("Rating", ""))

    article_block = (
        f"TITLE: {title}\n"
        f"TOPIC: {topic}\n"
        f"SOURCE: {source}\n"
        f"RATING: {rating}\n\n"
        f"BODY:\n{body}"
    )
    return title, topic, source, rating, body, article_block


def build_user_prompt_for_annotation(article_block: str) -> str:
    return (
        "You will annotate the following news article for inflammatory language and persuasive propaganda.\n"
        "Follow the system instructions and JSON schema exactly.\n\n"
        "ARTICLE:\n"
        f"{article_block}\n\n"
        "Return ONLY a single JSON object, no backticks, no explanation."
    )


@dataclass(frozen=True)
class ModelConfig:
    openai_model: str
    gemini_model: str
    adjudicator_model: str
    temperature: float = 0.1


def _retry(call, *, max_retries: int, base_sleep_s: float = 1.0):
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 - intentional catch/retry boundary
            last_exc = exc
            if attempt >= max_retries:
                raise
            sleep_s = base_sleep_s * (2**attempt) + random.random() * 0.25
            time.sleep(sleep_s)
    raise last_exc  # pragma: no cover


def _require_keys(unless_dry_run: bool):
    if unless_dry_run:
        return
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY env var.")
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Missing GEMINI_API_KEY env var.")


def _openai_client():
    from openai import OpenAI

    return OpenAI()


def _gemini_client():
    from google import genai

    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def annotate_dry_run(title: str, topic: str, source: str, rating: str, body: str) -> tuple[dict[str, Any], str]:
    n_paras = paragraph_count_from_body(body)
    obj = {
        "title": title,
        "topic": topic,
        "source": source,
        "rating": rating,
        "annotations": [
            {
                "category": "No Polarizing language",
                "subcategory": "no polarizing language",
                "text": "no polarizing language selected",
                "openFeedback": "dry-run placeholder",
                "paragraphIndex": i,
            }
            for i in range(n_paras)
        ],
    }
    ok, err = validate_annotation(obj)
    if not ok:
        raise ValueError(f"Dry-run output failed schema validation: {err}")
    raw = json.dumps(obj, ensure_ascii=False)
    return obj, raw


def annotate_with_openai(client, role_desc: str, article_block: str, title: str, topic: str, source: str, rating: str, *, body: str, model: str, temperature: float, max_retries: int):
    user_prompt = build_user_prompt_for_annotation(article_block)

    def _call():
        return client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTIONS + "\n\n" + role_desc},
                {"role": "user", "content": user_prompt},
            ],
        )

    completion = _retry(_call, max_retries=max_retries)
    raw = completion.choices[0].message.content.strip()
    json_str = extract_json_from_text(raw)
    obj = json.loads(json_str)

    obj.setdefault("title", title)
    obj.setdefault("topic", topic)
    obj.setdefault("source", source)
    obj.setdefault("rating", rating)
    obj = normalize_annotation_enums(obj)
    obj = repair_annotation_object(obj, body=body)
    # Keep annotator outputs as-is beyond basic repairs; apply paragraph policy to FINAL output only.

    ok, err = validate_annotation(obj)
    if not ok:
        raise ValueError(f"OpenAI returned JSON failed schema validation: {err}\n\n{json_str}")
    return obj, json_str


def annotate_with_gemini(client, role_desc: str, article_block: str, title: str, topic: str, source: str, rating: str, *, body: str, model: str, max_retries: int):
    user_prompt = build_user_prompt_for_annotation(article_block)
    prompt = (
        "SYSTEM INSTRUCTIONS:\n"
        + SYSTEM_INSTRUCTIONS
        + "\n\nJSON SCHEMA (YOU MUST FOLLOW THIS EXACTLY):\n"
        + json.dumps(ANNOTATION_SCHEMA)
        + "\n\nROLE:\n"
        + role_desc
        + "\n\nTASK:\n"
        + user_prompt
        + "\n\nOUTPUT FORMAT:\n"
        "Return ONLY a single JSON object that strictly matches the JSON schema above.\n"
        "Do NOT wrap the JSON in ```json``` fences.\n"
        "Do NOT include any commentary or explanation outside the JSON.\n"
    )

    def _call():
        return client.models.generate_content(model=model, contents=prompt)

    response = _retry(_call, max_retries=max_retries)
    raw = (getattr(response, "text", None) or "").strip()
    json_str = extract_json_from_text(raw)
    obj = json.loads(json_str)

    obj.setdefault("title", title)
    obj.setdefault("topic", topic)
    obj.setdefault("source", source)
    obj.setdefault("rating", rating)
    obj = normalize_annotation_enums(obj)
    obj = repair_annotation_object(obj, body=body)
    # Keep annotator outputs as-is beyond basic repairs; apply paragraph policy to FINAL output only.
    ok, err = validate_annotation(obj)
    if not ok:
        raise ValueError(f"Gemini returned JSON failed schema validation: {err}\n\n{json_str}")
    return obj, json_str


def adjudicate_with_openai(client, article_block: str, title: str, topic: str, source: str, rating: str, obj_a: dict[str, Any], obj_b: dict[str, Any], obj_c: dict[str, Any], *, body: str, model: str, temperature: float, max_retries: int):
    adjudicator_system = """
You are the Adjudicator, a methods-oriented political scientist overseeing three annotators.

Your goal: produce ONE final set of annotations.
Constraints:
- Output must strictly match the provided JSON schema.
- You may only select from the annotations that appear in the three annotator JSON objects.
- You may merge only exact duplicates (same category, same subcategory, same text, same paragraphIndex).
- Do NOT invent new spans.
- Be conservative: if unsure, choose No Polarizing language.
"""

    user_prompt = f"""
ARTICLE:
{article_block}

ANNOTATOR_A_JSON:
{json.dumps(obj_a, ensure_ascii=False)}

ANNOTATOR_B_JSON:
{json.dumps(obj_b, ensure_ascii=False)}

ANNOTATOR_C_JSON:
{json.dumps(obj_c, ensure_ascii=False)}

Return ONLY the final JSON object.
Meta fields must be set to:
  title={title!r}, topic={topic!r}, source={source!r}, rating={rating!r}
"""

    def _call():
        return client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": adjudicator_system + "\n\nJSON_SCHEMA:\n" + json.dumps(ANNOTATION_SCHEMA)},
                {"role": "user", "content": user_prompt},
            ],
        )

    completion = _retry(_call, max_retries=max_retries)
    raw = completion.choices[0].message.content.strip()
    json_str = extract_json_from_text(raw)
    obj = json.loads(json_str)

    obj.setdefault("title", title)
    obj.setdefault("topic", topic)
    obj.setdefault("source", source)
    obj.setdefault("rating", rating)
    obj = normalize_annotation_enums(obj)
    obj = repair_annotation_object(obj, body=body)
    obj = enforce_paragraph_no_polarizing_policy(obj, body=body)
    ok, err = validate_annotation(obj)
    if not ok:
        raise ValueError(f"Adjudicated JSON failed schema validation: {err}\n\n{json_str}")
    return obj, json_str


def run_pipeline(df: pd.DataFrame, cfg: ModelConfig, *, dry_run: bool, max_retries: int):
    openai_client = None
    gemini_client = None
    if not dry_run:
        openai_client = _openai_client()
        gemini_client = _gemini_client()

    results: list[dict[str, Any]] = []
    final_annotations: list[dict[str, Any]] = []

    for idx, row in tqdm(df.iterrows(), total=len(df)):
        title, topic, source, rating, body, article_block = build_article_text(row)

        if dry_run:
            obj_a, raw_a = annotate_dry_run(title, topic, source, rating, body)
            obj_b, raw_b = annotate_dry_run(title, topic, source, rating, body)
            obj_c, raw_c = annotate_dry_run(title, topic, source, rating, body)
            final_obj, final_raw = annotate_dry_run(title, topic, source, rating, body)
        else:
            obj_a, raw_a = annotate_with_openai(
                openai_client,
                "You are Annotator A, a political communication scholar. Strictly follow the codebook and JSON schema. Be conservative: if unsure, choose No Polarizing language.",
                article_block,
                title,
                topic,
                source,
                rating,
                body=body,
                model=cfg.openai_model,
                temperature=cfg.temperature,
                max_retries=max_retries,
            )

            obj_b, raw_b = annotate_with_gemini(
                gemini_client,
                "You are Annotator B, a linguistics/discourse analyst. Your strength is correct subcategory selection. Be conservative: avoid over-labeling; if unsure, choose No Polarizing language.",
                article_block,
                title,
                topic,
                source,
                rating,
                body=body,
                model=cfg.gemini_model,
                max_retries=max_retries,
            )

            obj_c, raw_c = annotate_with_openai(
                openai_client,
                "You are Annotator C, a conservative/high-precision media psychology expert. Be conservative: only label when explicit; if unsure, choose No Polarizing language.",
                article_block,
                title,
                topic,
                source,
                rating,
                body=body,
                model=cfg.openai_model,
                temperature=cfg.temperature,
                max_retries=max_retries,
            )

            final_obj, final_raw = adjudicate_with_openai(
                openai_client,
                article_block,
                title,
                topic,
                source,
                rating,
                obj_a,
                obj_b,
                obj_c,
                body=body,
                model=cfg.adjudicator_model,
                temperature=cfg.temperature,
                max_retries=max_retries,
            )

        results.append(
            {
                "index": idx,
                "title": title,
                "topic": topic,
                "source": source,
                "rating": rating,
                "annotator_A_json": raw_a,
                "annotator_B_json": raw_b,
                "annotator_C_json": raw_c,
                "final_json": final_raw,
            }
        )
        final_annotations.append(final_obj)

    return results, final_annotations


def main() -> int:
    _load_dotenv_if_present()

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="src/dataset_comparison_scripts/twelve_article_set.csv")
    parser.add_argument("--results-csv", default="src/dataset_comparison_scripts/annotated_results_3annotators.csv")
    parser.add_argument("--final-json", default="src/llm_annotation_results/final_annotations_3annotators.json")
    parser.add_argument("--openai-model", default="gpt-5.1")
    parser.add_argument("--adjudicator-model", default=None)
    parser.add_argument("--gemini-model", default="gemini-3-pro-preview")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true", help="No network calls; emits placeholder outputs.")
    args = parser.parse_args()

    _require_keys(unless_dry_run=args.dry_run)

    cfg = ModelConfig(
        openai_model=args.openai_model,
        adjudicator_model=args.adjudicator_model or args.openai_model,
        gemini_model=args.gemini_model,
    )

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    df = pd.read_csv(input_path)
    results, finals = run_pipeline(df, cfg, dry_run=args.dry_run, max_retries=args.max_retries)

    results_df = pd.DataFrame(results)
    results_csv_path = Path(args.results_csv)
    results_df.to_csv(results_csv_path, index=False)

    final_json_path = Path(args.final_json)
    final_json_path.parent.mkdir(parents=True, exist_ok=True)
    with final_json_path.open("w", encoding="utf-8") as f:
        json.dump(finals, f, indent=2, ensure_ascii=False)

    print(f"Wrote results CSV: {results_csv_path}")
    print(f"Wrote final JSON: {final_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
