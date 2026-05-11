# 🧬 CausalMed — Agentic AI for Causal Gene-Disease Relation Extraction

> *"We don't just find associations. We find causes."*

CausalMed is an end-to-end agentic AI system that reads thousands of biomedical papers and automatically distinguishes **causal** gene-disease relationships from mere **associations** — a problem no existing tool solves reliably at scale.

Built for doctors, researchers, and pharmacists.

---

## 🎯 The Problem

Biomedical literature contains millions of statements like:

- *"BRCA1 is associated with breast cancer"* — **associative**
- *"BRCA1 loss disables DNA repair, directly causing tumor formation"* — **causal**

Existing NLP tools cannot reliably tell the difference. CausalMed solves this.

---

## 🏗️ Architecture

```
User Query (Gene / Disease)
        ↓
Ingestion Agent       → PubMed API — fetches 20 papers
        ↓
NER Agent             → spaCy BC5CDR + NCBI gene database (262,223 genes)
        ↓
Normalization Agent   → MyGene.info — standardizes gene IDs
        ↓
Causal Reasoning      → CRED fine-tuned BioBERT — causal vs non-causal
        ↓
Analyst-Critic Loop   → Llama-3 via Groq — biological reasoning + peer review
        ↓
Validation Agent      → ClinVar — gene-level pathogenic evidence
        ↓
Contradiction Agent   → Flags conflicting evidence across papers
        ↓
Chain Assembly        → Multi-hop causal pathway graph
        ↓
Output Agent          → JSON + Interactive Knowledge Graph
        ↓
Streamlit UI          → Doctor / Researcher / Pharmacist modes
```

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Causal vs Associative** | CRED fine-tuned BioBERT distinguishes causal from associative statements |
| **Analyst-Critic Loop** | LLM agents debate each finding like peer reviewers |
| **Multi-hop Chains** | Assembles Gene → Protein → Pathway → Disease across papers |
| **Novel Hypothesis Detection** | Flags causal links not found in any database |
| **Contradiction Detection** | Identifies papers that dispute each other |
| **Drug Repurposing** | ChEMBL approved drugs for validated gene targets |
| **Clinical Trials** | Live ClinicalTrials.gov links for every finding |
| **Three User Modes** | Doctor, Researcher, Pharmacist — each with tailored output |

---

## 🚀 Setup

### Prerequisites
- Python 3.10+
- Windows / Mac / Linux
- 4GB RAM minimum

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-repo/causalmed.git
cd causalmed

# 2. Create virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install biomedical NER model (one-time)
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz

# 5. Set up environment variables
cp .env.example .env
# Edit .env and add your API keys
```

### API Keys Required

| Key | Where to get | Cost |
|-----|-------------|------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Free |

All other APIs (PubMed, ClinVar, ClinicalTrials.gov, ChEMBL, MyGene.info) require no key.

### Download Fine-tuned Model

Place the `biobert_cred_finetuned/` folder in the project root. It should contain:
```
biobert_cred_finetuned/
├── config.json
├── model.safetensors
├── tokenizer_config.json
└── tokenizer.json
```

---

## 🖥️ Running the App

### Streamlit UI (recommended)
```bash
streamlit run app.py
```
Opens at `http://localhost:8501`

### Pipeline only (terminal)
```bash
python pipeline.py
```

---

## 📁 Project Structure

```
causalmed_pipeline/
│
├── pipeline.py                    # Main LangGraph pipeline
├── state.py                       # Shared state between agents
├── app.py                         # Streamlit UI
├── requirements.txt               # Dependencies
├── .env.example                   # Environment variables template
├── human_genes.txt                # Cached NCBI gene database (auto-generated)
│
├── biobert_cred_finetuned/        # Fine-tuned causal classification model
│   ├── config.json
│   ├── model.safetensors
│   ├── tokenizer_config.json
│   └── tokenizer.json
│
├── agents/
│   ├── ingestion_agent.py         # PubMed paper fetcher
│   ├── ner_agent.py               # Biomedical NER (BC5CDR + NCBI genes)
│   ├── normalization_agent.py     # Gene ID normalization (MyGene.info)
│   ├── causal_reasoning_agent.py  # CRED fine-tuned BioBERT classifier
│   ├── analyst_critic_agent.py    # LLM Analyst-Critic reasoning loop
│   ├── validation_agent.py        # ClinVar + ChEMBL + ClinicalTrials
│   ├── contradiction_agent.py     # Cross-paper contradiction detection
│   ├── chain_assembly_agent.py    # Multi-hop causal pathway builder
│   └── output_agent.py            # JSON + Knowledge graph generator
│
└── outputs/                       # Generated outputs (auto-created)
    ├── causalmed_output_*.json
    └── knowledge_graph.html
```

---

## 🧪 Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Groq API (Llama-3.1-8b-instant) |
| Agent Framework | LangGraph |
| Causal Model | BioBERT fine-tuned on CRED dataset |
| NER | spaCy BC5CDR biomedical model |
| Gene Database | NCBI Homo sapiens gene info (262,223 genes) |
| Memory | ChromaDB |
| Graph | NetworkX + Pyvis |
| UI | Streamlit |
| Literature | PubMed + PMC API |

---

## 🗄️ Database APIs Used

| Database | Purpose | Cost |
|----------|---------|------|
| PubMed (NCBI) | Literature retrieval | Free |
| MyGene.info | Gene ID normalization | Free |
| ClinVar (NCBI) | Gene pathogenicity validation | Free |
| ClinicalTrials.gov | Active trial lookup | Free |
| ChEMBL (EBI) | Drug candidate discovery | Free |

**Total infrastructure cost: $0**

---

## 👥 Team

| Member | Responsibility |
|--------|---------------|
| N | LangGraph pipeline, Ingestion Agent, NER Agent, Chain Assembly |
| S | Causal Reasoning Agent, Analyst-Critic Loop, CRED fine-tuning |
| R | Normalization Agent, Validation Agent, Database APIs |
| P | Contradiction Agent, Output Agent, Streamlit UI |

---

## 📊 Model Performance

| Metric | Score |
|--------|-------|
| F1 Score (Causal) | 0.505 |
| Precision | 0.622 |
| Recall | 0.426 |
| Accuracy | 0.927 |

*Fine-tuned on CRED dataset using BioBERT with class-weighted loss.*

---

## 🎬 Demo Queries

| Mode | Query | What you'll see |
|------|-------|----------------|
| Doctor | `BRCA1` | Disease risks, drugs, trials for BRCA1 patients |
| Doctor | `TP53` | Causal links to multiple cancers |
| Researcher | `EGFR lung cancer` | Full causal analysis with novel hypotheses |
| Pharmacist | `ALK` | Drug candidates and mechanisms |

---

## 📄 Output Format

Every run produces:

**1. JSON knowledge object** (`outputs/causalmed_output_*.json`)
```json
{
  "query": "BRCA1 breast cancer",
  "summary": {
    "validated_count": 6,
    "novel_hypothesis_count": 2,
    "contradicted_count": 1
  },
  "validated_findings": [...],
  "novel_hypotheses": [...],
  "drug_candidates": [...],
  "clinical_trials": [...]
}
```

**2. Interactive knowledge graph** (`outputs/knowledge_graph.html`)
- Visual causal pathway graph
- Color coded: green = validated, orange = novel, red = contradicted

---

## 🏥 Real-World Use Cases

**For Doctors:** Enter a patient's gene mutation → get disease risk assessment + approved drugs + active trials in 2 minutes instead of reading hundreds of papers.

**For Researchers:** Find novel gene-disease hypotheses not yet in any database — potential new discoveries generated automatically.

**For Pharmacists:** Identify approved drugs targeting any gene with validated causal disease links.

---

## ⚠️ Disclaimer

CausalMed is a research tool intended to assist medical professionals. It should not be used as the sole basis for clinical decisions. All findings should be verified by qualified healthcare professionals.

---

## 📜 License

MIT License — see LICENSE file for details.