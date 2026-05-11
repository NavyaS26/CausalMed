# app.py
# P's work — Streamlit UI
# Three modes: Doctor, Researcher, Pharmacist
# Run with: streamlit run app.py

import streamlit as st
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from pipeline import run_pipeline

# ── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title="CausalMed",
    page_icon="🧬",
    layout="wide"
)

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f0f1a; }
    .stApp { background-color: #0f0f1a; color: white; }

    .section-header {
        font-size: 1.1em;
        font-weight: bold;
        margin: 16px 0 8px 0;
        padding-bottom: 4px;
        border-bottom: 1px solid #333;
    }

    .causal-card {
        background: #0d2b0d;
        border-radius: 10px;
        padding: 16px;
        margin: 10px 0;
        border-left: 5px solid #00cc44;
    }

    .associative-card {
        background: #1a1a0d;
        border-radius: 10px;
        padding: 16px;
        margin: 10px 0;
        border-left: 5px solid #ccaa00;
    }

    .novel-card {
        background: #1a0d00;
        border-radius: 10px;
        padding: 16px;
        margin: 10px 0;
        border-left: 5px solid #ff6600;
    }

    .contradicted-card {
        background: #1a0000;
        border-radius: 10px;
        padding: 16px;
        margin: 10px 0;
        border-left: 5px solid #cc0000;
    }

    .drug-card {
        background: #0d0d2b;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 4px 0;
        border-left: 4px solid #6644cc;
        display: inline-block;
        width: 100%;
    }

    .risk-high   { color: #ff4444; font-weight: bold; }
    .risk-medium { color: #ffaa00; font-weight: bold; }
    .risk-low    { color: #44ff88; font-weight: bold; }

    .mechanism-box {
        background: #111122;
        border-radius: 6px;
        padding: 10px;
        margin: 8px 0;
        font-size: 0.9em;
        font-style: italic;
        color: #aaaacc;
    }

    .badge-causal      { background:#006622; color:white; padding:3px 10px; border-radius:12px; font-size:0.8em; }
    .badge-associative { background:#665500; color:white; padding:3px 10px; border-radius:12px; font-size:0.8em; }
    .badge-novel       { background:#663300; color:white; padding:3px 10px; border-radius:12px; font-size:0.8em; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────
st.markdown("# 🧬 CausalMed")
st.markdown("**Agentic AI for Causal Gene-Disease Relation Extraction**")
st.caption("Reads thousands of biomedical papers and tells you what is CAUSAL vs what is merely associated.")
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
    "doctor":     "👨‍⚕️ **Doctor Mode** — Enter a patient's gene mutation. Get causal disease risks, approved drugs, and active trials.",
    "researcher": "🔬 **Researcher Mode** — Explore all causal and associative findings, novel hypotheses, and contradictions across literature.",
    "pharmacist": "💊 **Pharmacist Mode** — Find approved drugs and mechanisms for any gene or disease target."
}
st.info(mode_descriptions[mode])

# ── Input ─────────────────────────────────────────────────────
st.markdown("### 🔍 Enter Query")

if mode == "doctor":
    query_input = st.text_input(
        "Patient gene mutation",
        placeholder="e.g. BRCA1, TP53, EGFR, ALK"
    )
    query = f"{query_input} cancer causal mechanism pathway" if query_input else ""

elif mode == "researcher":
    query_input = st.text_input(
        "Gene or disease to investigate",
        placeholder="e.g. BRCA1 breast cancer, TP53 lung cancer"
    )
    query = f"{query_input} causal mechanism" if query_input else ""

else:
    query_input = st.text_input(
        "Gene target or disease",
        placeholder="e.g. EGFR, ALK, HER2"
    )
    query = f"{query_input} drug target treatment mechanism" if query_input else ""

run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

if run_btn and query_input:
    with st.spinner("CausalMed is reading papers and reasoning... (~2 minutes)"):
        try:
            result = run_pipeline(query)
            st.session_state["result"]       = result
            st.session_state["query_input"]  = query_input
            st.success("✅ Analysis complete!")
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

# ── Display Results ───────────────────────────────────────────
if "result" in st.session_state:
    result      = st.session_state["result"]
    query_input = st.session_state.get("query_input", "")
    summary     = result.get("summary", {})

    st.divider()
    st.markdown(f"## Results for: **{query_input}**")

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📄 Papers Analyzed",    summary.get("total_relations_analyzed", 0))
    c2.metric("✅ Causal & Validated",  summary.get("validated_count", 0))
    c3.metric("🔶 Novel Hypotheses",    summary.get("novel_hypothesis_count", 0))
    c4.metric("❌ Contradicted",        summary.get("contradicted_count", 0))

    st.divider()

    # ── DOCTOR MODE ───────────────────────────────────────────
    if mode == "doctor":

        validated    = result.get("validated_findings", [])
        novel        = result.get("novel_hypotheses", [])
        contradicted = result.get("contradicted_findings", [])
        all_relations = result.get("validated_findings", []) + \
                        result.get("novel_hypotheses", [])

        # Non-causal associations from full output
        non_causal = [r for r in all_relations
                      if r.get("causal_label") == "non-causal"]

        # ── CAUSAL LINKS ──
        st.markdown("### ✅ Causal Disease Links")
        st.caption("These genes have been identified as **causally linked** to diseases — not just associated. Backed by literature + ClinVar.")

        if validated:
            for rel in validated:
                confidence = rel.get("confidence", 0)
                risk       = "🔴 HIGH RISK" if confidence > 0.8 else \
                             "🟡 MEDIUM RISK" if confidence > 0.6 else "🟢 LOW RISK"

                st.markdown(f"""
                <div class="causal-card">
                    <span class="badge-causal">✅ CAUSAL</span>&nbsp;&nbsp;
                    <strong>{rel['gene']} → {rel['disease']}</strong>
                    &nbsp;&nbsp;<span>Risk: {risk} &nbsp;|&nbsp; Confidence: {confidence:.0%}</span>
                    <div class="mechanism-box">
                        📖 <em>"{rel.get('source_sentence', '')[:250]}..."</em>
                    </div>
                    <div style="margin-top:8px; font-size:0.9em;">
                        🧠 <strong>Why causal:</strong> {rel.get('analyst_reasoning', 'N/A')[:300]}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Drug candidates for this gene
                drugs = rel.get("drug_candidates", [])
                if drugs:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;💊 **Drugs targeting {rel['gene']}:** " +
                                " &nbsp;|&nbsp; ".join([f"`{d}`" for d in drugs]))

                # Clinical trials
                trials = rel.get("clinical_trials", [])
                if trials:
                    trial_links = " &nbsp; ".join([
                        f"[{t}](https://clinicaltrials.gov/study/{t})" for t in trials[:3]
                    ])
                    st.markdown(f"&nbsp;&nbsp;&nbsp;🏥 **Active trials:** {trial_links}")

                st.markdown("---")
        else:
            st.info("No validated causal links found for this query. Try a more specific gene name.")

        # ── NOVEL HYPOTHESES ──
        if novel:
            st.markdown("### 🔶 Potential Causal Links (Novel — Not Yet in Databases)")
            st.caption("These links were identified as causal by our AI but are not yet confirmed in clinical databases. Potential new discoveries.")
            for rel in novel[:3]:
                st.markdown(f"""
                <div class="novel-card">
                    <span class="badge-novel">🔶 NOVEL HYPOTHESIS</span>&nbsp;&nbsp;
                    <strong>{rel['gene']} → {rel['disease']}</strong>
                    &nbsp;&nbsp;Confidence: {rel.get('confidence', 0):.0%}
                    <div class="mechanism-box">
                        📖 <em>"{rel.get('source_sentence', '')[:200]}..."</em>
                    </div>
                    <div style="margin-top:8px; font-size:0.9em;">
                        🧠 {rel.get('analyst_reasoning', '')[:250]}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ── ASSOCIATIVE ONLY ──
        st.markdown("### ⚠️ Associations Only (Not Causal)")
        st.caption("These gene-disease pairs appear together in literature but our system determined the relationship is **not causal** — just co-occurrence or correlation.")

        non_causal_validated = [r for r in result.get("validated_findings", []) +
                                result.get("novel_hypotheses", [])
                                if r.get("classification") == "non_causal"]

        if non_causal_validated:
            for rel in non_causal_validated[:5]:
                st.markdown(f"""
                <div class="associative-card">
                    <span class="badge-associative">⚠️ ASSOCIATIVE</span>&nbsp;&nbsp;
                    <strong>{rel['gene']} → {rel['disease']}</strong>
                    <div class="mechanism-box">
                        📖 <em>"{rel.get('source_sentence', '')[:200]}..."</em>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No purely associative findings — all surviving relations were classified as causal.")

        # ── CONTRADICTIONS ──
        if contradicted:
            st.markdown("### ❌ Contradicted Findings")
            st.caption("Papers disagree on these links.")
            for rel in contradicted:
                st.markdown(f"""
                <div class="contradicted-card">
                    <strong>❌ {rel['gene']} → {rel['disease']}</strong><br>
                    <small>Contradicting papers: {', '.join(rel.get('contradictions', []))}</small>
                </div>
                """, unsafe_allow_html=True)

        # ── CAUSAL CHAINS ──
        chains = result.get("causal_chains", [])
        if chains:
            st.markdown("### 🔗 Biological Causal Pathway")
            st.caption("How the gene causally leads to disease through intermediate steps.")
            for chain in chains:
                path = " → ".join(chain["chain"])
                st.markdown(f"**{path}** (confidence: {chain['overall_confidence']:.0%})")
                for hop in chain["hops"]:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;↳ `{hop['from']}` causes `{hop['to']}`: "
                                f"*\"{hop['sentence'][:150]}...\"*")

    # ── RESEARCHER MODE ───────────────────────────────────────
    elif mode == "researcher":
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "✅ Validated Causal",
            "🔶 Novel Hypotheses",
            "⚠️ Associative Only",
            "❌ Contradicted",
            "🔗 Causal Chains"
        ])

        with tab1:
            validated = result.get("validated_findings", [])
            if validated:
                for rel in validated:
                    with st.expander(f"✅ {rel['gene']} → {rel['disease']} "
                                     f"| Confidence: {rel['confidence']:.0%} "
                                     f"| Reliability: {rel['reliability_score']:.2f}"):
                        st.markdown(f"**Relationship type:** ✅ CAUSAL — confirmed by ClinVar")
                        st.markdown(f"**Source sentence:** *\"{rel['source_sentence']}\"*")
                        st.markdown(f"**Analyst reasoning:** {rel.get('analyst_reasoning', '')}")
                        st.markdown(f"**Critic feedback:** {rel.get('critic_feedback', '')}")
                        st.markdown(f"**ClinVar score:** {rel.get('db_score', 0):.2f}")
                        st.markdown(f"**Evidence count:** {rel.get('evidence_count', 1)} papers")
                        if rel.get("drug_candidates"):
                            st.markdown(f"**Drugs:** {', '.join(rel['drug_candidates'])}")
                        if rel.get("clinical_trials"):
                            st.markdown(f"**Trials:** {', '.join(rel['clinical_trials'][:3])}")
            else:
                st.info("No validated causal findings.")

        with tab2:
            novel = result.get("novel_hypotheses", [])
            if novel:
                for rel in novel:
                    with st.expander(f"🔶 {rel['gene']} → {rel['disease']} "
                                     f"| Confidence: {rel['confidence']:.0%}"):
                        st.markdown("**Relationship type:** 🔶 NOVEL HYPOTHESIS — causal but not in any database yet")
                        st.markdown(f"**Source:** *\"{rel['source_sentence']}\"*")
                        st.markdown(f"**Analyst reasoning:** {rel.get('analyst_reasoning', '')}")
                        st.markdown(f"**Note:** Not found in ClinVar — potential new discovery")
            else:
                st.info("No novel hypotheses found.")

        with tab3:
            st.caption("These relations survived NER and model extraction but were classified as non-causal by the Analyst-Critic loop.")
            all_rels = result.get("validated_findings", []) + result.get("novel_hypotheses", [])
            non_causal = [r for r in all_rels if r.get("causal_label") == "non-causal"]
            if non_causal:
                for rel in non_causal[:10]:
                    with st.expander(f"⚠️ {rel['gene']} → {rel['disease']} — ASSOCIATIVE"):
                        st.markdown(f"**Source:** *\"{rel['source_sentence']}\"*")
                        st.markdown(f"**Critic reasoning:** {rel.get('critic_feedback', 'Classified as non-causal')}")
            else:
                st.info("No purely associative findings.")

        with tab4:
            contradicted = result.get("contradicted_findings", [])
            if contradicted:
                for rel in contradicted:
                    with st.expander(f"❌ {rel['gene']} → {rel['disease']}"):
                        st.markdown(f"**Contradicting papers:** {', '.join(rel.get('contradictions', []))}")
                        st.markdown(f"**Source:** *\"{rel['source_sentence']}\"*")
            else:
                st.info("No contradictions found.")

        with tab5:
            chains = result.get("causal_chains", [])
            if chains:
                for chain in chains:
                    path = " → ".join(chain["chain"])
                    with st.expander(f"🔗 {path} | Confidence: {chain['overall_confidence']:.0%}"):
                        for hop in chain["hops"]:
                            st.markdown(f"**{hop['from']} → {hop['to']}** "
                                        f"(confidence: {hop['confidence']:.0%})")
                            st.markdown(f"*\"{hop['sentence'][:200]}\"*")
                            st.divider()
            else:
                st.info("No multi-hop chains found.")

        # Knowledge graph
        graph_path = os.path.join(os.path.dirname(__file__), 'outputs', 'knowledge_graph.html')
        if os.path.exists(graph_path):
            st.markdown("### 🕸️ Knowledge Graph")
            with open(graph_path, 'r') as f:
                st.components.v1.html(f.read(), height=700, scrolling=True)

    # ── PHARMACIST MODE ───────────────────────────────────────
    else:
        st.markdown("### 💊 Drug Intelligence Report")
        st.caption("Approved drugs targeting genes with validated causal disease links.")

        drug_data = {}
        for rel in result.get("validated_findings", []) + result.get("novel_hypotheses", []):
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
                    "mechanism": rel.get("analyst_reasoning", "")
                }
            drug_data[gene]["drugs"].extend(drugs)
            drug_data[gene]["diseases"].append(rel.get("disease", ""))
            drug_data[gene]["trials"].extend(rel.get("clinical_trials", []))

        if drug_data:
            for gene, data in drug_data.items():
                with st.expander(f"🧬 {gene} — {len(set(data['drugs']))} drug(s) available"):
                    st.markdown(f"**Causally linked diseases:** {', '.join(set(data['diseases']))}")
                    st.markdown(f"**Biological mechanism:** {data['mechanism'][:300]}")
                    st.markdown("**Approved drug candidates:**")
                    for drug in set(data["drugs"]):
                        st.markdown(f"""
                        <div class="drug-card">💊 {drug}</div>
                        """, unsafe_allow_html=True)
                    if data["trials"]:
                        st.markdown("**Active clinical trials:**")
                        for trial in list(set(data["trials"]))[:5]:
                            st.markdown(f"- [{trial}](https://clinicaltrials.gov/study/{trial})")
        else:
            st.info("No drug candidates found. Try querying a specific gene like EGFR, ALK, or BRCA1.")

    # ── Download ──────────────────────────────────────────────
    st.divider()
    st.download_button(
        label="⬇️ Download Full JSON Report",
        data=json.dumps(result, indent=2),
        file_name=f"causalmed_{query_input}_{result.get('timestamp','')[:10]}.json",
        mime="application/json"
    )