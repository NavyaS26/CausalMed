# agents/normalization_agent.py
# R's work — Agent 3 (runs after NER)
# Converts gene names to standard IDs using MyGene.info free API.
# This is critical before querying any biological database.

import requests
from state import PipelineState


def normalize_gene(gene_name: str) -> dict:
    """
    Query MyGene.info to get standard IDs for a gene name.
    Returns dict with entrez_id, ensembl_id, symbol.
    Falls back to original name if not found.
    """
    try:
        url    = f"https://mygene.info/v3/query"
        params = {
            "q":      gene_name,
            "fields": "entrezgene,ensembl.gene,symbol,name",
            "size":   1,
            "species": "human"
        }
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get("hits"):
            hit = data["hits"][0]
            return {
                "original_name": gene_name,
                "symbol":        hit.get("symbol", gene_name),
                "entrez_id":     str(hit.get("entrezgene", "")),
                "ensembl_id":    hit.get("ensembl", {}).get("gene", "") if isinstance(hit.get("ensembl"), dict) else "",
                "normalized":    True
            }
    except Exception as e:
        print(f"[Normalization] Could not normalize {gene_name}: {e}")

    # Fallback — return original name if API fails
    return {
        "original_name": gene_name,
        "symbol":        gene_name,
        "entrez_id":     "",
        "ensembl_id":    "",
        "normalized":    False
    }


def normalization_agent(state: PipelineState) -> PipelineState:
    """
    LangGraph node function.
    Input:  state["entities"]            — raw NER output
    Output: state["normalized_entities"] — entities with standard gene IDs added
    """
    entities = state.get("entities", [])

    if not entities:
        print("[Normalization Agent] No entities to normalize.")
        state["normalized_entities"] = []
        return state

    print(f"[Normalization Agent] Normalizing {len(entities)} entities...")

    # Cache to avoid calling API multiple times for same gene
    cache = {}
    normalized = []

    for entity in entities:
        gene = entity.get("gene", "")

        if gene not in cache:
            cache[gene] = normalize_gene(gene)

        gene_info = cache[gene]

        normalized.append({
            **entity,
            "gene_symbol":  gene_info["symbol"],
            "gene_id":      gene_info["entrez_id"],
            "ensembl_id":   gene_info["ensembl_id"],
            "normalized":   gene_info["normalized"]
        })

    normalized_count = sum(1 for e in normalized if e["normalized"])
    print(f"[Normalization Agent] Successfully normalized {normalized_count}/{len(entities)} entities")

    state["normalized_entities"] = normalized
    return state