# agents/output_agent.py
# P's work — Agent 8
# Takes all validated relations, chains, and drug candidates
# and formats everything into a clean structured JSON output.
# Also generates a Pyvis interactive knowledge graph HTML file.

import json
import os
from datetime import datetime
from state import PipelineState

try:
    from pyvis.network import Network
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False
    print("[Output Agent] Pyvis not available — skipping graph visualization")


def build_summary(validated_relations: list) -> dict:
    """Build a summary of findings."""
    validated      = [r for r in validated_relations if r.get("classification") == "validated"]
    novel          = [r for r in validated_relations if r.get("classification") == "novel_hypothesis"]
    contradicted   = [r for r in validated_relations if r.get("classification") == "contradicted"]
    non_causal     = [r for r in validated_relations if r.get("classification") == "non_causal"]

    return {
        "total_relations_analyzed": len(validated_relations),
        "validated_count":          len(validated),
        "novel_hypothesis_count":   len(novel),
        "contradicted_count":       len(contradicted),
        "non_causal_count":         len(non_causal)
    }


def format_relation(rel: dict) -> dict:
    """Format a single relation for output."""
    return {
        "gene":              rel.get("gene_symbol", rel.get("gene", "")),
        "disease":           rel.get("disease", ""),
        "causal_label":      rel.get("causal_label", ""),
        "confidence":        rel.get("confidence", 0.0),
        "reliability_score": rel.get("reliability_score", 0.0),
        "classification":    rel.get("classification", ""),
        "evidence_count":    rel.get("evidence_count", 1),
        "source_paper":      rel.get("paper_id", ""),
        "source_sentence":   rel.get("sentence", ""),
        "analyst_reasoning": rel.get("analyst_reasoning", ""),
        "critic_feedback":   rel.get("critic_feedback", ""),
        "db_score":          rel.get("disgenet_score", 0.0),
        "clinical_trials":   rel.get("clinical_trials", []),
        "drug_candidates":   rel.get("drug_candidates", []),
        "contradictions":    rel.get("contradictions", [])
    }


def generate_knowledge_graph(validated_relations: list, chains: list, output_path: str):
    """Generate interactive Pyvis knowledge graph HTML."""
    if not PYVIS_AVAILABLE:
        return

    net = Network(
        height="700px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="white",
        directed=True
    )

    net.set_options("""
    {
        "nodes": {
            "borderWidth": 2,
            "size": 20,
            "font": {"size": 14}
        },
        "edges": {
            "arrows": {"to": {"enabled": true}},
            "smooth": {"type": "curvedCW", "roundness": 0.2}
        },
        "physics": {
            "stabilization": true,
            "barnesHut": {"gravitationalConstant": -8000}
        }
    }
    """)

    added_nodes = set()

    for rel in validated_relations:
        if rel.get("causal_label") != "causal":
            continue

        gene    = rel.get("gene_symbol", rel.get("gene", ""))
        disease = rel.get("disease", "")
        cls     = rel.get("classification", "novel_hypothesis")

        # Color by classification
        edge_color = "#00ff88" if cls == "validated" else \
                     "#ffaa00" if cls == "novel_hypothesis" else "#ff4444"

        # Add gene node
        if gene not in added_nodes:
            net.add_node(
                gene,
                label=gene,
                color="#4a90d9",
                title=f"Gene: {gene}",
                shape="dot"
            )
            added_nodes.add(gene)

        # Add disease node
        if disease not in added_nodes:
            net.add_node(
                disease,
                label=disease,
                color="#e74c3c",
                title=f"Disease: {disease}",
                shape="diamond"
            )
            added_nodes.add(disease)

        # Add edge
        net.add_edge(
            gene,
            disease,
            color=edge_color,
            title=f"Confidence: {rel.get('confidence', 0):.2f} | {cls}",
            width=2
        )

    net.save_graph(output_path)
    print(f"[Output Agent] Knowledge graph saved to {output_path}")


def output_agent(state: PipelineState) -> PipelineState:
    """
    LangGraph node function — Final output.
    Formats everything into structured JSON + generates knowledge graph.
    """
    validated_relations = state.get("validated_relations", [])
    chains              = state.get("chains", [])
    query               = state.get("user_query", "")

    print("[Output Agent] Generating final output...")

    # Separate by classification
    validated    = [format_relation(r) for r in validated_relations
                    if r.get("classification") == "validated"]
    novel        = [format_relation(r) for r in validated_relations
                    if r.get("classification") == "novel_hypothesis"]
    contradicted = [format_relation(r) for r in validated_relations
                    if r.get("classification") == "contradicted"]

    # Build final output
    final_output = {
        "query":       query,
        "timestamp":   datetime.now().isoformat(),
        "summary":     build_summary(validated_relations),
        "validated_findings":     validated,
        "novel_hypotheses":       novel,
        "contradicted_findings":  contradicted,
        "causal_chains":          chains,
        "drug_candidates": list({
            drug
            for r in validated_relations
            for drug in r.get("drug_candidates", [])
            if drug
        }),
        "clinical_trials": list({
            trial
            for r in validated_relations
            for trial in r.get("clinical_trials", [])
            if trial
        })
    }

    # Save JSON output
    output_dir  = os.path.join(os.path.dirname(__file__), '..', 'outputs')
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, f"causalmed_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(json_path, 'w') as f:
        json.dump(final_output, f, indent=2)
    print(f"[Output Agent] JSON saved to {json_path}")

    # Generate knowledge graph
    graph_path = os.path.join(output_dir, "knowledge_graph.html")
    generate_knowledge_graph(validated_relations, chains, graph_path)

    state["final_output"] = final_output
    return state