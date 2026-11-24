# agents/normalization_agent.py
# R's work — Agent 3
#
# FIX: Removed MyGene score threshold entirely.
# Accept normalization ONLY if:
#   returned_symbol == input (exact match)
#   OR input appears in MyGene's documented alias list
# No score threshold — high confidence ≠ correct identity for normalization.
# This prevents PC9→PCSK9, HCC→HYCC1, HBP→STAM2 wrong mappings.

import requests
from state import PipelineState

_DEBUG_LOGGED = False


def is_valid_mapping(input_name: str, hit: dict) -> bool:
    """
    Validates whether a MyGene mapping is trustworthy.

    Accepts ONLY:
    - Returned symbol exactly matches input (case-insensitive)
    - Input appears in the gene's documented alias list from MyGene

    No score threshold — MyGene confidence score does not guarantee
    correct identity for biomedical normalization.
    PC9 scores high for PCSK9 because it's the closest match,
    not because PC9 IS PCSK9.
    """
    if not hit or not isinstance(hit, dict):
        return False

    returned_symbol = hit.get("symbol", "").upper()
    input_upper     = input_name.upper()

    # Rule 1: Exact symbol match
    if returned_symbol == input_upper:
        return True

    # Rule 2: Input is a documented alias
    aliases = hit.get("alias", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    if input_upper in [a.upper() for a in aliases]:
        return True

    # Reject everything else
    return False


def normalize_genes_batch(gene_names: list) -> dict:
    """
    GET per gene — batch POST response order is unreliable.
    Only accepts exact match or documented alias.
    """
    if not gene_names:
        return {}

    results = {}

    for gene_name in gene_names:
        try:
            r = requests.get(
                "https://mygene.info/v3/query",
                params={
                    "q":       gene_name,
                    "fields":  "entrezgene,ensembl.gene,symbol,name,alias",
                    "species": "human",
                    "scopes":  "symbol,alias",
                    "size":    1
                },
                timeout=10
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if hits and isinstance(hits[0], dict):
                hit = hits[0]
                if is_valid_mapping(gene_name, hit):
                    ensembl = hit.get("ensembl", {})
                    results[gene_name] = {
                        "original_name": gene_name,
                        "symbol":        hit.get("symbol", gene_name),
                        "entrez_id":     str(hit.get("entrezgene", "")),
                        "ensembl_id":    ensembl.get("gene", "")
                                         if isinstance(ensembl, dict) else "",
                        "normalized":    True
                    }
                    print(f"  [Normalization] ✓ {gene_name} → {hit.get('symbol', gene_name)}")
                else:
                    print(f"  [Normalization] ✗ Rejected: "
                          f"{gene_name} → {hit.get('symbol', '?')} — keeping original")
                    results[gene_name] = _fallback(gene_name)
            else:
                results[gene_name] = _fallback(gene_name)
        except Exception as e:
            print(f"  [Normalization] Error for {gene_name}: {e}")
            results[gene_name] = _fallback(gene_name)

    return results

def _fallback(gene_name: str) -> dict:
    return {
        "original_name": gene_name,
        "symbol":        gene_name,
        "entrez_id":     "",
        "ensembl_id":    "",
        "normalized":    False
    }


def normalization_agent(state: PipelineState) -> PipelineState:
    entities = state.get("entities", [])
    if not entities:
        print("[Normalization Agent] No entities to normalize.")
        state["normalized_entities"] = []
        return state

    unique_genes = list({e.get("gene", "") for e in entities if e.get("gene")})
    print(f"[Normalization Agent] Normalizing {len(unique_genes)} unique genes "
          f"across {len(entities)} entities...")

    cache = normalize_genes_batch(unique_genes)

    normalized = []
    for entity in entities:
        gene      = entity.get("gene", "")
        gene_info = cache.get(gene) or _fallback(gene)
        normalized.append({
            **entity,
            "gene_symbol": gene_info["symbol"],
            "gene_id":     gene_info["entrez_id"],
            "ensembl_id":  gene_info["ensembl_id"],
            "normalized":  gene_info["normalized"]
        })

    norm_count = sum(1 for e in normalized if e["normalized"])
    print(f"[Normalization Agent] Normalized {norm_count}/{len(entities)} entities")
    state["normalized_entities"] = normalized
    return state