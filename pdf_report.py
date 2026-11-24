# pdf_report.py
# PDF report generator for CausalMed.
# Replaces JSON download with a structured, readable PDF.
# Supports Doctor, Researcher, and Pharmacist mode layouts.
#
# Dependency: reportlab  (pip install reportlab)

from agents.evidence_scoring import SOURCE_CLAIM_METHODS, evidence_summary
from io import BytesIO
from xml.sax.saxutils import escape
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.platypus import PageBreak

# ── Colour constants ──────────────────────────────────────────
NAVY      = colors.HexColor("#1C3557")
TEAL      = colors.HexColor("#1A6B72")
GREEN     = colors.HexColor("#1D6A41")
RED       = colors.HexColor("#9B2335")
GOLD      = colors.HexColor("#96700A")
PURPLE    = colors.HexColor("#4B3B8C")
SLATE     = colors.HexColor("#334E68")
MUTED     = colors.HexColor("#64748B")
LIGHT     = colors.HexColor("#EEF3F8")
WHITE     = colors.white
BLACK     = colors.black

# ── Style helpers ─────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()

    custom = {
        "title": ParagraphStyle(
            "title", parent=base["Title"],
            fontSize=22, textColor=NAVY, spaceAfter=4,
            fontName="Helvetica-Bold", alignment=TA_LEFT,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontSize=11, textColor=TEAL, spaceAfter=10,
            fontName="Helvetica-Oblique", alignment=TA_LEFT,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"],
            fontSize=14, textColor=WHITE, spaceAfter=6, spaceBefore=14,
            fontName="Helvetica-Bold", alignment=TA_LEFT,
            backColor=NAVY, borderPad=5, leftIndent=-6, rightIndent=-6,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontSize=12, textColor=NAVY, spaceAfter=4, spaceBefore=10,
            fontName="Helvetica-Bold", alignment=TA_LEFT,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"],
            fontSize=10, textColor=TEAL, spaceAfter=3, spaceBefore=6,
            fontName="Helvetica-Bold", alignment=TA_LEFT,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontSize=9.5, textColor=SLATE, spaceAfter=4,
            fontName="Helvetica", alignment=TA_JUSTIFY,
            leading=14,
        ),
        "italic": ParagraphStyle(
            "italic", parent=base["Normal"],
            fontSize=9, textColor=MUTED, spaceAfter=3,
            fontName="Helvetica-Oblique", alignment=TA_LEFT,
            leftIndent=10,
        ),
        "label_causal": ParagraphStyle(
            "label_causal", parent=base["Normal"],
            fontSize=9, textColor=GREEN, fontName="Helvetica-Bold",
        ),
        "label_novel": ParagraphStyle(
            "label_novel", parent=base["Normal"],
            fontSize=9, textColor=GOLD, fontName="Helvetica-Bold",
        ),
        "label_contra": ParagraphStyle(
            "label_contra", parent=base["Normal"],
            fontSize=9, textColor=RED, fontName="Helvetica-Bold",
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"],
            fontSize=8.5, textColor=MUTED, fontName="Helvetica",
        ),
        "chain": ParagraphStyle(
            "chain", parent=base["Normal"],
            fontSize=9.5, textColor=TEAL, fontName="Helvetica-Bold",
            spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"],
            fontSize=8, textColor=MUTED, fontName="Helvetica",
            alignment=TA_CENTER,
        ),
    }
    return custom


def _hr(color=NAVY, thickness=0.8):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=6, spaceBefore=2)


def _spacer(h=4):
    return Spacer(1, h * mm)


def _section_header(text: str, styles: dict) -> list:
    """Navy background section heading."""
    return [
        _spacer(3),
        Paragraph(f"  {text}", styles["h1"]),
        _spacer(2),
    ]


def _summary_table(summary: dict, styles: dict):
    """4-column summary metrics table."""
    data = [
        ["Pairs Analyzed", "Explicit claims", "Contextual", "Conflict flagged"],
        [
            str(summary.get("total_relations_analyzed", 0)),
            str(summary.get("validated_count", 0)),
            str(summary.get("novel_hypothesis_count", 0)),
            str(summary.get("contradicted_count", 0)),
        ]
    ]
    col_w = [38 * mm] * 4
    tbl = Table(data, colWidths=col_w)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0), 9),
        ("FONTNAME",     (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 1), (-1, 1), 16),
        ("TEXTCOLOR",    (0, 1), (0, 1), NAVY),
        ("TEXTCOLOR",    (1, 1), (1, 1), GREEN),
        ("TEXTCOLOR",    (2, 1), (2, 1), GOLD),
        ("TEXTCOLOR",    (3, 1), (3, 1), RED),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, 1), [LIGHT]),
        ("BOX",          (0, 0), (-1, -1), 0.5, NAVY),
        ("INNERGRID",    (0, 0), (-1, -1), 0.3, colors.HexColor("#C8D6E5")),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    return tbl


# ── Page header / footer callback ────────────────────────────

def _page_header_footer(canvas, doc, query: str, mode: str, timestamp: str):
    canvas.saveState()
    w, h = A4

    # Top bar
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 22 * mm, w, 22 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(15 * mm, h - 13 * mm, "CausalMed")
    canvas.setFont("Helvetica", 9)
    canvas.drawString(15 * mm, h - 19 * mm,
                      f"Agentic AI — Causal Gene-Disease Analysis  |  Mode: {mode.title()}")
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(w - 15 * mm, h - 13 * mm, f"Query: {query}")
    canvas.drawRightString(w - 15 * mm, h - 19 * mm, timestamp)

    # Bottom bar
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, w, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(w / 2, 3.5 * mm,
                             f"CausalMed  |  Page {doc.page}  |  — Research Use")
    canvas.restoreState()


# ── Mode-specific section builders ───────────────────────────

def _doctor_sections(result: dict, styles: dict) -> list:
    """Summarize explicit literature claims and related database records."""
    story = []
    validated    = result.get("validated_findings", [])
    contradicted = result.get("contradicted_findings", [])
    chains       = result.get("causal_chains", [])

    # ── Causal Disease Links ──
    story += _section_header("Explicit disease claims", styles)
    story.append(Paragraph(
        "These sentences contain an automatically extracted gene-to-disease claim. "
        "ClinVar contributes gene-level annotations.",
        styles["body"]
    ))
    story.append(_spacer(3))

    if validated:
        for rel in validated:
            conf  = rel.get("confidence", 0)
            gene  = rel.get("gene", "")
            dis   = rel.get("disease", "")
            drugs = rel.get("drug_candidates", [])
            trials = rel.get("clinical_trials", [])

            # Relation row
            rel_data = [[
                Paragraph(f"✓  {gene}  →  {dis}", ParagraphStyle(
                    "rc", parent=styles["h2"], textColor=GREEN, spaceAfter=0)),
                Paragraph(f"Model score: {conf:.0%}", styles["small"]),
            ]]
            rt = Table(rel_data, colWidths=[110 * mm, 50 * mm])
            rt.setStyle(TableStyle([
                ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#EEF3F8")),
                ("BOX",          (0, 0), (-1, -1), 0.5, GREEN),
                ("LEFTPADDING",  (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING",   (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
                ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ]))

            # Evidence sentence
            sent = rel.get("source_sentence", "")
            # Analyst reasoning — full text (no truncation)
            reasoning = evidence_summary(rel)

            block = KeepTogether([
                rt,
                _spacer(1),
                Paragraph(f"Evidence: \"{sent}\"", styles["italic"]),
                Paragraph(f"Evidence summary: {escape(reasoning)}", styles["body"]) if reasoning else Spacer(1, 0),
            ])

            if drugs:
                drug_str = "  |  ".join(drugs)
                block = KeepTogether([
                    rt,
                    _spacer(1),
                    Paragraph(f"Evidence: \"{sent}\"", styles["italic"]),
                    Paragraph(f"Evidence summary: {escape(reasoning)}", styles["body"]) if reasoning else Spacer(1, 0),
                    Paragraph(f"💊 ChEMBL candidates for {gene}: {drug_str}", styles["small"]),
                ])

            if trials:
                trial_str = "  ·  ".join(trials[:4])
                block = KeepTogether([
                    rt,
                    _spacer(1),
                    Paragraph(f"Evidence: \"{sent}\"", styles["italic"]),
                    Paragraph(f"Evidence summary: {escape(reasoning)}", styles["body"]) if reasoning else Spacer(1, 0),
                    Paragraph(f"💊 ChEMBL candidates for {gene}: {'  |  '.join(drugs)}", styles["small"]) if drugs else Spacer(1, 0),
                    Paragraph(f"🏥 Active clinical trials: {trial_str}", styles["small"]),
                ])

            story.append(block)
            story.append(_spacer(3))
    else:
        story.append(Paragraph("No explicit disease claims found.", styles["body"]))

    # ── Contradictions ──
    if contradicted:
        story += _section_header("Contradicted Findings — Use With Caution", styles)
        story.append(Paragraph(
            "The pipeline found potential conflicts using keywords in other papers. "
            "Review the cited papers to assess each conflict.",
            styles["body"]
        ))
        story.append(_spacer(2))
        for rel in contradicted:
            story.append(Paragraph(
                f"✗  {rel.get('gene')} → {rel.get('disease')}  "
                f"(contradicting papers: {', '.join(rel.get('contradictions', []))})",
                ParagraphStyle("contra", parent=styles["body"], textColor=RED)
            ))

    # ── Causal chains ──
    if chains:
        story += _section_header("Gene-Disease Graph Links", styles)
        story.append(Paragraph(
            "Graph links show gene-disease pairs from the retrieved literature.",
            styles["body"]
        ))
        story.append(_spacer(2))
        for chain in chains[:5]:
            path = " → ".join(chain["chain"])
            story.append(Paragraph(f"▶  {path}  (confidence: {chain['overall_confidence']:.0%})",
                                   styles["chain"]))
            for hop in chain["hops"]:
                story.append(Paragraph(
                    f"      {hop['from']} / {hop['to']}: \"{hop['sentence'][:180]}...\"",
                    styles["italic"]
                ))
            story.append(_spacer(2))

    return story


def _researcher_sections(result: dict, styles: dict, show_scoring_details: bool = False) -> list:
    """
    Researcher mode: full detail view.
    Shows: All validated, novel hypotheses, associative, contradicted, chains, full scores.
    """
    story = []

    # ── Validated causal ──
    story += _section_header("Explicit literature claims", styles)
    validated = result.get("validated_findings", [])
    if validated:
        for rel in validated:
            conf       = rel.get("confidence", 0)
            reasoning  = evidence_summary(rel)
            feedback   = rel.get("critic_feedback", "")
            sent       = rel.get("source_sentence", "")

            header_data = [[
                Paragraph(f"{rel.get('gene')} → {rel.get('disease')}", styles["h2"]),
                Paragraph(f"Sentence classifier: {conf:.0%}  |  Papers mentioning pair: {rel.get('evidence_count', 1)}",
                          styles["small"]),
            ]]
            ht = Table(header_data, colWidths=[80 * mm, 80 * mm])
            ht.setStyle(TableStyle([
                ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#E8F5E9")),
                ("BOX",          (0, 0), (-1, -1), 0.5, GREEN),
                ("LEFTPADDING",  (0, 0), (-1, -1), 6),
                ("TOPPADDING",   (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
                ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ]))

            drugs  = rel.get("drug_candidates", [])
            trials = rel.get("clinical_trials", [])

            story.append(KeepTogether([
                ht,
                _spacer(1),
                Paragraph(f"Source: \"{sent}\"", styles["italic"]),
                Paragraph(f"Evidence summary: {escape(reasoning)}", styles["body"]),
                Paragraph(f"Critic feedback: {escape(feedback)}", styles["small"]) if show_scoring_details and rel.get("checklist_status") == "available" and feedback else Spacer(1, 0),
                Paragraph(f"Drugs: {', '.join(drugs)}", styles["small"]) if drugs else Spacer(1, 0),
                Paragraph(f"Active trials: {', '.join(trials[:4])}", styles["small"]) if trials else Spacer(1, 0),
            ]))
            story.append(_spacer(3))
    else:
        story.append(Paragraph("No explicit literature claims.", styles["body"]))

    # ── Novel hypotheses ──
    story += _section_header("Contextual mentions", styles)
    novel = result.get("novel_hypotheses", [])
    if novel:
        story.append(Paragraph(
            "These sentences mention the pair without an extracted explicit causal claim.",
            styles["body"]
        ))
        story.append(_spacer(2))
        for rel in novel:
            reasoning = evidence_summary(rel)
            story.append(Paragraph(
                f"◈  {rel.get('gene')} → {rel.get('disease')}  (confidence: {rel.get('confidence', 0):.0%})",
                ParagraphStyle("novel_h", parent=styles["h3"], textColor=GOLD)
            ))
            story.append(Paragraph(f"Source: \"{rel.get('source_sentence', '')}\"", styles["italic"]))
            story.append(Paragraph(f"Evidence summary: {escape(reasoning)}", styles["body"]))
            story.append(_spacer(2))
    else:
        story.append(Paragraph("No contextual mentions found.", styles["body"]))

    # ── Associative only ──
    story += _section_header("Pairs with Insufficient Causal Evidence", styles)
    non_causal = result.get("non_causal_findings", [])
    if non_causal:
        story.append(Paragraph(
            "The sentence classifier did not detect causal wording for these candidate pairs.",
            styles["body"]
        ))
        story.append(_spacer(2))
        for rel in non_causal[:10]:
            feedback = rel.get("critic_feedback", "Classified as non-causal by Critic Agent.")
            story.append(Paragraph(
                f"○  {rel.get('gene')} → {rel.get('disease')}",
                ParagraphStyle("assoc_h", parent=styles["h3"], textColor=MUTED)
            ))
            story.append(Paragraph(f"Source: \"{rel.get('source_sentence', '')}\"", styles["italic"]))
            if show_scoring_details and rel.get("checklist_status") == "available" and feedback:
                story.append(Paragraph(f"Critic reasoning: {escape(feedback)}", styles["small"]))
            story.append(_spacer(1))
    else:
        story.append(Paragraph("No purely associative findings.", styles["body"]))

    # ── Contradictions ──
    story += _section_header("Contradicted Findings", styles)
    contradicted = result.get("contradicted_findings", [])
    if contradicted:
        for rel in contradicted:
            story.append(Paragraph(
                f"✗  {rel.get('gene')} → {rel.get('disease')}",
                ParagraphStyle("contra2", parent=styles["h3"], textColor=RED)
            ))
            story.append(Paragraph(
                f"Contradicting paper IDs: {', '.join(rel.get('contradictions', []))}",
                styles["small"]
            ))
            story.append(Paragraph(f"Source: \"{rel.get('source_sentence', '')}\"", styles["italic"]))
            story.append(_spacer(1))
    else:
        story.append(Paragraph("No contradictions detected.", styles["body"]))

    # ── Causal chains ──
    story += _section_header("Gene-Disease Graph Links", styles)
    chains = result.get("causal_chains", [])
    if chains:
        for chain in chains:
            path = " → ".join(chain["chain"])
            story.append(Paragraph(f"▶  {path}  (confidence: {chain['overall_confidence']:.0%})",
                                   styles["chain"]))
            for hop in chain["hops"]:
                story.append(Paragraph(
                    f"      {hop['from']} → {hop['to']}  (conf: {hop['confidence']:.0%}):  "
                    f"\"{hop['sentence'][:200]}...\"",
                    styles["italic"]
                ))
            story.append(_spacer(2))
    else:
        story.append(Paragraph("No graph links found.", styles["body"]))

    return story


def _pharmacist_sections(result: dict, styles: dict) -> list:
    """
    Pharmacist mode: drug intelligence view.
    Shows: Per-gene drug table, mechanism, active trials.
    Groups by gene → drugs → trials.
    Does NOT show: raw confidence scores, non-causal relations.
    """
    story = []
    story += _section_header("Drug Intelligence Report", styles)
    story.append(Paragraph(
        "ChEMBL drug candidates and ClinicalTrials.gov search results for genes in the literature findings.",
        styles["body"]
    ))
    story.append(_spacer(4))

    # Build per-gene drug dict
    drug_data = {}
    for rel in result.get("validated_findings", []) + result.get("novel_hypotheses", []):
        if rel.get("causal_label") != "causal":
            continue
        gene  = rel.get("gene", "Unknown")
        drugs = rel.get("drug_candidates", [])
        if not drugs:
            continue
        if gene not in drug_data:
            drug_data[gene] = {
                "diseases":   [],
                "drugs":      set(),
                "trials":     set(),
                "mechanism":  evidence_summary(rel),
                "confidence": rel.get("confidence", 0),
            }
        drug_data[gene]["drugs"].update(drugs)
        drug_data[gene]["diseases"].append(rel.get("disease", ""))
        drug_data[gene]["trials"].update(rel.get("clinical_trials", []))

    if not drug_data:
        story.append(Paragraph(
            "No drug candidates found for this query. Try a specific gene such as EGFR, ALK, or BRCA1.",
            styles["body"]
        ))
        return story

    for gene, data in drug_data.items():
        drugs   = sorted(data["drugs"])
        trials  = sorted(data["trials"])
        diseases = list(set(data["diseases"]))

        # Gene header table
        gene_hdr = [[
            Paragraph(f"🧬  {gene}", ParagraphStyle(
                "gname", parent=styles["h2"], textColor=WHITE, fontName="Helvetica-Bold")),
            Paragraph(f"{len(drugs)} drug(s)  |  {len(trials)} trial(s)  |  "
                      f"Confidence: {data['confidence']:.0%}",
                      ParagraphStyle("gmeta", parent=styles["small"],
                                     textColor=colors.HexColor("#A8C8DC"))),
        ]]
        gh = Table(gene_hdr, colWidths=[80 * mm, 80 * mm])
        gh.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), NAVY),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",   (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ]))

        # Diseases
        dis_str = ", ".join(diseases) if diseases else "—"
        mech    = data["mechanism"]

        # Drug table
        drug_rows = [["Drug Name", "Source"]]
        for d in drugs:
            drug_rows.append([d, "ChEMBL / EBI"])
        dt = Table(drug_rows, colWidths=[100 * mm, 60 * mm])
        dt.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), TEAL),
            ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
            ("BOX",          (0, 0), (-1, -1), 0.4, TEAL),
            ("INNERGRID",    (0, 0), (-1, -1), 0.3, colors.HexColor("#C8D6E5")),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ]))

        # Trials
        trial_content = []
        if trials:
            trial_content = [
                Paragraph("Active Clinical Trials:", styles["h3"]),
            ] + [
                Paragraph(f"• {t}  →  clinicaltrials.gov/study/{t}", styles["small"])
                for t in list(trials)[:6]
            ]

        story.append(KeepTogether([
            gh,
            _spacer(1),
            Paragraph(f"Diseases in the literature findings: {dis_str}", styles["body"]),
            Paragraph(f"Evidence summary: {escape(mech)}", styles["body"]) if mech else Spacer(1, 0),
            _spacer(2),
            Paragraph("ChEMBL Drug Candidates:", styles["h3"]),
            dt,
            _spacer(2),
            *trial_content,
            _spacer(4),
        ]))

    return story


# ── Public entry point ────────────────────────────────────────

def generate_pdf(result: dict, query: str, mode: str, show_scoring_details: bool = False) -> bytes:
    """
    Generate a PDF report from the pipeline result dict.

    Args:
        result:  The dict returned by run_pipeline()
        query:   The original user query string
        mode:    "doctor" | "researcher" | "pharmacist"

    Returns:
        PDF bytes suitable for st.download_button(data=...)
    """
    buf = BytesIO()
    timestamp = datetime.now().strftime("%Y-%m-%d  %H:%M")

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=28 * mm,
        bottomMargin=18 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        title=f"CausalMed Report — {query}",
        author="CausalMed Agentic AI",
    )

    styles = _styles()
    story  = []

    # ── Cover block ──
    mode_labels = {
        "doctor":     "Doctor Mode  —  Literature Overview",
        "researcher": "Researcher Mode  —  Full Causal Analysis",
        "pharmacist": "Pharmacist Mode  —  Drug Intelligence",
    }

    story.append(Paragraph("CausalMed", styles["title"]))
    story.append(Paragraph("Agentic AI for Causal Gene-Disease Relation Extraction", styles["subtitle"]))
    story.append(_hr(TEAL, 1.5))
    story.append(Paragraph(f"Report mode: {mode_labels.get(mode, mode)}", styles["h3"]))
    story.append(Paragraph(f"Query: {query}", styles["body"]))
    story.append(Paragraph(f"Generated: {timestamp}", styles["small"]))
    story.append(_spacer(4))

    # ── Summary table ──
    summary = result.get("summary", {})
    if result.get("evidence_method") in SOURCE_CLAIM_METHODS:
        story.append(_summary_table(summary, styles))
    story.append(_spacer(5))

    # ── Mode-specific content ──
    if result.get("evidence_method") not in SOURCE_CLAIM_METHODS:
        story.append(Paragraph("Historical report using the earlier weighted method. Rerun the query to extract explicit claims.", styles["body"]))
        for group in ("validated_findings", "novel_hypotheses", "non_causal_findings", "contradicted_findings"):
            for rel in result.get(group, []):
                source = f"{rel.get('gene', '')} / {rel.get('disease', '')} (PMID {rel.get('source_paper', '')})"
                story.append(Paragraph(escape(source), styles["h3"]))
                story.append(Paragraph(escape(rel.get("source_sentence", "")), styles["body"]))
    elif mode == "doctor":
        story += _doctor_sections(result, styles)
    elif mode == "researcher":
        story += _researcher_sections(result, styles, show_scoring_details)
    else:
        story += _pharmacist_sections(result, styles)

    if result.get("review_findings"):
        story += _section_header("Findings needing review", styles)
        for rel in result["review_findings"]:
            heading = f"{rel['gene']} → {rel['disease']} (PMID {rel['source_paper']})"
            story.append(Paragraph(escape(heading), styles["h3"]))
            story.append(Paragraph(escape(rel["review_reason"]), styles["body"]))
            story.append(Paragraph(escape(rel["source_sentence"]), styles["italic"]))

    # ── Disclaimer ──
    story.append(_spacer(6))
    story.append(_hr(MUTED, 0.5))
    story.append(Paragraph(
        "DISCLAIMER: This report is generated by an AI system for research and informational purposes only. "
        "It does not constitute medical advice. All findings should be reviewed by a qualified clinician "
        "before clinical application. Causal labels are AI-inferred from literature and database evidence.",
        ParagraphStyle("disc", parent=styles["small"], textColor=MUTED, alignment=TA_JUSTIFY)
    ))

    # Build with page header/footer
    doc.build(
        story,
        onFirstPage=lambda c, d: _page_header_footer(c, d, query, mode, timestamp),
        onLaterPages=lambda c, d: _page_header_footer(c, d, query, mode, timestamp),
    )

    return buf.getvalue()
