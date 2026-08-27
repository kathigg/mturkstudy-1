from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "run_decision_point_adjudication.py"
SPEC = importlib.util.spec_from_file_location("decision_point", SCRIPT)
decision_point = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["decision_point"] = decision_point
SPEC.loader.exec_module(decision_point)


class DecisionPointAdjudicationTests(unittest.TestCase):
    def candidate(
        self,
        *,
        source: str,
        title: str = "Example Article",
        paragraph: int = 0,
        text: str,
        category: str = "Inflammatory Language",
        subcategory: str = "name-calling",
        weight: float = 1.0,
    ):
        return decision_point.Candidate(
            source_name=source,
            source_weight=weight,
            article_title=title,
            norm_title=decision_point.normalize_title(title),
            paragraph_index=paragraph,
            text=text,
            category=category,
            subcategory=subcategory,
        )

    def test_clusters_exact_and_partial_span_overlap(self):
        candidates = [
            self.candidate(source="a", text="the deeply corrupt political machine"),
            self.candidate(source="b", text="deeply corrupt political machine"),
            self.candidate(source="c", text="ordinary fiscal policy debate"),
        ]

        clusters = decision_point.cluster_candidates(candidates)

        self.assertEqual(len(clusters), 2)
        self.assertEqual(len(clusters[0].candidates), 2)
        self.assertEqual(len(clusters[1].candidates), 1)

    def test_does_not_cluster_across_articles_or_paragraphs(self):
        candidates = [
            self.candidate(source="a", title="Article A", paragraph=0, text="deeply corrupt political machine"),
            self.candidate(source="b", title="Article B", paragraph=0, text="deeply corrupt political machine"),
            self.candidate(source="c", title="Article A", paragraph=1, text="deeply corrupt political machine"),
        ]

        clusters = decision_point.cluster_candidates(candidates)

        self.assertEqual(len(clusters), 3)

    def test_npl_matches_only_same_paragraph(self):
        pred = [
            {
                "title": "Example Article",
                "annotations": [decision_point.make_npl_annotation(0), decision_point.make_npl_annotation(1)],
            }
        ]
        gold = [
            {
                "title": "Example Article",
                "annotations": [decision_point.make_npl_annotation(0)],
            }
        ]

        metrics = decision_point.compare_predictions(pred, gold, include_npl=True)

        self.assertEqual(metrics["polarization_match"]["correct"], 1)
        self.assertEqual(metrics["polarization_match"]["prediction_total"], 2)
        self.assertEqual(metrics["polarization_match"]["gold_total"], 1)

    def test_source_vote_accept_score_uses_missing_source_as_no_vote(self):
        candidates = [self.candidate(source="a", text="deeply corrupt political machine")]
        clusters = decision_point.cluster_candidates(candidates)
        specs = [
            decision_point.SourceSpec("a", Path("a.json"), 1.0),
            decision_point.SourceSpec("b", Path("b.json"), 1.0),
        ]

        decision_point.apply_source_votes(clusters, specs)

        self.assertEqual(clusters[0].accept_score, 0.5)
        self.assertEqual([vote.decision for vote in clusters[0].binary_votes], ["polarizing", "not_polarizing"])

    def test_label_tie_breaks_by_weight(self):
        candidates = [
            self.candidate(
                source="a",
                text="deeply corrupt political machine",
                category="Persuasive Propaganda",
                subcategory="doubt",
                weight=1.0,
            ),
            self.candidate(
                source="b",
                text="deeply corrupt political machine",
                category="Inflammatory Language",
                subcategory="demonization",
                weight=2.0,
            ),
        ]

        category, subcategory, _ = decision_point.choose_label(candidates)

        self.assertEqual(category, "Inflammatory Language")
        self.assertEqual(subcategory, "demonization")


if __name__ == "__main__":
    unittest.main()
