import unittest
from unittest.mock import patch

from agents import analyst_critic_agent as analyst
from agents import causal_reasoning_agent as screen
from agents.evidence_scoring import claim_category


class PairScreenTests(unittest.TestCase):
    def test_shared_sentence_gets_distinct_predictions_and_retains_sources(self):
        sent = "BRCA1 was measured and TP53 was depleted in breast cancer."
        rows = [dict(gene=gene, disease="breast cancer", sentence=sent, paper_id=pmid)
                for pmid, gene in (("1", "BRCA1"), ("1", "TP53"), ("2", "TP53"))]
        scores = [{"causal_label": label, "confidence": 0.8} for label in ("non-causal", "causal")]
        with patch.object(screen, "predict_causal", side_effect=scores) as predict:
            state = screen.causal_reasoning_agent({"normalized_entities": rows + rows})
        self.assertEqual([call.args[0] for call in predict.call_args_list], [
            "@GeneSrc$ was measured and TP53 was depleted in @DiseaseTgt$.",
            "BRCA1 was measured and @GeneSrc$ was depleted in @DiseaseTgt$."])
        self.assertEqual([r["causal_label"] for r in state["causal_relations"]], ["non-causal", "causal", "causal"])
        self.assertEqual([r["sentence"] for r in state["causal_relations"]], [sent] * 3)

    def test_marker_boundaries_overlap_and_ner_offsets(self):
        self.assertEqual(screen.mark_pair("MET and MET2 met cancer.", "MET", "cancer"),
                         "@GeneSrc$ and MET2 met @DiseaseTgt$.")
        self.assertIsNone(screen.mark_pair("BRCA1 deficiency.", "BRCA1", "BRCA1 deficiency"))
        self.assertIsNone(screen.mark_pair("MET2 and cancer.", "MET", "cancer"))
        sent = "BRCA1 and cancer versus breast cancer."
        self.assertEqual(screen.mark_pair(sent, "BRCA1", "cancer", [(10, 16)]),
                         "@GeneSrc$ and @DiseaseTgt$ versus breast cancer.")

    def test_overlength_does_not_score_a_truncated_passage(self):
        result = screen.predict_causal("@GeneSrc$ " + "word " * 520 + "@DiseaseTgt$")
        self.assertEqual(result["causal_label"], "unresolved")
        self.assertIsNone(result["confidence"])

    def test_quote_budget_preserves_overflow(self):
        rows = [dict(gene="TP53", disease="cancer", sentence="TP53 drives cancer.", paper_id=str(i))
                for i in range(52)]
        with patch.object(screen, "predict_causal", return_value={"causal_label": "causal", "confidence": 0.8}):
            state = screen.causal_reasoning_agent({"normalized_entities": rows})
        with patch.object(analyst, "extract_checklist", return_value={}) as extract:
            analyst.analyst_agent(state)
        self.assertEqual(len(state["causal_relations"]), 52)
        self.assertEqual(extract.call_count, 50)
        self.assertEqual(state["causal_relations"][-1]["checklist_status"], "not_assessed")
        self.assertEqual(claim_category(state["causal_relations"][-1]), "needs_review")
