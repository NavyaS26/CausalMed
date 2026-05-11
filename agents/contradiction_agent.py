# agents/contradiction_agent.py
# P's work — Agent 7
# Scans all validated relations and flags contradictions.
# A contradiction is when one paper says Gene X CAUSES Disease Y
# and another paper's sentence suggests it does NOT.
# Uses simple keyword-based contradiction detection.

from state import PipelineState

# Keywords that suggest a non-causal or contradictory relationship
CONTRADICTION_KEYWORDS = [
    "no significant", "not associated", "no association",
    "failed to show", "did not cause", "no evidence",
    "not causal", "not linked", "no causal", "contrary",
    "inconsistent", "disputed", "controversial", "unclear",
    "no direct", "not directly", "without evidence"
]

# Keywords that strongly suggest causality
CAUSAL_KEYWORDS = [
    "causes", "leads to", "results in", "drives", "induces",
    "promotes", "triggers", "contributes to", "responsible for",
    "directly causes", "causally linked", "causal role"
]


def check_contradiction(gene: str, disease: str, papers: list) -> list:
    """
    Check if any paper in the corpus contradicts a causal gene-disease link.
    Returns list of contradicting paper IDs.
    """
    contradicting_papers = []
    gene_lower    = gene.lower()
    disease_lower = disease.lower()

    for paper in papers:
        abstract = paper.get("abstract", "").lower()
        pmid     = paper.get("pmid", "")

        # Check if this paper mentions both gene and disease
        if gene_lower not in abstract or disease_lower not in abstract:
            continue

        # Check for contradiction keywords near gene and disease mentions
        for keyword in CONTRADICTION_KEYWORDS:
            if keyword in abstract:
                # Find sentences containing both gene, disease, and contradiction keyword
                sentences = abstract.split('.')
                for sentence in sentences:
                    if (gene_lower in sentence and
                            disease_lower in sentence and
                            keyword in sentence):
                        contradicting_papers.append(pmid)
                        break

    return list(set(contradicting_papers))


def contradiction_agent(state: PipelineState) -> PipelineState:
    """
    LangGraph node function.
    Input:  state["validated_relations"] + state["papers"]
    Output: state["validated_relations"] with contradictions flagged
    """
    relations = state.get("validated_relations", [])
    papers    = state.get("papers", [])

    if not relations:
        print("[Contradiction Agent] No relations to check.")
        return state

    print(f"[Contradiction Agent] Checking {len(relations)} relations for contradictions...")

    contradicted_count = 0

    for i, rel in enumerate(relations):
        gene    = rel.get("gene", "")
        disease = rel.get("disease", "")

        if not gene or not disease:
            continue

        contradictions = check_contradiction(gene, disease, papers)

        if contradictions:
            relations[i]["contradictions"]  = contradictions
            relations[i]["classification"]  = "contradicted"
            contradicted_count += 1
            print(f"  CONTRADICTED: {gene} → {disease} "
                  f"(by papers: {contradictions})")

    print(f"[Contradiction Agent] Found {contradicted_count} contradicted relations")
    state["validated_relations"] = relations
    return state