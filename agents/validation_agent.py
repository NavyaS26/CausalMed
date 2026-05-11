# agents/validation_agent.py
# R's work — Agent 6 (runs after analyst-critic loop)
# Validation strategy:
# 1. ClinVar — does this gene have pathogenic clinical evidence?
#    (gene-level check, no disease name matching needed — scalable for any gene)
# 2. ClinicalTrials.gov — active trials for gene + disease
# 3. ChEMBL — approved drugs targeting this gene
#
# Why gene-level validation works:
# By the time a relation reaches here it has already passed:
# - CRED model: causal sentence classification
# - Analyst-Critic: LLM biological reasoning
# So validation just confirms: is this gene clinically real?

import requests
import math
from state import PipelineState

# Caches
_clinvar_gene_cache = {}
_chembl_cache       = {}


# ── ClinVar Gene-Level Validation ────────────────────────────

def get_gene_clinical_significance(gene_symbol: str) -> float:
    """
    Check if this gene has pathogenic variants in ClinVar.
    Returns score based on number of pathogenic entries.
    Works for ANY gene — no disease name matching needed.

    Scoring:
    - 0 entries     → 0.0  (no clinical evidence — novel hypothesis)
    - 1-10 entries  → 0.4  (some clinical evidence)
    - 11-100 entries → 0.6 (moderate clinical evidence)
    - 100+ entries  → 0.8  (well established pathogenic gene)
    """
    if gene_symbol in _clinvar_gene_cache:
        return _clinvar_gene_cache[gene_symbol]

    try:
        response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db":      "clinvar",
                "term":    f"{gene_symbol}[gene] AND pathogenic[clinical_significance]",
                "retmax":  1,
                "retmode": "json"
            },
            timeout=10
        )
        response.raise_for_status()
        count = int(response.json()
                           .get("esearchresult", {})
                           .get("count", 0))

        if count > 100:
            score = 0.8
        elif count > 10:
            score = 0.6
        elif count > 0:
            score = 0.4
        else:
            score = 0.0

        print(f"    ClinVar: {gene_symbol} has {count} pathogenic entries → score {score}")
        _clinvar_gene_cache[gene_symbol] = score
        return score

    except Exception as e:
        print(f"[Validation] ClinVar error for {gene_symbol}: {e}")
        _clinvar_gene_cache[gene_symbol] = 0.0
        return 0.0


# ── ClinicalTrials.gov ────────────────────────────────────────

def query_clinical_trials(gene: str, disease: str) -> list:
    """Search ClinicalTrials.gov for active trials."""
    try:
        response = requests.get(
            "https://clinicaltrials.gov/api/v2/studies",
            params={
                "query.term":           f"{gene} {disease}",
                "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING",
                "pageSize":             5,
                "fields":               "NCTId"
            },
            timeout=10
        )
        response.raise_for_status()
        trials = []
        for study in response.json().get("studies", []):
            nct_id = (study.get("protocolSection", {})
                           .get("identificationModule", {})
                           .get("nctId", ""))
            if nct_id:
                trials.append(nct_id)
        return trials
    except Exception as e:
        print(f"[Validation] ClinicalTrials error for {gene}: {e}")
        return []


# ── ChEMBL Drug Candidates ────────────────────────────────────

def query_chembl(gene_symbol: str) -> list:
    """Query ChEMBL for approved drugs targeting this gene."""
    if gene_symbol in _chembl_cache:
        return _chembl_cache[gene_symbol]

    drug_names = []
    try:
        response = requests.get(
            "https://www.ebi.ac.uk/chembl/api/data/target.json",
            params={
                "target_synonym__icontains": gene_symbol,
                "target_type":               "SINGLE PROTEIN",
                "organism":                  "Homo sapiens",
                "limit":                     3
            },
            timeout=10
        )
        if not response.ok:
            _chembl_cache[gene_symbol] = []
            return []

        for target in response.json().get("targets", [])[:2]:
            target_id = target.get("target_chembl_id", "")
            if not target_id:
                continue

            mech_r = requests.get(
                "https://www.ebi.ac.uk/chembl/api/data/mechanism.json",
                params={"target_chembl_id": target_id, "limit": 10},
                timeout=10
            )
            if mech_r.ok:
                for mech in mech_r.json().get("mechanisms", []):
                    mol_id = mech.get("molecule_chembl_id", "")
                    if mol_id:
                        mol_r = requests.get(
                            f"https://www.ebi.ac.uk/chembl/api/data/molecule/{mol_id}.json",
                            timeout=5
                        )
                        if mol_r.ok:
                            name = mol_r.json().get("pref_name", "")
                            if name:
                                drug_names.append(name)

        result = list(set(drug_names))[:5]
        _chembl_cache[gene_symbol] = result
        return result

    except Exception as e:
        print(f"[Validation] ChEMBL error for {gene_symbol}: {e}")
        _chembl_cache[gene_symbol] = []
        return []


# ── Reliability Score ─────────────────────────────────────────

def calculate_reliability_score(
    agent_confidence: float,
    db_score:         float,
    evidence_count:   int
) -> float:
    base  = (agent_confidence + db_score) / 2
    score = base * math.log(evidence_count + 2)
    return round(min(score, 1.0), 4)


# ── Classification ────────────────────────────────────────────

def classify_finding(causal_label: str, db_score: float, contradicted: bool) -> str:
    if contradicted:
        return "contradicted"
    if causal_label != "causal":
        return "non_causal"
    if db_score > 0.3:
        return "validated"
    return "novel_hypothesis"


# ── Main Agent ────────────────────────────────────────────────

def validation_agent(state: PipelineState) -> PipelineState:
    """
    LangGraph node function.
    Input:  state["causal_relations"]
    Output: state["validated_relations"] with scores + classification
    """
    relations = state.get("causal_relations", [])

    if not relations:
        print("[Validation Agent] No relations to validate.")
        state["validated_relations"] = []
        return state

    # Count evidence per gene-disease pair
    evidence_count = {}
    for rel in relations:
        key = f"{rel.get('gene_symbol', rel.get('gene', ''))}_{rel.get('disease', '')}"
        evidence_count[key] = evidence_count.get(key, 0) + 1

    print(f"[Validation Agent] Validating {len(relations)} relations...")

    validated   = []
    val_count   = 0
    novel_count = 0

    for rel in relations:
        gene_symbol  = rel.get("gene_symbol", rel.get("gene", ""))
        disease      = rel.get("disease", "")
        causal_label = rel.get("causal_label", "non-causal")

        # Skip non-causal
        if causal_label != "causal":
            rel["classification"]    = "non_causal"
            rel["reliability_score"] = 0.0
            validated.append(rel)
            continue

        print(f"  Validating: {gene_symbol} → {disease}")

        # Gene-level ClinVar validation
        db_score        = get_gene_clinical_significance(gene_symbol)
        clinical_trials = query_clinical_trials(gene_symbol, disease)
        drug_candidates = query_chembl(gene_symbol)

        key   = f"{gene_symbol}_{disease}"
        count = evidence_count.get(key, 1)

        reliability    = calculate_reliability_score(
            agent_confidence=rel.get("confidence", 0.5),
            db_score=db_score,
            evidence_count=count
        )
        classification = classify_finding(
            causal_label=causal_label,
            db_score=db_score,
            contradicted=bool(rel.get("contradictions"))
        )

        if classification == "validated":
            val_count += 1
            print(f"    ✅ VALIDATED")
        elif classification == "novel_hypothesis":
            novel_count += 1
            print(f"    🔶 NOVEL HYPOTHESIS")

        validated.append({
            **rel,
            "validated":         db_score > 0.3,
            "disgenet_score":    db_score,
            "clinical_trials":   clinical_trials,
            "drug_candidates":   drug_candidates,
            "reliability_score": reliability,
            "classification":    classification,
            "evidence_count":    count
        })

    print(f"[Validation Agent] Validated: {val_count} | Novel hypotheses: {novel_count}")
    state["validated_relations"] = validated
    return state