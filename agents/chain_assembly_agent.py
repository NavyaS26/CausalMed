import networkx as nx
from state import PipelineState
from typing import List, Dict


def build_causal_graph(causal_relations: list) -> nx.DiGraph:
    G = nx.DiGraph()
    for rel in causal_relations:
        if rel.get("evidence_tier") != "direct_claim":
            continue
        source = rel.get("gene_symbol") or rel["gene"]
        target = rel["disease"]
        if source == target:
            continue
        existing = G.get_edge_data(source, target)
        if existing and existing["confidence"] >= rel["confidence"]:
            continue
        G.add_edge(
            source, target,
            confidence=rel["confidence"],
            paper_id=rel["paper_id"],
            sentence=rel["sentence"],
            # FIX: removed dead clinvar_validated reference
            validated=rel.get("validated", False)
        )
    return G


def find_chains(G: nx.DiGraph, start_node: str, max_hops: int = 4) -> List[List]:
    chains = []
    stack  = [(start_node, [start_node])]
    while stack:
        node, path = stack.pop()
        if len(path) > max_hops:
            continue
        for neighbor in G.successors(node):
            if neighbor == node:
                continue
            new_path = path + [neighbor]
            if len(new_path) >= 2:
                chains.append(new_path)
            if neighbor not in path:
                stack.append((neighbor, new_path))
    return chains


def score_chain(G: nx.DiGraph, chain: list) -> float:
    score = 1.0
    for i in range(len(chain) - 1):
        if chain[i] == chain[i + 1]:
            return 0.0
        edge_data = G.get_edge_data(chain[i], chain[i + 1])
        score *= edge_data.get("confidence", 0.5) if edge_data else 0.3
    return round(score, 4)


def chain_to_dict(G: nx.DiGraph, chain: list) -> Dict:
    hops = []
    for i in range(len(chain) - 1):
        edge_data = G.get_edge_data(chain[i], chain[i + 1]) or {}
        hops.append({
            "from":       chain[i],
            "to":         chain[i + 1],
            "confidence": edge_data.get("confidence", 0.0),
            "paper_id":   edge_data.get("paper_id", "unknown"),
            "sentence":   edge_data.get("sentence", ""),
            "validated":  edge_data.get("validated", False)
        })
    return {
        "chain":              chain,
        "hops":               hops,
        "chain_length":       len(chain) - 1,
        "overall_confidence": score_chain(G, chain),
        "novel_hops":         [],
        "validated_hops":     [h for h in hops if h["validated"]]
    }


def chain_assembly_agent(state: PipelineState) -> PipelineState:
    print("[Chain Assembly Agent] Building causal graph...")

    relations = state.get("validated_relations", [])
    if not relations:
        print("[Chain Assembly Agent] No validated relations to assemble.")
        state["chains"] = []
        return state

    G = build_causal_graph(relations)
    print(f"[Chain Assembly Agent] Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # FIX: safe query parsing — guard against empty string and multi-word queries
    parts      = state.get("user_query", "").upper().split()
    query_gene = parts[0] if parts else ""
    gene_nodes = [n for n in G.nodes() if G.in_degree(n) == 0]
    start_nodes = [query_gene] if query_gene in G.nodes() else gene_nodes[:5]

    all_chains = []
    for gene in start_nodes:
        for path in find_chains(G, gene, max_hops=1):
            if any(path[i] == path[i+1] for i in range(len(path)-1)):
                continue
            if len(path) >= 2:
                chain_dict = chain_to_dict(G, path)
                all_chains.append(chain_dict)

    all_chains.sort(key=lambda x: x["overall_confidence"], reverse=True)
    all_chains = all_chains[:20]

    print(f"[Chain Assembly Agent] Assembled {len(all_chains)} chains")
    state["chains"] = all_chains
    return state
