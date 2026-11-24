import json
import os
from datetime import datetime
from state import PipelineState
from agents.evidence_scoring import PAIR_METHOD

try:
    from pyvis.network import Network
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False
    print("[Output Agent] Pyvis not available — skipping graph visualization")


def build_summary(validated_relations: list) -> dict:
    validated    = [r for r in validated_relations if r.get("classification") == "validated"]
    novel        = [r for r in validated_relations if r.get("classification") == "novel_hypothesis"]
    contradicted = [r for r in validated_relations if r.get("classification") == "contradicted"]
    non_causal   = [r for r in validated_relations if r.get("classification") == "non_causal"]
    return {
        "total_relations_analyzed": len(validated_relations),
        "review_count":             sum(r.get("classification") == "needs_review" for r in validated_relations),
        "validated_count":          len(validated),
        "novel_hypothesis_count":   len(novel),
        "contradicted_count":       len(contradicted),
        "non_causal_count":         len(non_causal)
    }


def format_relation(rel: dict) -> dict:
    return {
        "gene":              rel.get("gene_symbol", rel.get("gene", "")),
        "source_gene":       rel.get("gene", ""),
        "disease":           rel.get("disease", ""),
        "causal_label":      rel.get("causal_label", ""),
        "confidence":        rel.get("confidence", 0.0),
        "biobert_label":      rel.get("biobert_label", rel.get("causal_label", "")),
        "biobert_confidence": rel.get("biobert_confidence", rel.get("confidence", 0.0)),
        "disease_category":  rel.get("disease_category", ""),
        "disease_source":    rel.get("disease_source", ""),
        "mesh_id":           rel.get("mesh_id", ""),
        "mesh_label":        rel.get("mesh_label", ""),
        "reliability_score": rel.get("reliability_score", 0.0),
        "classification":    rel.get("classification", ""),
        "validated":         rel.get("validated", False),
        "evidence_count":    rel.get("evidence_count", 1),
        "evidence_papers":   rel.get("evidence_papers", []),
        "conflict_evidence": rel.get("conflict_evidence", []),
        "review_reason":     rel.get("review_reason", ""),
        "claim_quote":       rel.get("claim_quote", ""),
        "clinvar_record_count": rel.get("clinvar_record_count"),
        "clinvar_status":    rel.get("clinvar_status", "unknown"),
        "source_paper":      rel.get("paper_id", ""),
        "source_sentence":   rel.get("sentence", ""),
        "analyst_reasoning": rel.get("analyst_reasoning", ""),
        "critic_feedback":   rel.get("critic_feedback", ""),
        "checklist_status":      rel.get("checklist_status", "unknown"),
        "checklist_score":       rel.get("checklist_score"),
        "checklist_model":       rel.get("checklist_model"),
        "quote_assessment_version": rel.get("quote_assessment_version"),
        "evidence_checklist":    rel.get("evidence_checklist", {}),
        "critic_score":          rel.get("critic_score", 0.0),
        "combined_score":        rel.get("combined_score", 0.0),
        "evidence_tier":         rel.get("evidence_tier", "associative_only"),
        "evidence_tier_label":   rel.get("evidence_tier_label", "Insufficient causal evidence"),
        "needs_review":          rel.get("needs_review", False),
        # FIX: renamed from disgenet_score to clinvar_score
        "clinvar_score":     rel.get("clinvar_score", 0.0),
        "clinical_trials":   rel.get("clinical_trials", []),
        "drug_candidates":   rel.get("drug_candidates", []),
        "contradictions":    rel.get("contradictions", [])
    }


def generate_knowledge_graph(validated_relations: list, chains: list, output_path: str):
    if not PYVIS_AVAILABLE:
        return

    net = Network(height="700px", width="100%", bgcolor="#1a1a2e", font_color="white", directed=True)
    net.set_options("""
    {
        "nodes": {"borderWidth": 2, "size": 20, "font": {"size": 14}},
        "edges": {"arrows": {"to": {"enabled": true}}, "smooth": {"type": "curvedCW", "roundness": 0.2}},
        "physics": {"stabilization": true, "barnesHut": {"gravitationalConstant": -8000}}
    }
    """)

    added_nodes = set()
    for rel in validated_relations:
        if rel.get("evidence_tier") != "direct_claim":
            continue
        gene    = rel.get("gene_symbol", rel.get("gene", ""))
        disease = rel.get("disease", "")
        if gene not in added_nodes:
            net.add_node(gene, label=gene, color="#4a90d9", title=f"Gene: {gene}", shape="dot")
            added_nodes.add(gene)
        if disease not in added_nodes:
            net.add_node(disease, label=disease, color="#e74c3c", title=f"Disease: {disease}", shape="diamond")
            added_nodes.add(disease)
        net.add_edge(gene, disease, color="#00ff88",
                     title=f"Model score: {rel.get('confidence', 0):.2f} | Explicit causal statement", width=2)

    net.save_graph(output_path)
    print(f"[Output Agent] Knowledge graph saved to {output_path}")


def output_agent(state: PipelineState) -> PipelineState:
    validated_relations = state.get("validated_relations", [])
    chains              = state.get("chains", [])
    query               = state.get("user_query", "")

    print("[Output Agent] Generating final output...")

    validated    = [format_relation(r) for r in validated_relations if r.get("classification") == "validated"]
    novel        = [format_relation(r) for r in validated_relations if r.get("classification") == "novel_hypothesis"]
    contradicted = [format_relation(r) for r in validated_relations if r.get("classification") == "contradicted"]
    # FIX: expose non-causal relations so the UI can display them correctly
    non_causal   = [format_relation(r) for r in validated_relations if r.get("classification") == "non_causal"]

    final_output = {
        "evidence_method": PAIR_METHOD,
        "query":     query,
        "timestamp": datetime.now().isoformat(),
        "summary":   build_summary(validated_relations),
        "validated_findings":    validated,
        "novel_hypotheses":      novel,
        "contradicted_findings": contradicted,
        "non_causal_findings":   non_causal,
        "review_findings": [format_relation(r) for r in validated_relations if r.get("classification") == "needs_review"],
        "causal_chains":         chains,
        "drug_candidates": list({
            drug for r in validated_relations
            for drug in r.get("drug_candidates", []) if drug
        }),
        "clinical_trials": list({
            trial for r in validated_relations
            for trial in r.get("clinical_trials", []) if trial
        })
    }

    output_dir = os.path.join(os.path.dirname(__file__), '..', 'outputs')
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, f"causalmed_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(json_path, 'w') as f:
        json.dump(final_output, f, indent=2)
    print(f"[Output Agent] JSON saved to {json_path}")

    graph_path = os.path.join(output_dir, "knowledge_graph.html")
    generate_knowledge_graph(validated_relations, chains, graph_path)

    state["final_output"] = final_output
    return state
