from typing import TypedDict, List, Dict, Any


class CausalRelation(TypedDict):
    gene:                  str
    gene_symbol:           str
    gene_id:               str
    ensembl_id:            str
    disease:               str
    sentence:              str
    paper_id:              str
    causal_label:          str
    confidence:            float | None
    biobert_label:         str
    biobert_confidence:    float
    evidence_checklist:    Dict
    critic_score:          float
    analyst_reasoning:     str
    critic_feedback:       str
    needs_review:          bool
    review_reason:         str
    combined_score:        float | None
    evidence_tier:         str
    evidence_tier_label:   str
    validated:             bool
    clinvar_score:         float | None
    claim_quote:           str
    clinvar_record_count:  int | None
    clinvar_status:        str
    classification:        str
    contradictions:        List[str]
    conflict_evidence:     List[Dict]
    evidence_papers:       List[str]
    clinical_trials:       List[str]
    drug_candidates:       List[str]
    reliability_score:     float | None
    evidence_count:        int
    chain:                 List[Dict]


class PipelineState(TypedDict):
    user_query:                str
    papers:                    List[Dict]
    entities:                  List[Dict]
    normalized_entities:       List[Dict]
    causal_relations:          List[CausalRelation]
    chains:                    List[Dict]
    validated_relations:       List[CausalRelation]
    final_output:              Dict[str, Any]
    analyst_critic_iterations: int
    max_iterations:            int
