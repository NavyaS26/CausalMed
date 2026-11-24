# 🧬 CausalMed — Agentic AI for Causal Gene-Disease Relation Extraction

CausalMed is a research demo for reviewing gene-disease statements. Each query retrieves up to 20 PubMed abstracts. BioBERT screens each candidate gene–disease pair in its sentence. A second model checks flagged pairs for a supporting quotation.

---

## 🎯 The Problem

Biomedical literature contains millions of statements like:

- *"BRCA1 is associated with breast cancer"* — **associative**
- *"BRCA1 loss disables DNA repair, directly causing tumor formation"* — **causal**

CausalMed uses those distinctions to rank statements for manual review.

---

## 🏗️ Architecture

```
User Query (Gene / Disease)
        ↓
Ingestion Agent       → PubMed API — fetches 20 papers
        ↓
NER Agent             → spaCy BC5CDR + NCBI gene dictionary + MeSH disease lookup
        ↓
Normalization Agent   → MyGene.info — standardizes gene IDs
        ↓
Causal Reasoning      → CRED fine-tuned BioBERT — causal vs non-causal
        ↓
Analyst-Critic Loop   → Groq sentence assessment and supporting quotation
        ↓
Contradiction Agent   → Flags potential conflicts using keywords
        ↓
Validation Agent      → Groups findings and adds gene-level ClinVar annotations
        ↓
Chain Assembly        → Gene-disease evidence graph
        ↓
Output Agent          → JSON + Interactive Knowledge Graph
        ↓
Streamlit UI          → Doctor / Researcher / Pharmacist modes
```

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Causal vs Associative** | BioBERT screens the specific gene and disease marked in each passage |
| **Analyst-Critic Loop** | The LLM extracts an evidence checklist and the critic summarizes its observations |
| **Graph Links** | Displays gene-disease links from retrieved abstracts |
| **Contextual Mentions** | Displays contextual mentions for review |
| **Contradiction Detection** | Flags possible conflicts for manual review |
| **Drug Candidates** | ChEMBL target and mechanism search results |
| **Clinical Trials** | ClinicalTrials.gov search results when available |
| **Three User Modes** | Doctor, Researcher, Pharmacist — each with tailored output |

---

## 🚀 Setup

### Availability and requirements

The source is available from the repository linked below. The demo requires Python, the BC5CDR spaCy model, the separate CRED fine-tuned BioBERT weights, a Groq API key, and network access to the literature and database services. The model download and the setup commands are listed below.

### Prerequisites
- Python 3.12 (version used for the current dependency pins)
- Windows / Mac / Linux
- 4GB RAM minimum

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/UnisysUIP/2026-Bridging-Biomedical-Literature-and-Experimental-Data-Multi-Agent-Framework-for-Causal-Relation.git causalmed
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
cp .env.example .env  # macOS/Linux
# PowerShell: Copy-Item .env.example .env
# Edit .env and set GROQ_API_KEY
```

### API Keys Required

| Key | Where to get | Cost |
|-----|-------------|------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Free |

Set `NCBI_API_KEY` and `NCBI_EMAIL` in `.env` if available. PubMed and ClinVar requests share an in-process rate limiter and a short-lived response cache. The first disease lookup downloads the [2026 NLM descriptor archive](https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/) to `mesh_data/desc2026.gz`. Later runs use the local archive. Unique, case-insensitive matches to descriptor names and entry terms supply the MeSH identifier and tree paths.

### Download Fine-tuned Model

Download the model from this drive and place it in the folder: https://drive.google.com/drive/folders/101YZ1cDdzX84mxKenBfp2hnnzHxPCLz9?usp=sharing
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
python -X utf8 -m streamlit run app.py
```
Opens at `http://localhost:8501`

### Pipeline only (terminal)
```bash
python -X utf8 pipeline.py
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
│   ├── chain_assembly_agent.py    # Gene-disease graph builder
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
| LLM | Groq API (openai/gpt-oss-20b) |
| Agent Framework | LangGraph |
| Causal Model | BioBERT fine-tuned on CRED dataset |
| NER | spaCy BC5CDR biomedical model |
| Gene Database | NCBI Homo sapiens gene info |
| Graph | NetworkX + Pyvis |
| UI | Streamlit |
| Literature | PubMed abstracts via NCBI E-utilities |

---

## 🗄️ Database APIs Used

| Database | Purpose | Cost |
|----------|---------|------|
| PubMed (NCBI) | Literature retrieval | Free |
| MyGene.info | Gene ID normalization | Free |
| ClinVar (NCBI) | Gene-level pathogenic variant annotation | Free |
| ClinicalTrials.gov | Active trial lookup | Free |
| ChEMBL (EBI) | Drug candidate discovery | Free |

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

*Historical BioBERT model scores reported by the project. The evaluation split and reproduction scripts are pending.*

---

## 🎬 Demo Queries

| Mode | Query | What you'll see |
|------|-------|----------------|
| Doctor | `BRCA1` | BRCA1 literature signals and database annotations |
| Doctor | `TP53` | Literature signals involving TP53 |
| Researcher | `EGFR lung cancer` | Extracted claims, contextual mentions and source sentences |
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
- Gene-disease links from retrieved literature
- The graph shows explicit claims extracted from source sentences. Flagged conflicts are listed in the report.

---

## Interpreting results

**All matching source passages** groups the original sentences by passage and PubMed ID in every view. Each candidate pair gets its own BioBERT input with the target mentions replaced by the CRED markers `@GeneSrc$` and `@DiseaseTgt$`. Other genes and diseases remain in context. Missing, overlapping, or overlength inputs go to review. Every distinct candidate remains in the report. The first 50 screen-positive candidates receive a quote assessment and any further screen-positive candidates are marked for review. The evidence count is the number of distinct analyzed papers mentioning the pair.

Review the cited abstract to assess each candidate relation. ClinVar annotations are gene-level. ChEMBL entries are candidate matches, and trial entries are search results. The JSON keys `validated_findings` and `novel_hypotheses` are retained for existing readers and refer to explicit causal statements and contextual mentions, respectively.

---

## ⚠️ Disclaimer

CausalMed is for literature review and research. Clinical decisions require independent evidence and professional judgment.

---

## 📜 License

The project code is available under the [MIT license](LICENSE). External datasets, model weights, and bundled third-party assets have their own terms.

### How findings are grouped

For each flagged pair, the extractor reads the original sentence. An explicit claim requires a verbatim quotation containing both mentions and an assessment that the authors attribute the outcome to that gene. Descriptions and associations go under contextual mentions. An incomplete assessment or unverifiable quote goes to review. A cross-paper denial is flagged separately. ClinVar record counts, disease category and the number of papers supply context. These categories describe article wording. Researcher mode can show extraction details.

The distinction between evidence description and evidence quality follows the [Evidence Ontology authors' discussion](https://doi.org/10.1093/database/bau075). The grouping rules are specific to CausalMed. New JSON reports use `evidence_method: source_claim_pair_v2`. Reports tagged `source_claim_v1` used whole-sentence screening.

To compare simple search, pair screening, and explicit claims, run the following from the project root with the published CRED test file and the configured Groq service:

```powershell
.\venv\Scripts\python.exe -X utf8 evaluation/check_cred.py outputs/cred-source/data/test_data outputs/cred-eval --pair-screen
```

The comparison uses CRED's marked entities and the papers outside the original 100-pair pilot. Counts are per gene–disease pair per abstract. Retrieval, entity recognition, and overlap with the checkpoint's training data are outside this check.

The quote checker evaluates what the authors attribute to the target gene, including statements written in passive voice. It checks whether the named condition is the outcome and whether the authors qualify the statement as an assumption or association. An explicit claim still needs a verbatim quotation. The checker retries an invalid assessment once. If the assessment remains unavailable, the pair goes to review. New assessed records identify this prompt as `quote_assessment_version: attribution_v2`.

With CRED's `val_data` in the same directory, the following command evaluates eight validation papers selected by PMID after excluding the test papers. To replay the seven audited cases, run the second and third commands. The regression report distinguishes passage-level expectations from CRED's abstract-level labels and exits with a nonzero status for outstanding mismatches.

```powershell
.\venv\Scripts\python.exe -X utf8 evaluation/check_cred.py outputs/cred-source/data/val_data outputs/cred-eval/validation-replay --validation-against outputs/cred-source/data/test_data
.\venv\Scripts\python.exe -X utf8 evaluation/check_cred.py outputs/cred-source/data/test_data outputs/cred-eval/audit-replay --audit-from outputs/cred-eval/fresh_predictions.json
.\venv\Scripts\python.exe -X utf8 evaluation/check_quote_cases.py outputs/cred-eval/audit-replay/fresh_predictions.json
```
