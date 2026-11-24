import json
import unittest
from unittest.mock import Mock, patch

from agents import analyst_critic_agent as analyst
from agents import validation_agent as validation
from agents.evidence_scoring import CHECKLIST_FIELDS, claim_category, evidence_summary


class ScoringTests(unittest.TestCase):
    def test_treatment_title_cannot_supply_a_causal_quote(self):
        for sentence, expected in (
            ("Suppression of mutant HTT for the treatment of Huntington disease.", "contextual"),
            ("HTT mutations cause Huntington disease, motivating trials for the treatment of Huntington disease.", "direct_claim"),
        ):
            rel = {"gene": "HTT", "disease": "Huntington disease", "sentence": sentence,
                   "causal_label": "causal", "checklist_status": "available",
                   "evidence_checklist": {**dict.fromkeys(CHECKLIST_FIELDS, True), "claim_quote": sentence}}
            self.assertEqual(claim_category(rel), expected)

    def test_retries_rejected_json_and_validates_replacement(self):
        check = {**dict.fromkeys(CHECKLIST_FIELDS, False), "claim_quote": "", "reasoning": "An assumption."}
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = json.dumps(check)
        rejected = RuntimeError("Bad request")
        rejected.body = {"error": {"code": "json_validate_failed"}}
        source = {"gene": "A", "disease": "B", "sentence": "A was assumed to cause B."}
        for first in (rejected, Mock(choices=[])):
            with patch.object(analyst, "client") as service:
                create = service.chat.completions.create
                create.side_effect = [first, response]
                self.assertEqual(analyst.extract_checklist(source), check)
                self.assertEqual(create.call_count, 2)

    def test_invalid_schema_retries_once_and_outages_return_immediately(self):
        source = {"gene": "A", "disease": "B", "sentence": "B was caused by changes in A."}
        for outputs in (["{}", "{}"], [""]):
            with patch.object(analyst, "call_llm", side_effect=outputs) as call:
                self.assertEqual(analyst.extract_checklist(source), {})
                self.assertEqual(call.call_count, len(outputs))

    def test_unavailable_assessment_stays_unscored(self):
        relation = {"gene": "PARP", "disease": "breast cancer", "sentence": "Sample sentence.",
                    "causal_label": "causal", "confidence": 0.7143, "paper_id": "1"}
        for response in ("", "{}", json.dumps(dict.fromkeys(CHECKLIST_FIELDS, "false"))):
            state = {"causal_relations": [relation.copy()]}
            with patch.object(analyst, "call_llm", return_value=response):
                analyst.analyst_agent(state)
            analyst.critic_agent(state)
            result = validation.validation_agent(state)["validated_relations"][0]
            self.assertEqual(result["classification"], "needs_review")
            self.assertIsNone(result["combined_score"])
            self.assertTrue(evidence_summary(result))

    def test_descriptive_and_explicit_statements(self):
        checks = dict.fromkeys(CHECKLIST_FIELDS, False)
        checks["claim_quote"] = ""
        checks["reasoning"] = "The gene was measured in the source sentence."
        with patch.object(analyst, "call_llm", return_value=json.dumps(checks)):
            self.assertEqual(analyst.extract_checklist({"gene": "A", "disease": "B", "sentence": "A B."}), checks)
        rel = {"gene": "A", "disease": "B", "causal_label": "causal", "sentence": "A causes B.",
               "evidence_checklist": checks, "checklist_status": "available"}
        self.assertEqual(claim_category(rel), "contextual")
        checks.update(claim_quote="A causes B.", gene_drives_disease=True, disease_outcome_linked=True)
        self.assertEqual(claim_category(rel), "direct_claim")
        for bad_quote in ("A definitely causes B.", "causes B."):
            checks["claim_quote"] = bad_quote
            self.assertEqual(claim_category(rel), "needs_review")
        rel["contradictions"] = ["123"]
        self.assertEqual(claim_category(rel), "contradicted")
