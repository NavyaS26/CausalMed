"""Describe automatically extracted statements about a particular gene and disease."""
import re


PAIR_METHOD = "source_claim_pair_v2"
SOURCE_CLAIM_METHODS = ("source_claim_v1", PAIR_METHOD)
CHECKLIST_FIELDS = ("mechanism_present", "gene_drives_disease", "disease_outcome_linked",
                    "directional_language", "experimental_evidence")
LABELS = {
    "direct_claim": "Explicit causal statement",
    "contextual": "Contextual mention",
    "non_causal": "No causal signal detected",
    "needs_review": "Needs review",
    "contradicted": "Potential conflict",
}


def treatment_purpose_only(sentence: str, disease: str) -> bool:
    """The only named disease is the object of a terminal treatment-purpose phrase."""
    if not disease:
        return False
    mentions = list(re.finditer(r"(?<!\w)" + re.escape(disease) + r"(?!\w)", sentence, re.I))
    if len(mentions) != 1:
        return False
    start, end = mentions[0].span()
    return (not sentence[end:].strip(" .!?") and
            re.search(r"\bfor\s+(?:the\s+)?treatment\s+of\s+$", sentence[:start], re.I) is not None)


def claim_category(rel: dict) -> str:
    if rel.get("causal_label") == "unresolved" or rel.get("checklist_status") == "not_assessed":
        return "needs_review"
    if rel.get("contradictions"):
        return "contradicted"
    if rel.get("causal_label") != "causal":
        return "non_causal"
    check = rel.get("evidence_checklist", {})
    if (rel.get("checklist_status") != "available" or not isinstance(check, dict)
            or any(type(check.get(key)) is not bool for key in CHECKLIST_FIELDS)):
        return "needs_review"
    quote = check.get("claim_quote")
    if not isinstance(quote, str):
        return "needs_review"
    if not quote.strip():
        return "contextual"
    if quote not in rel.get("sentence", ""):
        return "needs_review"
    for field in ("gene", "disease"):
        mention = rel.get(field)
        if not mention or not re.search(r"(?<!\w)" + re.escape(mention) + r"(?!\w)", quote, re.I):
            return "needs_review"
    if not (check["gene_drives_disease"] and check["disease_outcome_linked"]):
        return "needs_review"
    if treatment_purpose_only(rel["sentence"], rel["disease"]):
        return "contextual"
    return "direct_claim"


def evidence_summary(rel: dict) -> str:
    return (rel.get("analyst_reasoning") or rel.get("review_reason") or
            "No sentence-level explanation was recorded.")
