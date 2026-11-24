import re
from state import PipelineState

def find_conflicts(gene: str, disease: str, source_paper_id: str, papers: list, original_gene: str = "") -> list:
    names = {name for name in (gene, original_gene) if name}
    if not names or not disease:
        return []
    gene_term = r"(?<!\w)(?:" + "|".join(re.escape(name) for name in sorted(names)) + r")(?!\w)"
    disease_term = r"(?<!\w)" + re.escape(disease) + r"(?!\w)"
    subject = gene_term + r"(?:\s+(?:mutations?|variants?|expression|loss|deficiency))?"
    denial = r"(?:did|does|do)\s+not\s+(?:directly\s+)?cause|(?:is|was|are|were)\s+not\s+(?:a\s+cause\s+of|responsible\s+for)"
    between = r"no\s+(?:direct\s+)?causal\s+(?:link|relationship|association)\s+between\s+"
    patterns = [
        re.compile(subject + r"\s+(?:" + denial + r")\s+" + disease_term, re.I),
        re.compile(between + gene_term + r"\s+and\s+" + disease_term, re.I),
        re.compile(between + disease_term + r"\s+and\s+" + gene_term, re.I),
    ]
    conflicts = []
    for paper in papers:
        pmid = paper.get("pmid")
        if not pmid or pmid == source_paper_id:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", paper.get("abstract", "")):
            if any(pattern.search(sentence) for pattern in patterns):
                conflicts.append({"paper_id": pmid, "sentence": sentence.strip()})
    return conflicts


def check_contradiction(gene: str, disease: str, source_paper_id: str, papers: list, original_gene: str = "") -> list:
    conflicts = find_conflicts(gene, disease, source_paper_id, papers, original_gene)
    return sorted({entry["paper_id"] for entry in conflicts})


def contradiction_agent(state: PipelineState) -> PipelineState:
    relations = state.get("causal_relations", [])
    papers    = state.get("papers", [])

    if not relations:
        print("[Contradiction Agent] No relations to check.")
        return state

    print(f"[Contradiction Agent] Checking {len(relations)} relations for contradictions...")
    contradicted_count = 0

    for rel in relations:
        if rel.get("causal_label") != "causal":
            continue
        original_gene   = rel.get("gene", "")
        gene            = rel.get("gene_symbol") or original_gene
        disease         = rel.get("disease", "")
        source_paper_id = rel.get("paper_id", "")

        if not gene or not disease:
            continue

        conflicts = find_conflicts(gene, disease, source_paper_id, papers, original_gene)
        rel["conflict_evidence"] = conflicts
        contradictions = sorted({entry["paper_id"] for entry in conflicts})
        rel["contradictions"] = contradictions

        if contradictions:
            contradicted_count += 1
            print(f"  CONTRADICTED: {gene} → {disease} (by papers: {contradictions})")

    print(f"[Contradiction Agent] Found {contradicted_count} contradicted relations")
    state["causal_relations"] = relations
    return state
