import requests
from agents.evidence_scoring import claim_category, LABELS, treatment_purpose_only
from agents.ncbi_client import fetch_eutils
from state import PipelineState

_clinvar_cache = {}
_chembl_cache  = {}

def get_clinvar_count(gene_symbol: str) -> int | None:
    if gene_symbol in _clinvar_cache:
        return _clinvar_cache[gene_symbol]
    try:
        response = fetch_eutils(
            "esearch.fcgi",
            params={
                "db":      "clinvar",
                "term":    f"{gene_symbol}[gene] AND pathogenic[clinical_significance]",
                "retmax":  1,
                "retmode": "json"
            },
            timeout=10
        )
        count = int(response.json()["esearchresult"]["count"])
        _clinvar_cache[gene_symbol] = count
        return count
    except Exception as e:
        print(f"[Validation] ClinVar error for {gene_symbol}: {e}")
        return None


def query_clinical_trials(gene: str, disease: str) -> list:
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


def query_chembl(gene_symbol: str) -> list:
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
            timeout=15
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
                timeout=15
            )
            if mech_r.ok:
                for mech in mech_r.json().get("mechanisms", []):
                    mol_id = mech.get("molecule_chembl_id", "")
                    if mol_id:
                        mol_r = requests.get(
                            f"https://www.ebi.ac.uk/chembl/api/data/molecule/{mol_id}.json",
                            timeout=8
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


def validation_agent(state: PipelineState) -> PipelineState:
    relations = state.get("causal_relations", [])
    if not relations:
        print("[Validation Agent] No relations to validate.")
        state["validated_relations"] = []
        return state

    papers_by_pair = {}
    for rel in relations:
        key = (rel.get("gene_symbol") or rel["gene"], rel.get("mesh_id") or rel["disease"].casefold())
        if rel.get("paper_id"):
            papers_by_pair.setdefault(key, set()).add(rel["paper_id"])

    print(f"[Validation Agent] Validating {len(relations)} relations...")

    validated   = []
    for rel in relations:
        gene_symbol  = rel.get("gene_symbol") or rel["gene"]
        disease      = rel.get("disease", "")

        key = (gene_symbol, rel.get("mesh_id") or disease.casefold())
        source_papers = sorted(papers_by_pair.get(key, ()))
        count = len(source_papers)
        rel = {**rel, "evidence_count": count, "evidence_papers": source_papers}

        category = claim_category(rel)
        bucket = {"direct_claim": "validated", "contextual": "novel_hypothesis"}.get(category, category)
        annotated = {
            **rel, "classification": bucket, "validated": False, "evidence_tier": category,
            "evidence_tier_label": LABELS[category], "combined_score": None, "reliability_score": None,
            "clinvar_score": None, "clinvar_record_count": None, "clinvar_status": "not_queried",
            "needs_review": category == "needs_review",
        }
        if category == "needs_review" and not annotated.get("review_reason"):
            annotated["review_reason"] = "The source assessment was incomplete or its quotation could not be verified."
        if category == "contextual" and treatment_purpose_only(rel.get("sentence", ""), disease):
            annotated["analyst_reasoning"] = "The authors mention the disease as the condition being treated."
        if category == "direct_claim":
            annotated["claim_quote"] = rel["evidence_checklist"]["claim_quote"]
        if category in ("direct_claim", "contextual", "contradicted"):
            records = get_clinvar_count(gene_symbol)
            annotated.update(clinvar_record_count=records,
                             clinvar_status="available" if records is not None else "unavailable",
                             clinical_trials=query_clinical_trials(gene_symbol, disease),
                             drug_candidates=query_chembl(gene_symbol))
        validated.append(annotated)

    state["validated_relations"] = validated
    return state
