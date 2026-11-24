# app.py
# P's work — Streamlit UI
# Three modes: Doctor, Researcher, Pharmacist
#
# UPDATES:
# - Risk labels removed (HIGH/MEDIUM/LOW RISK → evidence tier only)
# - Doctor mode: clinical_disease shown first
# - Doctor mode: generic_disease + research_concept collapsed under Research Findings
# - Doctor mode: invalid_entity never shown
# - Researcher mode: all four categories shown with labels
# - disease_category, mesh_id, disease_source shown in researcher mode

from html import escape
from agents.evidence_scoring import PAIR_METHOD, SOURCE_CLAIM_METHODS, evidence_summary
import streamlit as st
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from pipeline import run_pipeline

st.set_page_config(page_title="CausalMed", page_icon="🧬", layout="wide")

st.markdown("""
<style>
    .main  { background-color: #0f0f1a; }
    .stApp { background-color: #0f0f1a; color: white; }
    .card-strong {
        background: #0a2a0a; border-radius: 10px; padding: 16px;
        margin: 10px 0; border-left: 5px solid #00ee55;
    }
    .card-moderate {
        background: #0d2b0d; border-radius: 10px; padding: 16px;
        margin: 10px 0; border-left: 5px solid #44cc44;
    }
    .card-emerging {
        background: #1a1a0d; border-radius: 10px; padding: 16px;
        margin: 10px 0; border-left: 5px solid #ccaa00;
    }
    .card-associative {
        background: #1a1000; border-radius: 10px; padding: 16px;
        margin: 10px 0; border-left: 5px solid #886600;
    }
    .card-contradicted {
        background: #1a0000; border-radius: 10px; padding: 16px;
        margin: 10px 0; border-left: 5px solid #cc0000;
    }
    .card-research {
        background: #111133; border-radius: 10px; padding: 16px;
        margin: 10px 0; border-left: 5px solid #4444aa;
    }
    .drug-card {
        background: #0d0d2b; border-radius: 8px; padding: 10px 14px;
        margin: 4px 0; border-left: 4px solid #6644cc;
        display: inline-block; width: 100%;
    }
    .mechanism-box {
        background: #111122; border-radius: 6px; padding: 10px;
        margin: 8px 0; font-size: 0.9em; font-style: italic; color: #aaaacc;
    }
    .checklist-box {
        background: #0a1628; border-radius: 6px; padding: 10px 14px;
        margin: 8px 0; font-size: 0.85em; font-family: monospace;
    }
    .chain-row {
        background: #111122; border-radius: 8px; padding: 10px 16px;
        margin: 6px 0;
    }
    .badge-strong      { background:#005522; color:white; padding:3px 10px; border-radius:12px; font-size:0.8em; }
    .badge-moderate    { background:#006622; color:white; padding:3px 10px; border-radius:12px; font-size:0.8em; }
    .badge-emerging    { background:#665500; color:white; padding:3px 10px; border-radius:12px; font-size:0.8em; }
    .badge-associative { background:#443300; color:white; padding:3px 10px; border-radius:12px; font-size:0.8em; }
    .badge-research    { background:#222266; color:white; padding:3px 10px; border-radius:12px; font-size:0.8em; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────
st.markdown("# 🧬 CausalMed")
st.markdown("**Agentic AI for Causal Gene-Disease Relation Extraction**")
st.caption("Find gene–disease statements in PubMed abstracts and inspect the passages behind them.")
st.divider()

# ── Mode Selection ────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("👨‍⚕️ Doctor Mode", use_container_width=True):
        st.session_state["mode"] = "doctor"
with col2:
    if st.button("🔬 Researcher Mode", use_container_width=True):
        st.session_state["mode"] = "researcher"
with col3:
    if st.button("💊 Pharmacist Mode", use_container_width=True):
        st.session_state["mode"] = "pharmacist"

if "mode" not in st.session_state:
    st.session_state["mode"] = "doctor"
mode = st.session_state["mode"]

mode_descriptions = {
    "doctor":     "👨‍⚕️ **Doctor Mode** — Browse literature signals, gene-level annotations, and related trial records.",
    "researcher": "🔬 **Researcher Mode** — Explore all findings grouped by the source statement, including contextual mentions and research concepts.",
    "pharmacist": "💊 **Pharmacist Mode** — Browse ChEMBL drug candidates and related trial records."
}
st.info(mode_descriptions[mode])

# ── Input ─────────────────────────────────────────────────────
st.markdown("### 🔍 Enter Query")
if mode == "doctor":
    query_input = st.text_input("Gene to investigate", placeholder="e.g. BRCA1, TP53, EGFR, ALK")
    query = f"{query_input} causal mechanism" if query_input else ""
elif mode == "researcher":
    query_input = st.text_input("Gene or disease to investigate", placeholder="e.g. BRCA1 breast cancer, TP53 lung cancer")
    query = f"{query_input} causal mechanism" if query_input else ""
else:
    query_input = st.text_input("Gene target or disease", placeholder="e.g. EGFR, ALK, HER2")
    query = f"{query_input} drug target treatment mechanism" if query_input else ""

run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

if run_btn and query_input:
    with st.spinner("CausalMed is reading papers and reasoning..."):
        try:
            result = run_pipeline(query)
            st.session_state["result"]      = result
            st.session_state["query_input"] = query_input
            st.success("✅ Analysis complete!")
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()


# ── Helpers ───────────────────────────────────────────────────

def tier_badge(tier: str) -> str:
    if tier == "direct_claim":
        return '<span class="badge-strong">Explicit causal statement</span>'
    return '<span class="badge-emerging">Contextual mention</span>'


def card_class(tier: str) -> str:
    return "card-strong" if tier == "direct_claim" else "card-emerging"


def render_checklist(rel: dict):
    checklist = rel.get("evidence_checklist", {})
    if not show_scoring_details or not checklist:
        return
    if rel.get("checklist_status") != "available" and not (rel.get("analyst_reasoning") or "").strip():
        st.caption("This saved run has no verified checklist assessment.")
        return
    score    = rel.get("critic_score", None)

    def c(val): return "✓" if val else "✗"

    score_str    = f"{score:.2f}" if score is not None else "—"

    st.markdown(f"""
    <div class="checklist-box">
        <strong>Evidence Checklist</strong> &nbsp;
        <span style="color:#aaaacc;">BioBERT: {score_str}</span><br>
        {c(checklist.get('mechanism_present'))} Biological mechanism &nbsp;&nbsp;
        {c(checklist.get('gene_drives_disease'))} Gene drives disease &nbsp;&nbsp;
        {c(checklist.get('disease_outcome_linked'))} Disease outcome linked<br>
        {c(checklist.get('directional_language'))} Directional language &nbsp;&nbsp;
        {c(checklist.get('experimental_evidence'))} Experimental evidence
    </div>
    """, unsafe_allow_html=True)


def render_causal_card(rel: dict):
    """Render a single causal finding card."""
    tier     = rel.get("evidence_tier", "associative_only")
    conf     = rel.get("confidence", 0.0)
    css      = card_class(tier)
    badge    = tier_badge(tier)

    disease_cat = rel.get("disease_category", "")
    mesh_label  = rel.get("mesh_label", "")
    cat_note    = ""
    if disease_cat == "generic_disease":
        cat_note = ' &nbsp;<span style="color:#ccaa00; font-size:0.8em;">(broad disease term)</span>'
    elif disease_cat == "research_concept":
        cat_note = ' &nbsp;<span style="color:#4444aa; font-size:0.8em;">(research concept)</span>'

    canonical = f" <span style='color:#aaaacc; font-size:0.8em;'>({mesh_label})</span>" \
                if mesh_label and mesh_label != rel.get("disease", "") else ""

    st.markdown(f"""
    <div class="{css}">
        {badge}&nbsp;&nbsp;
        <strong>{rel['gene']} → {rel['disease']}</strong>{canonical}{cat_note}
        &nbsp;&nbsp;
        <span style="color:#aaaacc; font-size:0.9em;">
            BioBERT: {conf:.0%}
        </span>
        <div class="mechanism-box">
            📖 <em>"{rel.get('source_sentence', '')}"</em>
        </div>
        <div style="margin-top:8px; font-size:0.9em;">
            🧠 <strong>Evidence summary:</strong> {escape(evidence_summary(rel))}
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_checklist(rel)

    if rel.get("claim_quote"):
        st.write("Claim quotation", rel["claim_quote"])
    drugs = rel.get("drug_candidates", [])
    if drugs:
        st.markdown(f"&nbsp;&nbsp;&nbsp;💊 **Drugs targeting {rel['gene']}:** " +
                    " &nbsp;|&nbsp; ".join([f"`{d}`" for d in drugs]))
    trials = rel.get("clinical_trials", [])
    if trials:
        trial_links = " &nbsp; ".join([
            f"[{t}](https://clinicaltrials.gov/study/{t})" for t in trials[:3]
        ])
        st.markdown(f"&nbsp;&nbsp;&nbsp;🏥 **Active trials:** {trial_links}")
    st.markdown("---")


# ── Display Results ───────────────────────────────────────────
if "result" in st.session_state:
    result = st.session_state["result"]
    if result.get("evidence_method") not in SOURCE_CLAIM_METHODS:
        st.info("This saved run used the earlier weighted method. Run Analysis again to extract source claims.")
        st.download_button("Download original JSON", json.dumps(result, indent=2), file_name="historical_report.json")
        st.stop()
    query_input = st.session_state.get("query_input", "")
    summary     = result.get("summary", {})

    st.divider()
    st.markdown(f"## Results for: **{query_input}**")

    st.subheader("Gene–Disease Graph Links")
    chains = result.get("causal_chains", [])
    if chains:
        st.caption("These links summarize explicit statements in the retrieved papers. The BioBERT score ranks passages by the classifier’s confidence in its label.")
        for chain in chains:
            st.write(f"**{' → '.join(chain['chain'])}** · BioBERT score {chain['overall_confidence']:.0%}")
            for hop in chain.get("hops", []):
                pmid = str(hop.get("paper_id", ""))
                if pmid.isdigit():
                    st.markdown(f"[PubMed {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                if hop.get("sentence"):
                    st.text(hop["sentence"])
    else:
        st.info("No explicit gene–disease link was included in the graph for this run.")
    if result.get("review_findings") or result.get("contradicted_findings"):
        st.caption(f"Findings needing review: {len(result.get('review_findings', []))} · Potential conflicts: {len(result.get('contradicted_findings', []))}")
    st.divider()

    show_scoring_details = mode == "researcher" and st.checkbox("Show extraction details", value=False)
    if show_scoring_details:
        if result["evidence_method"] == PAIR_METHOD:
            st.caption("BioBERT screens each named gene–disease pair in context. An explicit claim requires a supporting quotation from the original passage.")
        else:
            st.caption("This saved run used one BioBERT score per sentence.")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📄 Relations Analyzed",  summary.get("total_relations_analyzed", 0))
    c2.metric("✅ Explicit claims",   summary.get("validated_count", 0))
    c3.metric("🔶 Contextual mentions",     summary.get("novel_hypothesis_count", 0))
    c4.metric("❌ Potential conflicts", summary.get("contradicted_count", 0))
    c5.metric("Needs review", len(result.get("review_findings", [])))
    passages = {}
    for group in ("validated_findings", "novel_hypotheses", "contradicted_findings",
                  "non_causal_findings", "review_findings"):
        for rel in result.get(group, []):
            source = (rel.get("source_paper"), rel.get("source_sentence"))
            if source[1]:
                pair = f"{rel.get('source_gene') or rel['gene']} → {rel['disease']}"
                passages.setdefault(source, []).append(f"{pair} · {rel['evidence_tier_label']}")
    if passages:
        with st.expander(f"All matching source passages ({len(passages)})"):
            for (pmid, sentence), pairs in passages.items():
                if str(pmid).isdigit():
                    st.markdown(f"[PubMed {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                st.text(sentence)
                st.caption(" | ".join(pairs))
    st.divider()

    # ── DOCTOR MODE ───────────────────────────────────────────
    if mode == "doctor":
        validated    = result.get("validated_findings", [])
        novel        = result.get("novel_hypotheses", [])
        contradicted = result.get("contradicted_findings", [])
        non_causal   = result.get("non_causal_findings", [])

        # Separate clinical findings from research/generic
        clinical_validated = [r for r in validated
                               if r.get("disease_category") == "clinical_disease"]
        research_validated = [r for r in validated
                               if r.get("disease_category") in ("generic_disease", "research_concept", "unmapped_disease")]
        clinical_novel     = [r for r in novel
                               if r.get("disease_category") == "clinical_disease"]
        research_novel     = [r for r in novel
                               if r.get("disease_category") in ("generic_disease", "research_concept", "unmapped_disease")]

        # ── CLINICAL FINDINGS ──
        st.markdown("### ✅ Explicit causal statements about clinical diseases")
        st.caption("Each entry links an automatically identified claim to its source sentence.")

        if clinical_validated:
            for rel in clinical_validated:
                render_causal_card(rel)
        elif passages:
            st.info("No clinical disease pair in this run had a verified explicit causal quotation. Open All matching source passages above to read the sentences that were screened.")
        else:
            st.info("This run found no passages containing a candidate gene–disease pair.")

        # ── NOVEL CLINICAL ──
        if clinical_novel:
            st.markdown("### 🔶 Contextual mentions")
            st.caption("The source mentions the pair without an extracted explicit causal claim.")
            for rel in clinical_novel:
                render_causal_card(rel)

        # ── RESEARCH FINDINGS (collapsed) ──
        research_all = research_validated + research_novel
        if research_all:
            with st.expander(f"⚠️ Research Findings ({len(research_all)}) — broad, unmapped, and other terms"):
                st.caption("These findings involve broad, unmapped, or non-disease terms.")
                for rel in research_all:
                    tier  = rel.get("evidence_tier", "associative_only")
                    badge = tier_badge(tier)
                    css   = card_class(tier)
                    cat   = rel.get("disease_category", "")
                    cat_label = cat.replace("_", " ").title()
                    st.markdown(f"""
                    <div class="card-research">
                        {badge}&nbsp;&nbsp;
                        <strong>{rel['gene']} → {rel['disease']}</strong>
                        &nbsp;<span style="color:#aaaacc; font-size:0.8em;">({cat_label})</span>
                        <div class="mechanism-box">
                            📖 <em>"{rel.get('source_sentence', '')}"</em>
                        </div>
                        <div style="margin-top:6px; font-size:0.9em;">
                            🧠 {escape(evidence_summary(rel))}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    render_checklist(rel)

        # ── ASSOCIATIONS ONLY ──
        if non_causal:
            st.markdown("### ⚠️ Insufficient Causal Evidence")
            st.caption("BioBERT did not flag these candidates for quote assessment. All matching source passages are available above.")
            for rel in non_causal[:5]:
                st.markdown(f"""
                <div class="card-associative">
                    <span class="badge-associative">⚪ Insufficient Causal Evidence</span>&nbsp;&nbsp;
                    <strong>{rel['gene']} → {rel['disease']}</strong>
                    <div class="mechanism-box">
                        📖 <em>"{rel.get('source_sentence', '')}"</em>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ── CONTRADICTIONS ──
        if contradicted:
            st.markdown("### ❌ Potential Conflicts")
            st.caption("The pipeline detected potential conflicts using keywords in other papers.")
            for rel in contradicted:
                st.markdown(f"""
                <div class="card-contradicted">
                    <strong>❌ {rel['gene']} → {rel['disease']}</strong><br>
                    <small>Contradicting papers: {', '.join(rel.get('contradictions', []))}</small>
                </div>
                """, unsafe_allow_html=True)

    # ── RESEARCHER MODE ───────────────────────────────────────
    elif mode == "researcher":
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "✅ Explicit Clinical Claims",
            "🔬 Other Terms",
            "🔶 Contextual Mentions",
            "⚪ Insufficient Evidence",
            "❌ Potential Conflicts"
        ])

        with tab1:
            validated = result.get("validated_findings", [])
            clinical  = [r for r in validated if r.get("disease_category") == "clinical_disease"]
            if clinical:
                for rel in clinical:
                    label = rel.get("evidence_tier_label", "")
                    with st.expander(f"{label}: {rel['gene']} → {rel['disease']} "
                                     f"| BioBERT: {rel['confidence']:.0%}"):
                        st.markdown(f"**Source sentence:** *\"{rel['source_sentence']}\"*")
                        st.markdown(f"**Evidence summary:** {evidence_summary(rel)}")
                        if show_scoring_details and rel.get("checklist_status") == "available":
                            st.markdown(f"**Critic feedback:** {rel.get('critic_feedback', '')}")
                        render_checklist(rel)
                        st.write("Source PMIDs mentioning this pair:", ", ".join(rel.get("evidence_papers") or [rel.get("source_paper", "")]))
                        st.markdown(f"**Gene-level ClinVar records:** {rel.get('clinvar_record_count') if rel.get('clinvar_record_count') is not None else 'unavailable'}")
                        st.markdown(f"**Disease category:** {rel.get('disease_category', '')} "
                                    f"| MeSH ID: {rel.get('mesh_id', 'N/A')} "
                                    f"| Source: {rel.get('disease_source', 'N/A')}")
                        if rel.get("drug_candidates"):
                            st.markdown(f"**Drugs:** {', '.join(rel['drug_candidates'])}")
                        if rel.get("clinical_trials"):
                            st.markdown(f"**Trials:** {', '.join(rel['clinical_trials'][:3])}")
            else:
                st.info("No clinical disease sentence in this run qualified as an explicit causal statement. Check contextual mentions and findings needing review.")

        with tab2:
            validated = result.get("validated_findings", [])
            novel     = result.get("novel_hypotheses", [])
            research  = [r for r in validated + novel
                         if r.get("disease_category") in ("generic_disease", "research_concept", "unmapped_disease")]
            if research:
                for rel in research:
                    cat = rel.get("disease_category", "")
                    with st.expander(f"🔬 {rel['gene']} → {rel['disease']} "
                                     f"| {cat} "
                                     f"| BioBERT: {rel['confidence']:.0%}"):
                        st.markdown(f"**Source:** *\"{rel['source_sentence']}\"*")
                        st.markdown(f"**Evidence summary:** {evidence_summary(rel)}")
                        render_checklist(rel)
                        st.markdown(f"**Disease category:** {cat}")
                        st.markdown(f"**MeSH ID:** {rel.get('mesh_id', 'Not found in MeSH')}")
                        st.markdown(f"**Disease source:** {rel.get('disease_source', '')}")
                        st.info("This finding involves a broad, unmapped, or non-disease term. "
                                "Treat as a research signal, not a clinical conclusion.")
            else:
                st.info("No findings for other terms.")

        with tab3:
            novel = result.get("novel_hypotheses", [])
            clinical_novel = [r for r in novel if r.get("disease_category") == "clinical_disease"]
            if clinical_novel:
                for rel in clinical_novel:
                    with st.expander(f"🔶 {rel['gene']} → {rel['disease']} "
                                     f"| {rel.get('evidence_tier_label', '')} "
                                     f"| BioBERT: {rel['confidence']:.0%}"):
                        st.markdown(f"**Source:** *\"{rel['source_sentence']}\"*")
                        st.markdown(f"**Evidence summary:** {evidence_summary(rel)}")
                        render_checklist(rel)
            else:
                st.info("No contextual clinical disease mentions.")

        with tab4:
            non_causal = result.get("non_causal_findings", [])
            if non_causal:
                for rel in non_causal[:10]:
                    with st.expander(f"⚪ {rel['gene']} → {rel['disease']}"):
                        st.markdown(f"**Source:** *\"{rel['source_sentence']}\"*")
                        if show_scoring_details and rel.get("checklist_status") == "available":
                            st.markdown(f"**Critic feedback:** {rel.get('critic_feedback', '')}")
                        render_checklist(rel)
            else:
                st.info("No findings in the insufficient-evidence group.")

        with tab5:
            contradicted = result.get("contradicted_findings", [])
            if contradicted:
                for rel in contradicted:
                    with st.expander(f"❌ {rel['gene']} → {rel['disease']}"):
                        st.markdown(f"**Contradicting papers:** {', '.join(rel.get('contradictions', []))}")
                        for evidence in rel.get("conflict_evidence", []):
                            st.text(f"PMID {evidence['paper_id']} · {evidence['sentence']}")
                        st.markdown(f"**Source:** *\"{rel['source_sentence']}\"*")
            else:
                st.info("No contradictions found.")

        graph_path = os.path.join(os.path.dirname(__file__), 'outputs', 'knowledge_graph.html')
        if os.path.exists(graph_path):
            st.markdown("### 🕸️ Knowledge Graph")
            with open(graph_path, 'r') as f:
                st.components.v1.html(f.read(), height=700, scrolling=True)

    # ── PHARMACIST MODE ───────────────────────────────────────
    else:
        st.markdown("### 💊 Drug Intelligence Report")
        st.caption("ChEMBL drug candidates for genes in the literature findings.")
        drug_data = {}
        all_rels  = result.get("validated_findings", []) + result.get("novel_hypotheses", [])
        for rel in all_rels:
            if rel.get("causal_label") != "causal":
                continue
            gene  = rel.get("gene", "")
            drugs = rel.get("drug_candidates", [])
            if not drugs:
                continue
            if gene not in drug_data:
                drug_data[gene] = {
                    "diseases":  [],
                    "drugs":     [],
                    "trials":    [],
                    "tier":      rel.get("evidence_tier_label", ""),
                    "mechanism": evidence_summary(rel)
                }
            drug_data[gene]["drugs"].extend(drugs)
            drug_data[gene]["diseases"].append(rel.get("disease", ""))
            drug_data[gene]["trials"].extend(rel.get("clinical_trials", []))

        if drug_data:
            for gene, data in drug_data.items():
                with st.expander(f"🧬 {gene} — {len(set(data['drugs']))} drug(s) | {data['tier']}"):
                    st.markdown(f"**Diseases in the literature findings:** {', '.join(set(data['diseases']))}")
                    st.markdown(f"**Evidence summary:** {data['mechanism']}")
                    st.markdown("**ChEMBL drug candidates:**")
                    for drug in set(data["drugs"]):
                        st.markdown(f'<div class="drug-card">💊 {drug}</div>', unsafe_allow_html=True)
                    if data["trials"]:
                        st.markdown("**Active clinical trials:**")
                        for trial in list(set(data["trials"]))[:5]:
                            st.markdown(f"- [{trial}](https://clinicaltrials.gov/study/{trial})")
        else:
            st.info("No drug candidates found. Try querying a specific gene like EGFR, ALK, or BRCA1.")

    if result.get("review_findings"):
        with st.expander(f"Findings needing review ({len(result['review_findings'])})"):
            for rel in result["review_findings"]:
                st.write(f"{rel['gene']} → {rel['disease']} · PMID {rel['source_paper']}")
                st.caption(rel["review_reason"])
                st.text(rel["source_sentence"])

    # ── Download ──────────────────────────────────────────────
    st.divider()
    st.subheader("📥 Download Report")
    try:
        from pdf_report import generate_pdf
        pdf_bytes = generate_pdf(result, query_input, mode, show_scoring_details=show_scoring_details)
        st.download_button(
            label="📄 Download Professional PDF Report",
            data=pdf_bytes,
            file_name=f"CausalMed_{query_input}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception:
        st.warning("The PDF report could not be generated. The JSON report is available below.")

    st.download_button(
        label="⬇️ Download Full JSON Report",
        data=json.dumps(result, indent=2),
        file_name=f"causalmed_{query_input}_{result.get('timestamp','')[:10]}.json",
        mime="application/json"
    )
