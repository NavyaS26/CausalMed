"""Compare same-sentence search with the production quote checker on CRED test data."""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.analyst_critic_agent import MODEL, extract_checklist
from agents.evidence_scoring import claim_category


def load_pairs(path):
    pairs = {}
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            key = (row["index"], row["id1"], row["id2"])
            gold = int(row["label"])
            pair = pairs.setdefault(key, {"gold": gold, "sentences": set(), "same_sentence": False})
            if gold != pair["gold"]:
                raise ValueError(f"Conflicting labels for {key}")
            pair["same_sentence"] |= row["is_in_same_sent"] == "True"
            for sentence in re.split(r"(?<=[.!?])\s+", row["sentence"]):
                if "@GeneSrc$" in sentence and "@DiseaseTgt$" in sentence:
                    pair["sentences"].add(sentence)
    return pairs


def measure(rows, field):
    counts = Counter()
    for row in rows:
        gold, found = row["gold"], row[field]
        counts[("tp" if found else "fn") if gold else ("fp" if found else "tn")] += 1
    tp, fp, fn = (counts[key] for key in ("tp", "fp", "fn"))
    return {**{k: counts[k] for k in ("tp", "fp", "fn", "tn")},
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None}


def sample_order(key):
    return hashlib.sha256("|".join(("cred-pilot-v1", *key)).encode()).digest()


def check_pair_screen(fresh, pairs, output_dir):
    """Run the production screen and quote checker on a fixed set of paper/pair records."""
    from agents.causal_reasoning_agent import causal_reasoning_agent
    from agents.analyst_critic_agent import analyst_agent

    entities = []
    for row in fresh:
        for text in sorted(pairs[row["key"]]["sentences"]):
            sentence = text.replace("@GeneSrc$", "TargetGene").replace("@DiseaseTgt$", "TargetDisease")
            entities.append(dict(gene="TargetGene", disease="TargetDisease", sentence=sentence,
                                 paper_id=row["key"][0]))
    state = causal_reasoning_agent({"normalized_entities": entities})
    for pmid in sorted({r["paper_id"] for r in state["causal_relations"]}):
        paper_relations = [r for r in state["causal_relations"] if r["paper_id"] == pmid]
        analyst_agent({"causal_relations": paper_relations})
    passages = {(r["paper_id"], r["sentence"]): r for r in state["causal_relations"]}
    for row in fresh:
        assessments = []
        for text in sorted(pairs[row["key"]]["sentences"]):
            sentence = text.replace("@GeneSrc$", "TargetGene").replace("@DiseaseTgt$", "TargetDisease")
            rel = passages[row["key"][0], sentence]
            assessments.append({"source": text, "screen": rel["causal_label"],
                                "category": claim_category(rel), "confidence": rel["confidence"],
                                "checklist_status": rel.get("checklist_status"), "check": rel.get("evidence_checklist")})
        row["passages"] = assessments
        row["screen"] = any(p["screen"] == "causal" for p in assessments)
        row["direct"] = any(p["category"] == "direct_claim" for p in assessments)
        row["review_only"] = not row["direct"] and any(p["category"] == "needs_review" for p in assessments)
    result = {"pmids": sorted({r["key"][0] for r in fresh}), "pairs": len(fresh), "model": MODEL,
              "simple_search": measure(fresh, "baseline"), "pair_screen": measure(fresh, "screen"),
              "explicit_claims": measure(fresh, "direct"),
              "review_only_pairs": sum(r["review_only"] for r in fresh),
              "direct_or_review_pairs": sum(r["direct"] or r["review_only"] for r in fresh),
              "passage_categories": dict(Counter(claim_category(r) for r in passages.values())),
              "missing_assessments": sum(r.get("checklist_status") == "unavailable" for r in passages.values())}
    (output_dir / "fresh_predictions.json").write_text(json.dumps(fresh, indent=2), encoding="utf-8")
    (output_dir / "fresh_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("test_file", type=Path)
    parser.add_argument("output_dir", type=Path)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--pair-screen", action="store_true", help="Evaluate pair screening and quotes on non-pilot PMIDs")
    selection.add_argument("--validation-against", type=Path, metavar="TEST_FILE",
                           help="Evaluate eight deterministic validation PMIDs absent from TEST_FILE")
    selection.add_argument("--audit-from", type=Path, metavar="PREDICTIONS",
                           help="Replay screen-positive misses and disputed direct claims from a saved comparison")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pairs = load_pairs(args.test_file)
    rows = [{"key": key, "gold": pair["gold"], "baseline": bool(pair["sentences"]),
             "dataset_same_sentence": pair["same_sentence"]}
            for key, pair in sorted(pairs.items(), key=lambda item: sample_order(item[0]))]
    if args.pair_screen:
        pilot_pmids = {r["key"][0] for r in rows[:100]}
        check_pair_screen([r for r in rows if r["key"][0] not in pilot_pmids], pairs, args.output_dir)
        return
    if args.validation_against:
        excluded = {k[0] for k in load_pairs(args.validation_against)}
        eligible = {k[0] for k in pairs} - excluded
        pmids = sorted(eligible, key=lambda p: hashlib.sha256(("quote-audit-v1|" + p).encode()).digest())[:8]
        check_pair_screen([r for r in rows if r["key"][0] in pmids], pairs, args.output_dir)
        return
    if args.audit_from:
        previous = json.loads(args.audit_from.read_text(encoding="utf-8"))
        keys = {tuple(r["key"]) for r in previous if r["screen"] and bool(r["gold"]) != r["direct"]}
        check_pair_screen([r for r in rows if r["key"] in keys], pairs, args.output_dir)
        return
    sample = rows[:100]
    cache = {}
    for row in sample:
        for text in sorted(pairs[row["key"]]["sentences"]):
            if text in cache:
                continue
            sentence = text.replace("@GeneSrc$", "TargetGene").replace("@DiseaseTgt$", "TargetDisease")
            relation = {"sentence": sentence, "gene": "TargetGene", "disease": "TargetDisease",
                        "causal_label": "causal"}  # Pass every candidate through the quote checker.
            check = extract_checklist(relation)
            relation.update(evidence_checklist=check, checklist_status="available" if check else "unavailable")
            cache[text] = {"category": claim_category(relation), "check": check}
            if len(cache) >= 3 and not any(item["check"] for item in cache.values()):
                raise RuntimeError("No usable service responses in the first three calls.")
        row["passages"] = [{"masked_source": text, **cache[text]} for text in sorted(pairs[row["key"]]["sentences"])]
        categories = [item["category"] for item in row["passages"]]
        row["direct"] = "direct_claim" in categories
        row["review_only"] = not row["direct"] and "needs_review" in categories
    workload = Counter(item["category"] for row in sample for item in row["passages"])
    result = {"test_sha256": hashlib.sha256(args.test_file.read_bytes()).hexdigest(), "model": MODEL,
              "full_pairs": len(rows), "full_baseline": measure(rows, "baseline"),
              "dataset_same_sentence": measure(rows, "dataset_same_sentence"),
              "sample_pairs": len(sample), "sample_pmids": len({row["key"][0] for row in sample}),
              "sample_baseline": measure(sample, "baseline"), "sample_quote_checker": measure(sample, "direct"),
              "pair_passages": dict(workload), "review_only_pairs": sum(row["review_only"] for row in sample),
              "distinct_requests": len(cache), "missing_responses": sum(not item["check"] for item in cache.values())}
    for filename, data in (("summary.json", result), ("pilot_predictions.json", sample)):
        (args.output_dir / filename).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
