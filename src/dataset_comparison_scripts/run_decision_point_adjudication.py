from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO / "src/dataset_comparison_scripts/2-20/2-20_selected_articles.csv"
DEFAULT_GOLD = (
    REPO
    / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/"
    "consolidated_bagozzi_inhouse_overlap_gold_with_conservative_npl_paragraph_spans.json"
)
DEFAULT_OUTPUT_ROOT = REPO / "src/llm_annotation_results/2-20/decision_point_adjudication_v1"
DEFAULT_ANALYSIS_ROOT = (
    REPO / "src/dataset_comparison_scripts/statistical_analysis/bagozzi_27/decision_point_adjudication_v1"
)

DEFAULT_CANDIDATE_SOURCES = [
    (
        "gpt5mini_prompt5",
        REPO
        / "src/llm_annotation_results/2-20/npl_prompt_comparison/"
        "prompt_5_human_aligned_precision_recall_single_models/openai_gpt_5_mini/final_annotations.json",
        1.1,
    ),
    (
        "gemini_flash_prompt5",
        REPO
        / "src/llm_annotation_results/2-20/npl_prompt_comparison/"
        "prompt_5_human_aligned_precision_recall_single_models/gemini_gemini_3_1_flash_lite/final_annotations.json",
        1.0,
    ),
    (
        "claude_haiku_prompt5",
        REPO
        / "src/llm_annotation_results/2-20/npl_prompt_comparison/"
        "prompt_5_human_aligned_precision_recall_single_models/claude_claude_haiku_4_5/final_annotations.json",
        0.7,
    ),
    (
        "adjudicated_prompt2",
        REPO
        / "src/llm_annotation_results/2-20/npl_prompt_comparison/adjudication_prompt_1_to_5/"
        "prompt_2_dr_bagozzi_temp0p0_run1/final_annotations.json",
        1.1,
    ),
]

DEFAULT_LABEL_SOURCES = [
    (
        "gpt5mini_prompt4_labeler",
        REPO
        / "src/llm_annotation_results/2-20/npl_prompt_comparison/"
        "prompt_4_boundary_examples_precision_single_models/openai_gpt_5_mini/final_annotations.json",
        1.2,
    ),
    (
        "adjudicated_prompt4_labeler",
        REPO
        / "src/llm_annotation_results/2-20/npl_prompt_comparison/adjudication_prompt_1_to_5/"
        "prompt_4_boundary_examples_precision_temp0p0_run1/final_annotations.json",
        1.2,
    ),
]

THRESHOLDS = [0.45, 0.50, 0.55, 0.60, 0.65]
NPL_CATEGORY = "No Polarizing language"
NPL_SUBCATEGORY = "no polarizing language"
NPL_TEXT = "no polarizing language selected"


@dataclass(frozen=True)
class SourceSpec:
    name: str
    path: Path
    weight: float = 1.0


@dataclass
class Article:
    title: str
    topic: str
    source: str
    rating: str
    body: str
    paragraphs: list[str]

    @property
    def norm_title(self) -> str:
        return normalize_title(self.title)


@dataclass
class Candidate:
    source_name: str
    source_weight: float
    article_title: str
    norm_title: str
    paragraph_index: int
    text: str
    category: str
    subcategory: str
    open_feedback: str = ""


@dataclass
class BinaryVote:
    cluster_id: str
    validator: str
    decision: str
    confidence: float
    weight: float
    reason: str = ""
    matching_span: str = ""

    @property
    def yes_contribution(self) -> float:
        if self.decision == "polarizing":
            return self.weight * self.confidence
        return self.weight * (1.0 - self.confidence)


@dataclass
class Cluster:
    cluster_id: str
    article_title: str
    norm_title: str
    paragraph_index: int
    candidates: list[Candidate] = field(default_factory=list)
    binary_votes: list[BinaryVote] = field(default_factory=list)
    accept_score: float = 0.0
    accepted: bool = False
    representative_span: str = ""
    final_category: str = ""
    final_subcategory: str = ""
    final_open_feedback: str = ""

    def candidate_spans(self) -> list[str]:
        seen: set[str] = set()
        spans: list[str] = []
        for candidate in self.candidates:
            key = normalize_span(candidate.text)
            if key and key not in seen:
                seen.add(key)
                spans.append(candidate.text)
        return spans

    def source_names(self) -> set[str]:
        return {candidate.source_name for candidate in self.candidates}


def normalize_title(text: str | None) -> str:
    return re.sub(r"[^\w\s]", "", text or "").strip().lower()


def normalize_space(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_span(text: str | None) -> str:
    text = re.sub(r"[^\w\s]", " ", text or "").lower()
    return normalize_space(text)


def normalize_label(text: str | None) -> str:
    return re.sub(r"_+", " ", text or "").strip().lower()


def canonical_category(text: str | None) -> str:
    label = normalize_label(text)
    if label == "inflammatory language":
        return "Inflammatory Language"
    if label == "persuasive propaganda":
        return "Persuasive Propaganda"
    if "no polarizing language" in label:
        return NPL_CATEGORY
    return normalize_space(text or "")


def canonical_subcategory(text: str | None) -> str:
    label = normalize_label(text)
    if label in {"causal oversimplification", "casual oversimplification"}:
        return "casual oversimplification"
    if "no polarizing language" in label:
        return NPL_SUBCATEGORY
    return label


def is_npl(annotation: dict[str, Any] | Candidate) -> bool:
    if isinstance(annotation, Candidate):
        joined = f"{annotation.category} {annotation.subcategory} {annotation.text}"
    else:
        joined = (
            f"{annotation.get('category', '')} {annotation.get('subcategory', '')} "
            f"{annotation.get('text', '')}"
        )
    return "no polarizing language" in normalize_label(joined)


def decode_literal_newlines(text: str) -> str:
    return text.replace("\\n", "\n")


def split_paragraphs(body: str) -> list[str]:
    paragraphs = [p.strip() for p in decode_literal_newlines(body).split("\n") if p.strip()]
    return paragraphs or [decode_literal_newlines(body).strip()]


def load_dotenv_if_present() -> None:
    dotenv_path = REPO / ".env"
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def load_comparison_module() -> Any:
    path = REPO / "src/dataset_comparison_scripts/paragraph_llm_human_comparison.py"
    spec = importlib.util.spec_from_file_location("paragraph_llm_human_comparison", path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Could not load comparison module from {path}")
    spec.loader.exec_module(module)
    return module


COMP = load_comparison_module()


def spans_match(a: Candidate | dict[str, Any], b: Candidate | dict[str, Any], *, title: str) -> bool:
    a_text = a.text if isinstance(a, Candidate) else str(a.get("text", ""))
    b_text = b.text if isinstance(b, Candidate) else str(b.get("text", ""))
    a_pidx = a.paragraph_index if isinstance(a, Candidate) else a.get("paragraphIndex")
    b_pidx = b.paragraph_index if isinstance(b, Candidate) else b.get("paragraphIndex")
    return bool(COMP.spans_match(a_text, b_text, title, title, a_pidx, b_pidx))


def load_articles(path: Path, *, max_articles: int | None = None) -> list[Article]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if max_articles is not None:
        rows = rows[:max_articles]
    articles: list[Article] = []
    for row in rows:
        body = decode_literal_newlines(str(row.get("News body") or row.get("news_body") or ""))
        articles.append(
            Article(
                title=str(row.get("Headline") or row.get("title") or ""),
                topic=str(row.get("Topic") or row.get("topic") or ""),
                source=str(row.get("News Source") or row.get("source") or ""),
                rating=str(row.get("Rating") or row.get("rating") or ""),
                body=body,
                paragraphs=split_paragraphs(body),
            )
        )
    return articles


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_source_spec(value: str, *, default_weight: float = 1.0) -> SourceSpec:
    if "=" not in value:
        raise ValueError(f"Source must be formatted as NAME=PATH or NAME=PATH:WEIGHT, got: {value}")
    name, rest = value.split("=", 1)
    weight = default_weight
    path_text = rest
    maybe_path, maybe_weight = rest.rsplit(":", 1) if ":" in rest else (rest, "")
    try:
        if maybe_weight:
            weight = float(maybe_weight)
            path_text = maybe_path
    except ValueError:
        path_text = rest
    return SourceSpec(name=name.strip(), path=Path(path_text).expanduser(), weight=weight)


def existing_specs(defaults: list[tuple[str, Path, float]], overrides: list[str] | None) -> list[SourceSpec]:
    if overrides:
        specs = [parse_source_spec(value) for value in overrides]
    else:
        specs = [SourceSpec(name, path, weight) for name, path, weight in defaults]

    out: list[SourceSpec] = []
    for spec in specs:
        path = spec.path if spec.path.is_absolute() else REPO / spec.path
        if not path.exists():
            print(f"Skipping missing source: {spec.name} -> {path}", file=sys.stderr)
            continue
        out.append(SourceSpec(spec.name, path, spec.weight))
    return out


def load_candidates_from_source(spec: SourceSpec, article_titles: set[str] | None = None) -> list[Candidate]:
    data = load_json(spec.path)
    candidates: list[Candidate] = []
    for article in data:
        title = str(article.get("title") or "UNKNOWN_TITLE")
        norm_title = normalize_title(title)
        if article_titles is not None and norm_title not in article_titles:
            continue
        for ann in article.get("annotations") or article.get("items") or []:
            if not isinstance(ann, dict) or is_npl(ann):
                continue
            text = normalize_space(str(ann.get("text") or ""))
            if not text:
                continue
            pidx = ann.get("paragraphIndex")
            if not isinstance(pidx, int):
                pidx = 0
            candidates.append(
                Candidate(
                    source_name=spec.name,
                    source_weight=spec.weight,
                    article_title=title,
                    norm_title=norm_title,
                    paragraph_index=pidx,
                    text=text,
                    category=canonical_category(str(ann.get("category") or "")),
                    subcategory=canonical_subcategory(str(ann.get("subcategory") or "")),
                    open_feedback=normalize_space(str(ann.get("openFeedback") or ann.get("reason") or "")),
                )
            )
    return candidates


def should_add_to_cluster(cluster: Cluster, candidate: Candidate) -> bool:
    if cluster.norm_title != candidate.norm_title:
        return False
    if cluster.paragraph_index != candidate.paragraph_index:
        return False
    return any(spans_match(existing, candidate, title=cluster.article_title) for existing in cluster.candidates)


def choose_representative_span(candidates: list[Candidate]) -> str:
    nonempty = [candidate.text for candidate in candidates if normalize_span(candidate.text)]
    if not nonempty:
        return ""
    return min(nonempty, key=lambda text: (len(normalize_span(text).split()), len(text), normalize_span(text)))


def cluster_candidates(candidates: list[Candidate]) -> list[Cluster]:
    clusters: list[Cluster] = []
    counters: dict[tuple[str, int], int] = {}
    for candidate in candidates:
        matched = None
        for cluster in clusters:
            if should_add_to_cluster(cluster, candidate):
                matched = cluster
                break
        if matched is None:
            key = (candidate.norm_title, candidate.paragraph_index)
            counters[key] = counters.get(key, 0) + 1
            cluster_id = f"{candidate.norm_title[:48]}__p{candidate.paragraph_index}__c{counters[key]}"
            matched = Cluster(
                cluster_id=cluster_id,
                article_title=candidate.article_title,
                norm_title=candidate.norm_title,
                paragraph_index=candidate.paragraph_index,
            )
            clusters.append(matched)
        matched.candidates.append(candidate)

    for cluster in clusters:
        cluster.representative_span = choose_representative_span(cluster.candidates)
    return clusters


def apply_source_votes(clusters: list[Cluster], candidate_specs: list[SourceSpec]) -> list[dict[str, Any]]:
    vote_rows: list[dict[str, Any]] = []
    total_weight = sum(spec.weight for spec in candidate_specs)
    for cluster in clusters:
        cluster.binary_votes = []
        proposed_sources = cluster.source_names()
        for spec in candidate_specs:
            matching = [candidate.text for candidate in cluster.candidates if candidate.source_name == spec.name]
            proposed = spec.name in proposed_sources
            vote = BinaryVote(
                cluster_id=cluster.cluster_id,
                validator=spec.name,
                decision="polarizing" if proposed else "not_polarizing",
                confidence=1.0,
                weight=spec.weight,
                reason="source proposed a matching span" if proposed else "source did not propose a matching span",
                matching_span=" | ".join(matching),
            )
            cluster.binary_votes.append(vote)
            vote_rows.append(asdict(vote))
        yes_weight = sum(vote.weight for vote in cluster.binary_votes if vote.decision == "polarizing")
        cluster.accept_score = round(yes_weight / total_weight, 6) if total_weight else 0.0
    return vote_rows


def extract_json_from_text(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model output.")
    depth = 0
    in_string = False
    escaped = False
    for pos in range(start, len(text)):
        char = text[pos]
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
                return json.loads(text[start : pos + 1])
    raise ValueError("Could not parse complete JSON object from model output.")


BINARY_SYSTEM_PROMPT = """You are evaluating candidate text spans from news articles.

Decide whether the candidate span itself contains polarizing language.

Use this binary decision:
- polarizing: the span contains inflammatory language or persuasive propaganda.
- not_polarizing: the span is neutral, factual, ordinary context, attribution, or background information.

Rules:
- Judge only the candidate span, using the article text as context.
- Do not infer polarizing language from the general topic alone.
- A factual sentence about a controversy, poll, quote attribution, number, event, or policy can still be not_polarizing.
- Return valid JSON only with keys: decision, confidence, reason.
- decision must be exactly "polarizing" or "not_polarizing".
"""


def build_binary_prompt(article: Article, cluster: Cluster) -> str:
    return (
        "Evaluate this candidate span.\n\n"
        f"Article title: {article.title}\n"
        f"Source: {article.source}\n"
        f"Rating: {article.rating}\n"
        f"Topic: {article.topic}\n"
        f"Paragraph index from source data: {cluster.paragraph_index}\n\n"
        f"Article text:\n{article.body}\n\n"
        f"Candidate span:\n{cluster.representative_span}\n\n"
        'Return JSON like {"decision":"polarizing","confidence":0.91,"reason":"short reason"}'
    )


def normalize_binary_decision(value: Any) -> str:
    text = normalize_label(str(value or ""))
    if text in {"polarizing", "yes", "accept", "true"}:
        return "polarizing"
    if text in {"not polarizing", "not_polarizing", "no", "deny", "false"}:
        return "not_polarizing"
    raise ValueError(f"Unrecognized binary decision: {value!r}")


def retry(call, *, max_retries: int) -> Any:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= max_retries:
                raise
            time.sleep(1.0 * (2**attempt) + random.random() * 0.25)
    raise last_exc or RuntimeError("Retry failed without exception")


def apply_openai_binary_votes(
    clusters: list[Cluster],
    articles_by_title: dict[str, Article],
    *,
    output_csv: Path,
    raw_jsonl: Path,
    models: list[str],
    temperature: float | None,
    max_retries: int,
    resume: bool,
) -> list[dict[str, Any]]:
    load_dotenv_if_present()
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for --validator-mode openai")
    from openai import OpenAI

    client = OpenAI()
    previous: dict[tuple[str, str], dict[str, Any]] = {}
    if resume and output_csv.exists():
        with output_csv.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                previous[(row["cluster_id"], row["validator"])] = row

    rows: list[dict[str, Any]] = list(previous.values())
    completed = set(previous)
    raw_mode = "a" if resume and raw_jsonl.exists() else "w"
    raw_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with raw_jsonl.open(raw_mode, encoding="utf-8") as raw_handle:
        for cluster in clusters:
            article = articles_by_title.get(cluster.norm_title)
            if article is None:
                continue
            cluster.binary_votes = []
            for model in models:
                key = (cluster.cluster_id, model)
                if key in completed:
                    row = previous[key]
                    cluster.binary_votes.append(
                        BinaryVote(
                            cluster_id=cluster.cluster_id,
                            validator=model,
                            decision=str(row["decision"]),
                            confidence=float(row["confidence"]),
                            weight=float(row["weight"]),
                            reason=str(row.get("reason", "")),
                            matching_span=cluster.representative_span,
                        )
                    )
                    continue

                request_kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": BINARY_SYSTEM_PROMPT},
                        {"role": "user", "content": build_binary_prompt(article, cluster)},
                    ],
                    "response_format": {"type": "json_object"},
                }
                if temperature is not None:
                    request_kwargs["temperature"] = temperature

                def _call() -> Any:
                    return client.chat.completions.create(**request_kwargs)

                completion = retry(_call, max_retries=max_retries)
                raw = completion.choices[0].message.content or ""
                obj = extract_json_from_text(raw)
                decision = normalize_binary_decision(obj.get("decision"))
                confidence = max(0.0, min(1.0, float(obj.get("confidence") or 0.0)))
                vote = BinaryVote(
                    cluster_id=cluster.cluster_id,
                    validator=model,
                    decision=decision,
                    confidence=confidence,
                    weight=1.0,
                    reason=normalize_space(str(obj.get("reason") or "")),
                    matching_span=cluster.representative_span,
                )
                row = asdict(vote)
                rows.append(row)
                cluster.binary_votes.append(vote)
                write_csv(output_csv, rows)
                raw_handle.write(
                    json.dumps(
                        {"cluster_id": cluster.cluster_id, "validator": model, "raw_response": raw, "parsed": obj},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                raw_handle.flush()

            total_weight = sum(vote.weight for vote in cluster.binary_votes)
            yes_score = sum(vote.yes_contribution for vote in cluster.binary_votes)
            cluster.accept_score = round(yes_score / total_weight, 6) if total_weight else 0.0
    return rows


def matching_label_candidates(cluster: Cluster, label_candidates: list[Candidate]) -> list[Candidate]:
    return [
        candidate
        for candidate in label_candidates
        if candidate.norm_title == cluster.norm_title
        and candidate.paragraph_index == cluster.paragraph_index
        and spans_match(candidate, {"text": cluster.representative_span, "paragraphIndex": cluster.paragraph_index}, title=cluster.article_title)
    ]


def choose_label(candidates: list[Candidate]) -> tuple[str, str, str]:
    scores: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        key = (canonical_category(candidate.category), canonical_subcategory(candidate.subcategory))
        bucket = scores.setdefault(
            key,
            {"weight": 0.0, "count": 0, "feedback": [], "source_weights": []},
        )
        bucket["weight"] += candidate.source_weight
        bucket["count"] += 1
        bucket["source_weights"].append(candidate.source_weight)
        if candidate.open_feedback:
            bucket["feedback"].append(candidate.open_feedback)

    if not scores:
        return "Persuasive Propaganda", "exaggeration", "No label votes were available; defaulted deterministically."

    best_key, best_value = max(
        scores.items(),
        key=lambda item: (
            item[1]["weight"],
            item[1]["count"],
            max(item[1]["source_weights"] or [0.0]),
            item[0][0],
            item[0][1],
        ),
    )
    feedback = best_value["feedback"][0] if best_value["feedback"] else "Selected by weighted label vote."
    return best_key[0], best_key[1], feedback


def apply_cluster_labels(
    clusters: list[Cluster],
    label_candidates: list[Candidate],
    *,
    use_label_refinement: bool,
) -> None:
    for cluster in clusters:
        label_pool = list(cluster.candidates)
        if use_label_refinement:
            # Prompt 4-style labelers are evidence, not an override. Keeping
            # cluster votes in the pool prevents a high-precision label source
            # from lowering recall-aligned labels when it disagrees alone.
            label_pool.extend(matching_label_candidates(cluster, label_candidates))
        category, subcategory, feedback = choose_label(label_pool)
        cluster.final_category = category
        cluster.final_subcategory = subcategory
        cluster.final_open_feedback = feedback
        cluster.representative_span = choose_representative_span(label_pool)


def make_npl_annotation(paragraph_index: int) -> dict[str, Any]:
    return {
        "text": NPL_TEXT,
        "category": NPL_CATEGORY,
        "subcategory": NPL_SUBCATEGORY,
        "openFeedback": "No polarizing language detected in this paragraph.",
        "paragraphIndex": paragraph_index,
    }


def materialize_final_articles(
    articles: list[Article],
    clusters: list[Cluster],
    *,
    threshold_by_title: dict[str, float],
    label_candidates: list[Candidate],
    use_label_refinement: bool,
) -> list[dict[str, Any]]:
    apply_cluster_labels(clusters, label_candidates, use_label_refinement=use_label_refinement)
    accepted_by_title_para: dict[tuple[str, int], list[Cluster]] = {}
    for cluster in clusters:
        threshold = threshold_by_title.get(cluster.norm_title, threshold_by_title.get("*", 0.5))
        cluster.accepted = cluster.accept_score >= threshold
        if not cluster.accepted:
            continue
        accepted_by_title_para.setdefault((cluster.norm_title, cluster.paragraph_index), []).append(cluster)

    final_articles: list[dict[str, Any]] = []
    for article in articles:
        annotations: list[dict[str, Any]] = []
        for pidx in range(len(article.paragraphs)):
            clusters_for_para = accepted_by_title_para.get((article.norm_title, pidx), [])
            if not clusters_for_para:
                annotations.append(make_npl_annotation(pidx))
                continue
            for cluster in sorted(clusters_for_para, key=lambda c: (normalize_span(c.representative_span), c.cluster_id)):
                annotations.append(
                    {
                        "text": cluster.representative_span,
                        "category": cluster.final_category,
                        "subcategory": cluster.final_subcategory,
                        "openFeedback": cluster.final_open_feedback,
                        "paragraphIndex": pidx,
                    }
                )

        final_articles.append(
            {
                "title": article.title,
                "topic": article.topic,
                "source": article.source,
                "rating": article.rating,
                "annotations": annotations,
            }
        )
    return final_articles


def polarizing_only(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for article in articles:
        row = dict(article)
        row["annotations"] = [ann for ann in article.get("annotations", []) if not is_npl(ann)]
        out.append(row)
    return out


def flatten_articles(data: list[dict[str, Any]], *, include_npl: bool) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for article in data:
        title = str(article.get("title") or "UNKNOWN_TITLE")
        annotations = list(article.get("annotations") or article.get("items") or [])
        if not include_npl:
            annotations = [ann for ann in annotations if not is_npl(ann)]
        out[normalize_title(title)] = {"title": title, "annotations": annotations}
    return out


def greedy_match(
    predicted: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    match_fn,
) -> tuple[list[tuple[int, int]], set[int], set[int]]:
    pairs: list[tuple[int, int]] = []
    used_gold: set[int] = set()
    unmatched_pred = set(range(len(predicted)))
    for pred_idx, pred_ann in enumerate(predicted):
        for gold_idx, gold_ann in enumerate(gold):
            if gold_idx in used_gold:
                continue
            if match_fn(pred_ann, gold_ann):
                pairs.append((pred_idx, gold_idx))
                used_gold.add(gold_idx)
                unmatched_pred.discard(pred_idx)
                break
    unmatched_gold = set(range(len(gold))) - used_gold
    return pairs, unmatched_pred, unmatched_gold


def npl_aware_match(pred_ann: dict[str, Any], gold_ann: dict[str, Any], title: str) -> bool:
    pred_npl = is_npl(pred_ann)
    gold_npl = is_npl(gold_ann)
    if pred_npl and gold_npl:
        return pred_ann.get("paragraphIndex") == gold_ann.get("paragraphIndex")
    if pred_npl or gold_npl:
        return False
    return bool(
        COMP.spans_match(
            pred_ann.get("text", ""),
            gold_ann.get("text", ""),
            title,
            title,
            pred_ann.get("paragraphIndex"),
            gold_ann.get("paragraphIndex"),
        )
    )


def f1(precision: float, recall: float) -> float:
    return (2 * precision * recall / (precision + recall)) if precision + recall else 0.0


def strict_metric(correct: int, prediction_total: int, gold_total: int) -> dict[str, Any]:
    precision = correct / prediction_total if prediction_total else 0.0
    recall = correct / gold_total if gold_total else 0.0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1(precision, recall), 3),
        "correct": correct,
        "prediction_total": prediction_total,
        "gold_total": gold_total,
    }


def compare_predictions(
    predicted_articles: list[dict[str, Any]],
    gold_articles: list[dict[str, Any]],
    *,
    include_npl: bool,
    title_filter: set[str] | None = None,
    title_policy: str = "gold_nonempty",
) -> dict[str, Any]:
    pred = flatten_articles(predicted_articles, include_npl=include_npl)
    gold = flatten_articles(gold_articles, include_npl=include_npl)
    titles = sorted(set(pred) & set(gold))
    if title_filter is not None:
        titles = [title for title in titles if title in title_filter]
    if title_policy == "gold_nonempty":
        titles = [title for title in titles if gold[title]["annotations"]]
    elif title_policy != "all_shared":
        raise ValueError(f"Unknown title_policy: {title_policy}")

    matched = 0
    prediction_total = 0
    gold_total = 0
    category_correct = 0
    subcategory_correct = 0
    per_article: dict[str, Any] = {}
    for title in titles:
        pred_article = pred[title]
        gold_article = gold[title]
        pred_annotations = pred_article["annotations"]
        gold_annotations = gold_article["annotations"]
        match_fn = (
            (lambda p, g, t=title: npl_aware_match(p, g, t))
            if include_npl
            else (
                lambda p, g, t=title: bool(
                    COMP.spans_match(
                        p.get("text", ""),
                        g.get("text", ""),
                        t,
                        t,
                        p.get("paragraphIndex"),
                        g.get("paragraphIndex"),
                    )
                )
            )
        )
        pairs, unmatched_pred, unmatched_gold = greedy_match(pred_annotations, gold_annotations, match_fn)
        prediction_total += len(pred_annotations)
        gold_total += len(gold_annotations)
        matched += len(pairs)
        article_category_correct = 0
        article_subcategory_correct = 0
        for pred_idx, gold_idx in pairs:
            pred_ann = pred_annotations[pred_idx]
            gold_ann = gold_annotations[gold_idx]
            if canonical_category(pred_ann.get("category")) == canonical_category(gold_ann.get("category")):
                category_correct += 1
                article_category_correct += 1
            if canonical_subcategory(pred_ann.get("subcategory")) == canonical_subcategory(gold_ann.get("subcategory")):
                subcategory_correct += 1
                article_subcategory_correct += 1
        per_article[gold_article["title"]] = {
            "matched": len(pairs),
            "prediction_total": len(pred_annotations),
            "gold_total": len(gold_annotations),
            "prediction_only": len(unmatched_pred),
            "gold_only": len(unmatched_gold),
            "category_correct": article_category_correct,
            "subcategory_correct": article_subcategory_correct,
        }

    span_precision = matched / prediction_total if prediction_total else 0.0
    span_recall = matched / gold_total if gold_total else 0.0
    return {
        "titles_compared": len(titles),
        "polarization_match": {
            "precision": round(span_precision, 3),
            "recall": round(span_recall, 3),
            "f1": round(f1(span_precision, span_recall), 3),
            "correct": matched,
            "prediction_total": prediction_total,
            "gold_total": gold_total,
        },
        "category_match": strict_metric(category_correct, prediction_total, gold_total),
        "subcategory_match": strict_metric(subcategory_correct, prediction_total, gold_total),
        "label_agreement_on_matched": {
            "category": round(category_correct / matched, 3) if matched else 0.0,
            "subcategory": round(subcategory_correct / matched, 3) if matched else 0.0,
            "matched": matched,
        },
        "per_article": per_article,
    }


def best_threshold_for_titles(
    articles: list[Article],
    clusters: list[Cluster],
    label_candidates: list[Candidate],
    gold_articles: list[dict[str, Any]],
    *,
    thresholds: list[float],
    train_titles: set[str],
) -> float:
    best = thresholds[0]
    best_key = (-1.0, -1.0, 0.0)
    for threshold in thresholds:
        final_articles = materialize_final_articles(
            articles,
            clusters,
            threshold_by_title={"*": threshold},
            label_candidates=label_candidates,
            use_label_refinement=True,
        )
        metrics = compare_predictions(
            final_articles,
            gold_articles,
            include_npl=True,
            title_filter=train_titles,
        )
        polar = metrics["polarization_match"]
        key = (polar["f1"], polar["recall"], -threshold)
        if key > best_key:
            best_key = key
            best = threshold
    return best


def select_thresholds(
    articles: list[Article],
    clusters: list[Cluster],
    label_candidates: list[Candidate],
    gold_articles: list[dict[str, Any]],
    *,
    thresholds: list[float],
    fixed_threshold: float,
    auto_threshold: bool,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    if not auto_threshold:
        return {"*": fixed_threshold}, [{"mode": "fixed", "threshold": fixed_threshold}]

    gold_by_title = flatten_articles(gold_articles, include_npl=True)
    norm_titles = [article.norm_title for article in articles if gold_by_title.get(article.norm_title, {}).get("annotations")]
    all_train_titles = set(norm_titles)
    threshold_by_title: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for holdout_title in norm_titles:
        train_titles = all_train_titles - {holdout_title}
        chosen = best_threshold_for_titles(
            articles,
            clusters,
            label_candidates,
            gold_articles,
            thresholds=thresholds,
            train_titles=train_titles,
        )
        threshold_by_title[holdout_title] = chosen
        rows.append({"mode": "leave_one_article_out", "held_out_title": holdout_title, "threshold": chosen})

    overall = best_threshold_for_titles(
        articles,
        clusters,
        label_candidates,
        gold_articles,
        thresholds=thresholds,
        train_titles=all_train_titles,
    )
    threshold_by_title["*"] = overall
    rows.append({"mode": "overall_best_reference", "held_out_title": "*", "threshold": overall})
    return threshold_by_title, rows


def cluster_record(cluster: Cluster, *, threshold: float) -> dict[str, Any]:
    source_votes: list[dict[str, Any]] = []
    for source in sorted(cluster.source_names()):
        spans = [candidate.text for candidate in cluster.candidates if candidate.source_name == source]
        labels = [
            f"{candidate.category}/{candidate.subcategory}"
            for candidate in cluster.candidates
            if candidate.source_name == source
        ]
        source_votes.append({"source": source, "spans": spans, "labels": labels})

    return {
        "cluster_id": cluster.cluster_id,
        "article_title": cluster.article_title,
        "paragraphIndex": cluster.paragraph_index,
        "candidate_spans": cluster.candidate_spans(),
        "source_model_votes": source_votes,
        "representative_span": cluster.representative_span,
        "binary_votes": [asdict(vote) for vote in cluster.binary_votes],
        "accept_score": cluster.accept_score,
        "accepted": cluster.accept_score >= threshold,
        "final_category": cluster.final_category,
        "final_subcategory": cluster.final_subcategory,
    }


def cluster_decision_rows(clusters: list[Cluster], threshold_by_title: dict[str, float]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster in clusters:
        threshold = threshold_by_title.get(cluster.norm_title, threshold_by_title.get("*", 0.5))
        rows.append(
            {
                "cluster_id": cluster.cluster_id,
                "article_title": cluster.article_title,
                "paragraph_index": cluster.paragraph_index,
                "representative_span": cluster.representative_span,
                "source_count": len(cluster.source_names()),
                "candidate_count": len(cluster.candidates),
                "accept_score": cluster.accept_score,
                "threshold": threshold,
                "accepted": cluster.accept_score >= threshold,
                "final_category": cluster.final_category,
                "final_subcategory": cluster.final_subcategory,
                "sources": "|".join(sorted(cluster.source_names())),
            }
        )
    return rows


def ablation_row(name: str, predicted: list[dict[str, Any]], gold: list[dict[str, Any]]) -> dict[str, Any]:
    npl = compare_predictions(predicted, gold, include_npl=True)
    polar = compare_predictions(predicted, gold, include_npl=False)
    return {
        "ablation": name,
        "npl_polarization_precision": npl["polarization_match"]["precision"],
        "npl_polarization_recall": npl["polarization_match"]["recall"],
        "npl_polarization_f1": npl["polarization_match"]["f1"],
        "npl_category_precision": npl["category_match"]["precision"],
        "npl_category_recall": npl["category_match"]["recall"],
        "npl_category_f1": npl["category_match"]["f1"],
        "npl_subcategory_precision": npl["subcategory_match"]["precision"],
        "npl_subcategory_recall": npl["subcategory_match"]["recall"],
        "npl_subcategory_f1": npl["subcategory_match"]["f1"],
        "polarizing_span_precision": polar["polarization_match"]["precision"],
        "polarizing_span_recall": polar["polarization_match"]["recall"],
        "polarizing_span_f1": polar["polarization_match"]["f1"],
        "polarizing_category_agreement_on_matched": polar["label_agreement_on_matched"]["category"],
        "polarizing_subcategory_agreement_on_matched": polar["label_agreement_on_matched"]["subcategory"],
    }


def build_ablation_rows(
    articles: list[Article],
    clusters: list[Cluster],
    label_candidates: list[Candidate],
    gold_articles: list[dict[str, Any]],
    threshold_by_title: dict[str, float],
    *,
    prompt2_path: Path | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    union_articles = materialize_final_articles(
        articles,
        clusters,
        threshold_by_title={"*": -1.0},
        label_candidates=[],
        use_label_refinement=False,
    )
    rows.append(ablation_row("candidate_union_no_binary_filter", union_articles, gold_articles))

    binary_only_articles = materialize_final_articles(
        articles,
        clusters,
        threshold_by_title=threshold_by_title,
        label_candidates=[],
        use_label_refinement=False,
    )
    rows.append(ablation_row("binary_filter_no_label_refinement", binary_only_articles, gold_articles))

    full_articles = materialize_final_articles(
        articles,
        clusters,
        threshold_by_title=threshold_by_title,
        label_candidates=label_candidates,
        use_label_refinement=True,
    )
    rows.append(ablation_row("full_decision_point_pipeline", full_articles, gold_articles))

    if prompt2_path and prompt2_path.exists():
        rows.append(ablation_row("current_broad_prompt2_adjudication", load_json(prompt2_path), gold_articles))
    return rows


def parse_thresholds(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def default_prompt2_path() -> Path:
    return (
        REPO
        / "src/llm_annotation_results/2-20/npl_prompt_comparison/adjudication_prompt_1_to_5/"
        "prompt_2_dr_bagozzi_temp0p0_run1/final_annotations.json"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run decision-point AI adjudication over existing LLM annotation outputs.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--gold-json", default=str(DEFAULT_GOLD))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--analysis-root", default=str(DEFAULT_ANALYSIS_ROOT))
    parser.add_argument("--candidate-source", action="append", help="NAME=PATH or NAME=PATH:WEIGHT. Defaults to known prompt outputs.")
    parser.add_argument("--label-source", action="append", help="NAME=PATH or NAME=PATH:WEIGHT. Defaults to Prompt 4 label sources.")
    parser.add_argument("--validator-mode", choices=["source-votes", "openai"], default="source-votes")
    parser.add_argument("--binary-validator-model", action="append", default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--thresholds", default=",".join(str(item) for item in THRESHOLDS))
    parser.add_argument("--auto-threshold", action="store_true", default=True)
    parser.add_argument("--fixed-threshold", action="store_false", dest="auto_threshold")
    parser.add_argument("--max-articles", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Do not call external validators; implies --validator-mode source-votes.")
    args = parser.parse_args()

    if args.dry_run:
        args.validator_mode = "source-votes"

    output_root = Path(args.output_root)
    analysis_root = Path(args.analysis_root)
    output_root.mkdir(parents=True, exist_ok=True)
    analysis_root.mkdir(parents=True, exist_ok=True)

    articles = load_articles(Path(args.input), max_articles=args.max_articles)
    article_titles = {article.norm_title for article in articles}
    articles_by_title = {article.norm_title: article for article in articles}
    gold_articles = load_json(Path(args.gold_json))

    candidate_specs = existing_specs(DEFAULT_CANDIDATE_SOURCES, args.candidate_source)
    label_specs = existing_specs(DEFAULT_LABEL_SOURCES, args.label_source)
    if not candidate_specs:
        raise FileNotFoundError("No candidate sources were available.")

    candidates: list[Candidate] = []
    for spec in candidate_specs:
        candidates.extend(load_candidates_from_source(spec, article_titles))
    clusters = cluster_candidates(candidates)

    binary_votes_csv = analysis_root / "binary_validation_votes.csv"
    if args.validator_mode == "source-votes":
        vote_rows = apply_source_votes(clusters, candidate_specs)
        write_csv(binary_votes_csv, vote_rows)
    else:
        models = args.binary_validator_model or ["gpt-5-mini"]
        vote_rows = apply_openai_binary_votes(
            clusters,
            articles_by_title,
            output_csv=binary_votes_csv,
            raw_jsonl=analysis_root / "binary_validation_raw_responses.jsonl",
            models=models,
            temperature=args.temperature,
            max_retries=args.max_retries,
            resume=args.resume,
        )

    label_candidates: list[Candidate] = []
    for spec in label_specs:
        label_candidates.extend(load_candidates_from_source(spec, article_titles))

    thresholds = parse_thresholds(args.thresholds)
    threshold_by_title, threshold_rows = select_thresholds(
        articles,
        clusters,
        label_candidates,
        gold_articles,
        thresholds=thresholds,
        fixed_threshold=args.threshold,
        auto_threshold=args.auto_threshold,
    )

    final_articles = materialize_final_articles(
        articles,
        clusters,
        threshold_by_title=threshold_by_title,
        label_candidates=label_candidates,
        use_label_refinement=True,
    )
    final_polarizing = polarizing_only(final_articles)

    final_json = output_root / "final_annotations.json"
    final_polarizing_json = output_root / "final_annotations_polarizing_only.json"
    write_json(final_json, final_articles)
    write_json(final_polarizing_json, final_polarizing)

    npl_metrics = compare_predictions(final_articles, gold_articles, include_npl=True)
    polarizing_metrics = compare_predictions(final_articles, gold_articles, include_npl=False)
    metrics_summary = {
        "method": "decision-point adjudication",
        "validator_mode": args.validator_mode,
        "candidate_sources": [asdict(spec) | {"path": str(spec.path)} for spec in candidate_specs],
        "label_sources": [asdict(spec) | {"path": str(spec.path)} for spec in label_specs],
        "threshold_selection": threshold_rows,
        "npl_inclusive": npl_metrics,
        "polarizing_only": polarizing_metrics,
        "outputs": {
            "final_annotations": str(final_json),
            "final_annotations_polarizing_only": str(final_polarizing_json),
        },
    }
    write_json(analysis_root / "metrics_summary.json", metrics_summary)
    write_json(analysis_root / "threshold_selection.json", threshold_rows)

    apply_cluster_labels(clusters, label_candidates, use_label_refinement=True)
    cluster_records = [
        cluster_record(cluster, threshold=threshold_by_title.get(cluster.norm_title, threshold_by_title.get("*", args.threshold)))
        for cluster in clusters
    ]
    write_jsonl(analysis_root / "candidate_clusters.jsonl", cluster_records)
    write_csv(analysis_root / "cluster_decisions.csv", cluster_decision_rows(clusters, threshold_by_title))

    ablation_rows = build_ablation_rows(
        articles,
        clusters,
        label_candidates,
        gold_articles,
        threshold_by_title,
        prompt2_path=default_prompt2_path(),
    )
    write_csv(analysis_root / "ablation_summary.csv", ablation_rows)

    print(
        json.dumps(
            {
                "clusters": len(clusters),
                "candidate_annotations": len(candidates),
                "final_annotations": sum(len(article["annotations"]) for article in final_articles),
                "final_polarizing_annotations": sum(len(article["annotations"]) for article in final_polarizing),
                "npl_polarization_match": npl_metrics["polarization_match"],
                "polarizing_span_match": polarizing_metrics["polarization_match"],
                "metrics_summary": str(analysis_root / "metrics_summary.json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
