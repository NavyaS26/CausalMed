# state.py
# Shared state object that gets passed between all agents in the pipeline.
# Every agent reads from this and writes back to it.

from typing import TypedDict, List, Optional, Dict, Any

class CausalRelation(TypedDict):
    gene: str
    gene_id: str                  # normalized via MyGene.info
    disease: str
    sentence: str                 # source sentence from paper
    paper_id: str                 # PubMed ID
    causal_label: str             # "causal" or "non-causal"
    confidence: float             # 0.0 to 1.0 from causal reasoning agent
    analyst_reasoning: str        # analyst agent explanation
    critic_feedback: str          # critic agent feedback
    validated: bool               # did DisGeNET confirm this?
    disgenet_score: float         # DisGeNET association score
    classification: str           # "validated" | "novel_hypothesis" | "contradicted"
    contradictions: List[str]     # list of paper IDs that dispute this link
    clinical_trials: List[str]    # active trial IDs from ClinicalTrials.gov
    drug_candidates: List[str]    # drugs from ChEMBL targeting this gene
    chain: List[Dict]             # multi-hop chain hops


class PipelineState(TypedDict):
    # Input
    user_query: str               # e.g. "TP53 and lung cancer"

    # After ingestion
    papers: List[Dict]            # list of {pmid, title, abstract, full_text}

    # After NER
    entities: List[Dict]          # list of {gene, disease, sentence, paper_id}

    # After normalization
    normalized_entities: List[Dict]

    # After causal reasoning + analyst-critic
    causal_relations: List[CausalRelation]

    # After chain assembly
    chains: List[Dict]

    # After validation
    validated_relations: List[CausalRelation]

    # Final
    final_output: Dict[str, Any]

    # Control flags
    analyst_critic_iterations: int   # tracks how many loops have happened
    max_iterations: int              # cap at 3 to avoid infinite loops