"""Replay seven audited CRED cases against saved passage predictions.

Expectations describe the selected passage. The original CRED labels describe
the abstract. A benchmark disagreement alone does not adjudicate the passage.
"""
import argparse
import json
from pathlib import Path


# PMID, gene ID, disease ID, identifying text, expected category, audit finding
CASES = [
    ("34440548", "6622", "D010300", "first genetic cause", "direct_claim",
     "The authors identify SNCA mutations as a genetic cause of Parkinson's disease."),
    ("31263285", "15194", "D006816", "disorder caused by", "direct_claim",
     "The sentence attributes Huntington's disease to the gene alteration in passive voice."),
    ("28781905", "6622", "D010300", "can modify the susceptibility", "direct_claim",
     "The conclusion asserts a change in susceptibility. A supporting quotation must preserve that qualification. The earlier screen skipped this sentence."),
    ("25900096", "23400", "C537177", "mutations in this gene cause", "direct_claim",
     "The causal statement names Kufor-Rakeb syndrome. The original service response failed."),
    ("25900096", "23400", "D010300", "mutations in this gene cause", "contextual",
     "The same causal clause names Kufor-Rakeb syndrome. Parkinson's disease is the surrounding topic."),
    ("32603820", "351", "D000544", "currently assumed", "contextual",
     "The authors describe a proposed effect of amyloid peptide on impairments in Alzheimer's disease."),
    ("34440548", "6622", "D009410", "aggregation and accumulation perpetuate", None,
     "The authors attribute ongoing neuronal degeneration to protein aggregation. Preserve the process and its direction. The abstract-level label is negative; the passage has no independent label."),
]


def audit(rows):
    pairs = {tuple(row["key"]): row for row in rows}
    findings = []
    for pmid, gene, disease, anchor, expected, note in CASES:
        row = pairs[pmid, gene, disease]
        matches = [p for p in row["passages"] if anchor in p["source"]]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one passage for {pmid}/{gene}/{disease}: {anchor}")
        passage = matches[0]
        category = passage["category"]
        if expected is None:
            status = "unadjudicated"
        elif category == expected:
            status = "matched"
        else:
            status = "mismatch"
        findings.append(dict(pmid=pmid, gene_id=gene, disease_id=disease, cred_label=row["gold"],
                             note=note, source=passage["source"], expected=expected, actual=category,
                             status=status, assessment_status=passage["checklist_status"],
                             quote=(passage["check"] or {}).get("claim_quote")))
    return findings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    findings = audit(json.loads(args.predictions.read_text(encoding="utf-8")))
    if args.output:
        args.output.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    for record in findings:
        print(record["pmid"], record["disease_id"], record["status"], record["actual"])
    raise SystemExit(int(any(r["status"] == "mismatch" for r in findings)))
