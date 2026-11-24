import gzip
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from agents.evidence_scoring import CHECKLIST_FIELDS
from agents.contradiction_agent import find_conflicts
from agents.mesh_descriptors import read_index
from agents import validation_agent as validation


class EvidenceTests(unittest.TestCase):
    def test_negation_belongs_to_the_named_pair(self):
        papers = [
            {"pmid": "1", "abstract": "TP53 was linked to cancer, but a placebo did not cause nausea."},
            {"pmid": "2", "abstract": "TP53 did not cause cancer."},
        ]
        self.assertEqual(find_conflicts("TP53", "cancer", "3", papers), [
            {"paper_id": "2", "sentence": "TP53 did not cause cancer."}
        ])

    def test_unique_descriptor_and_ambiguous_entry_term(self):
        records = []
        for identifier, label in [("D001", "Condition A"), ("D002", "Condition B")]:
            records.append(f"""<DescriptorRecord><DescriptorUI>{identifier}</DescriptorUI>
                <DescriptorName><String>{label}</String></DescriptorName>
                <ConceptList><Concept><TermList><Term><String>shared term</String></Term></TermList></Concept></ConceptList>
                <TreeNumberList><TreeNumber>C01</TreeNumber></TreeNumberList></DescriptorRecord>""")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "test.gz"
            with gzip.open(path, "wt") as stream:
                stream.write("<DescriptorRecordSet>" + "".join(records) + "</DescriptorRecordSet>")
            index = read_index(path)
        self.assertEqual(index["condition a"]["mesh_id"], "D001")
        self.assertEqual(index["condition a"]["tree_numbers"], ["C01"])
        self.assertIsNone(index["shared term"])

    def test_outage_and_multiple_mentions(self):
        records = [{"gene": "TP53", "disease": "cancer", "paper_id": pmid, "causal_label": "causal"}
                   for pmid in ("1", "1", "2")]
        for record in records:
            record.update(sentence="TP53 drives cancer.", checklist_status="available",
                          evidence_checklist={**dict.fromkeys(CHECKLIST_FIELDS, False), "gene_drives_disease": True,
                                              "disease_outcome_linked": True, "claim_quote": "TP53 drives cancer."})
        with (
            patch.object(validation, "fetch_eutils", side_effect=RuntimeError("offline")),
            patch.object(validation, "_clinvar_cache", {}),
            patch.object(validation, "query_chembl", return_value=[]),
            patch.object(validation, "query_clinical_trials", return_value=[]),
        ):
            result = validation.validation_agent({"causal_relations": records})
        for relation in result["validated_relations"]:
            self.assertEqual(relation["evidence_papers"], ["1", "2"])
            self.assertEqual(relation["evidence_tier"], "direct_claim")
            self.assertEqual(relation["clinvar_status"], "unavailable")
            self.assertIsNone(relation["combined_score"])
