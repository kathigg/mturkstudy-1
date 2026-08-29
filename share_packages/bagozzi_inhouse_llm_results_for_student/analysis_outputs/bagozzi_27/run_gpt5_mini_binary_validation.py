from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
DEFAULT_TRAINING_JSON = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/turker_training_set_four_articles_with_ringers.json"
)
DEFAULT_OUTPUT_DIR = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/gpt5_mini_binary_validation_with_ringers"
)


@dataclass(frozen=True)
class StudyItem:
    item_id: str
    article_title: str
    source: str
    rating: str
    topic: str
    article_text: str
    paragraph_index: int
    candidate_span: str
    hidden_gold_binary: str
    hidden_gold_category: str
    hidden_gold_subcategory: str
    source_annotation_type: str


def load_dotenv_if_present() -> None:
    dotenv_path = REPO / ".env"
    if not dotenv_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            os.environ.setdefault(key.strip(), value)
        return
    load_dotenv(dotenv_path=dotenv_path, override=False)


def normalize_space(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object found in model output.")
    depth = 0
    in_string = False
    escaped = False
    for i, char in enumerate(text[start:], start):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                obj = json.loads(text[start : i + 1])
                if not isinstance(obj, dict):
                    raise ValueError("Model JSON was not an object.")
                return obj
    raise ValueError("No complete JSON object found in model output.")


def normalize_decision(value: Any) -> str:
    text = normalize_space(str(value)).lower().replace("-", "_").replace(" ", "_")
    if text in {"polarizing", "yes", "accept", "agree", "problematic", "true"}:
        return "polarizing"
    if text in {
        "not_polarizing",
        "non_polarizing",
        "no",
        "deny",
        "disagree",
        "not_problematic",
        "false",
        "no_polarizing_language",
    }:
        return "not_polarizing"
    raise ValueError(f"Unrecognized binary decision: {value!r}")


def build_study_items_from_training_json(path: Path) -> list[StudyItem]:
    articles = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(articles, list):
        raise ValueError(f"Expected list of articles in {path}")

    items: list[StudyItem] = []
    true_counter = 0
    false_counter = 0
    for article_idx, article in enumerate(articles):
        article_title = str(article.get("title") or article.get("source_title") or f"article_{article_idx}")
        article_text = normalize_space(str(article.get("news_body") or ""))
        source = str(article.get("news_source") or "")
        rating = str(article.get("rating") or "")
        topic = str(article.get("topic") or "")

        for ann in article.get("annotations") or []:
            true_counter += 1
            items.append(
                StudyItem(
                    item_id=f"training_true_{true_counter:03d}",
                    article_title=article_title,
                    source=source,
                    rating=rating,
                    topic=topic,
                    article_text=article_text,
                    paragraph_index=int(ann.get("paragraph_index", ann.get("paragraphIndex", 0))),
                    candidate_span=normalize_space(str(ann.get("text") or "")),
                    hidden_gold_binary="polarizing",
                    hidden_gold_category=str(ann.get("category") or ""),
                    hidden_gold_subcategory=str(ann.get("subcategory") or ""),
                    source_annotation_type="true_annotation",
                )
            )

        for ann in article.get("false_annotations") or []:
            false_counter += 1
            items.append(
                StudyItem(
                    item_id=f"training_false_{false_counter:03d}",
                    article_title=article_title,
                    source=source,
                    rating=rating,
                    topic=topic,
                    article_text=article_text,
                    paragraph_index=int(ann.get("paragraph_index", ann.get("paragraphIndex", 0))),
                    candidate_span=normalize_space(str(ann.get("text") or "")),
                    hidden_gold_binary="not_polarizing",
                    hidden_gold_category=str(ann.get("category") or ""),
                    hidden_gold_subcategory=str(ann.get("subcategory") or ""),
                    source_annotation_type="false_annotation_ringer",
                )
            )

    if not items:
        raise ValueError(f"No training items found in {path}")
    return items


def item_for_model(item: StudyItem) -> dict[str, Any]:
    return {
        "item_id": item.item_id,
        "article_title": item.article_title,
        "source": item.source,
        "rating": item.rating,
        "topic": item.topic,
        "article_text": item.article_text,
        "paragraph_index": item.paragraph_index,
        "candidate_span": item.candidate_span,
    }


def hidden_gold_for_item(item: StudyItem) -> dict[str, Any]:
    payload = asdict(item)
    payload.pop("article_text", None)
    return payload


SYSTEM_PROMPT = """You are evaluating candidate text spans from news articles for a worker qualification task.

Decide whether the candidate span itself contains polarizing language.

Use this binary decision:
- polarizing: the span contains inflammatory language or persuasive propaganda.
- not_polarizing: the span is neutral, factual, ordinary context, attribution, or background information.

Definitions:
- Inflammatory language includes direct insults/name-calling, demonization, or scapegoating.
- Persuasive propaganda includes exaggeration, slogans, bandwagon/social-pressure appeals, casual oversimplification, or doubt/credibility-undermining framing.

Rules:
- Judge only the candidate span, using the article text as context.
- Do not infer polarizing language from the general topic alone.
- A factual sentence about a controversy, poll, quote attribution, number, event, or policy can still be not_polarizing.
- Return valid JSON only with keys: decision, confidence, reason.
- decision must be exactly "polarizing" or "not_polarizing".
"""


def build_user_prompt(item: StudyItem) -> str:
    visible = item_for_model(item)
    return (
        "Evaluate this candidate span.\n\n"
        f"Article title: {visible['article_title']}\n"
        f"Source: {visible['source']}\n"
        f"Rating: {visible['rating']}\n"
        f"Topic: {visible['topic']}\n"
        f"Paragraph index from source data: {visible['paragraph_index']}\n\n"
        f"Article text:\n{visible['article_text']}\n\n"
        f"Candidate span:\n{visible['candidate_span']}\n\n"
        'Return JSON like {"decision":"polarizing","confidence":0.91,"reason":"short reason"}'
    )


def retry(call, *, max_retries: int) -> Any:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 - deliberate API retry boundary
            last_exc = exc
            if attempt >= max_retries:
                raise
            time.sleep(1.0 * (2**attempt) + random.random() * 0.25)
    raise last_exc or RuntimeError("Retry failed without exception")


def call_openai(
    client: Any,
    *,
    model: str,
    item: StudyItem,
    temperature: float | None,
    max_retries: int,
) -> tuple[dict[str, Any], str]:
    request_kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(item)},
        ],
        "response_format": {"type": "json_object"},
    }
    if temperature is not None:
        request_kwargs["temperature"] = temperature

    def _call() -> Any:
        return client.chat.completions.create(**request_kwargs)

    try:
        completion = retry(_call, max_retries=max_retries)
    except Exception as exc:
        msg = str(exc).lower()
        if "temperature" in msg and temperature is not None:
            request_kwargs.pop("temperature", None)
            completion = retry(_call, max_retries=max_retries)
        elif "response_format" in msg:
            request_kwargs.pop("response_format", None)
            completion = retry(_call, max_retries=max_retries)
        else:
            raise

    raw = completion.choices[0].message.content or ""
    obj = parse_json_object(raw)
    obj["decision"] = normalize_decision(obj.get("decision"))
    try:
        obj["confidence"] = float(obj.get("confidence", 0))
    except (TypeError, ValueError):
        obj["confidence"] = 0.0
    obj["reason"] = normalize_space(str(obj.get("reason") or ""))
    return obj, raw


def existing_decisions_by_item(results_csv: Path) -> dict[str, dict[str, str]]:
    if not results_csv.exists():
        return {}
    with results_csv.open(newline="", encoding="utf-8") as f:
        return {row["item_id"]: row for row in csv.DictReader(f)}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tp = sum(1 for r in rows if r["gold_binary"] == "polarizing" and r["decision"] == "polarizing")
    fn = sum(1 for r in rows if r["gold_binary"] == "polarizing" and r["decision"] == "not_polarizing")
    tn = sum(1 for r in rows if r["gold_binary"] == "not_polarizing" and r["decision"] == "not_polarizing")
    fp = sum(1 for r in rows if r["gold_binary"] == "not_polarizing" and r["decision"] == "polarizing")
    total = len(rows)
    correct = tp + tn

    def div(num: int, den: int) -> float:
        return round(num / den, 3) if den else 0.0

    def row_correct(row: dict[str, Any]) -> bool:
        return str(row["is_correct"]).lower() == "true"

    by_type: dict[str, dict[str, Any]] = {}
    for key in ["true_annotation", "false_annotation_ringer"]:
        subset = [r for r in rows if r["source_annotation_type"] == key]
        by_type[key] = {
            "total": len(subset),
            "correct": sum(1 for r in subset if row_correct(r)),
            "accuracy": div(sum(1 for r in subset if row_correct(r)), len(subset)),
            "marked_polarizing": sum(1 for r in subset if r["decision"] == "polarizing"),
            "marked_not_polarizing": sum(1 for r in subset if r["decision"] == "not_polarizing"),
        }

    by_article: dict[str, dict[str, Any]] = {}
    for title in sorted({r["article_title"] for r in rows}):
        subset = [r for r in rows if r["article_title"] == title]
        by_article[title] = {
            "total": len(subset),
            "correct": sum(1 for r in subset if row_correct(r)),
            "accuracy": div(sum(1 for r in subset if row_correct(r)), len(subset)),
            "true_annotations": sum(1 for r in subset if r["gold_binary"] == "polarizing"),
            "ringers": sum(1 for r in subset if r["gold_binary"] == "not_polarizing"),
        }

    return {
        "total_items": total,
        "gold_polarizing_items": tp + fn,
        "gold_not_polarizing_ringers": tn + fp,
        "correct": correct,
        "incorrect": total - correct,
        "accuracy": div(correct, total),
        "confusion_matrix": {
            "true_positive": tp,
            "false_negative": fn,
            "true_negative": tn,
            "false_positive": fp,
        },
        "polarizing_precision": div(tp, tp + fp),
        "polarizing_recall_sensitivity": div(tp, tp + fn),
        "not_polarizing_specificity": div(tn, tn + fp),
        "negative_predictive_value": div(tn, tn + fn),
        "by_source_annotation_type": by_type,
        "by_article": by_article,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-json", default=str(DEFAULT_TRAINING_JSON))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    load_dotenv_if_present()
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY env var.")

    training_json = Path(args.training_json).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results_csv = output_dir / "gpt5_mini_binary_validation_results.csv"
    summary_json = output_dir / "gpt5_mini_binary_validation_summary.json"
    raw_jsonl = output_dir / "raw_gpt5_mini_responses.jsonl"
    visible_items_json = output_dir / "study_items_for_model_no_gold.json"
    hidden_key_json = output_dir / "hidden_gold_key.json"

    items = build_study_items_from_training_json(training_json)
    if args.max_items is not None:
        items = items[: args.max_items]

    visible_items_json.write_text(
        json.dumps([item_for_model(item) for item in items], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    hidden_key_json.write_text(
        json.dumps([hidden_gold_for_item(item) for item in items], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    previous = existing_decisions_by_item(results_csv) if args.resume else {}
    rows: list[dict[str, Any]] = list(previous.values()) if args.resume else []
    completed = {row["item_id"] for row in rows}

    from openai import OpenAI

    client = OpenAI()
    raw_mode = "a" if args.resume and raw_jsonl.exists() else "w"
    with raw_jsonl.open(raw_mode, encoding="utf-8") as raw_f:
        for idx, item in enumerate(items, start=1):
            if item.item_id in completed:
                continue
            print(f"[{idx}/{len(items)}] {item.item_id} {item.hidden_gold_binary}", flush=True)
            obj, raw = call_openai(
                client,
                model=args.model,
                item=item,
                temperature=args.temperature,
                max_retries=args.max_retries,
            )
            is_correct = obj["decision"] == item.hidden_gold_binary
            row = {
                "item_id": item.item_id,
                "model": args.model,
                "temperature": args.temperature,
                "article_title": item.article_title,
                "paragraph_index": item.paragraph_index,
                "candidate_span": item.candidate_span,
                "decision": obj["decision"],
                "confidence": obj["confidence"],
                "reason": obj["reason"],
                "gold_binary": item.hidden_gold_binary,
                "gold_category": item.hidden_gold_category,
                "gold_subcategory": item.hidden_gold_subcategory,
                "source_annotation_type": item.source_annotation_type,
                "is_correct": is_correct,
            }
            rows.append(row)
            write_csv(results_csv, rows)
            raw_f.write(
                json.dumps(
                    {
                        "item_id": item.item_id,
                        "raw_response": raw,
                        "parsed": obj,
                        "gold_binary": item.hidden_gold_binary,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            raw_f.flush()

    summary = {
        "method": (
            "MTurk-style binary validation: model sees article text and candidate span only; "
            "hidden true/ringer labels are not included in the prompt."
        ),
        "candidate_source": str(training_json),
        "model": args.model,
        "temperature": args.temperature,
        "model_visible_items": str(visible_items_json),
        "hidden_gold_key": str(hidden_key_json),
        "raw_responses": str(raw_jsonl),
        "results_csv": str(results_csv),
        "scores": score(rows),
    }
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary["scores"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
