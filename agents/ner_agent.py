# agents/ner_agent.py
# N's work — Agent 2
# Uses spaCy BC5CDR biomedical NER model for disease recognition.
# Uses NCBI official human gene database for gene recognition.
# All 20,000+ human gene symbols loaded from NCBI at startup.
# Completely local after first download — no API dependency.

import spacy
import re
import os
import gzip
import requests
from state import PipelineState

# ── Load BC5CDR biomedical NER model ──────────────────────────
print("[NER Agent] Loading BC5CDR biomedical NER model...")
nlp = spacy.load("en_ner_bc5cdr_md")
print("[NER Agent] Model loaded.")

# ── Load Human Gene Database from NCBI ───────────────────────

GENE_CACHE_PATH = os.path.join(os.path.dirname(__file__), '..', 'human_genes.txt')
NCBI_GENE_URL   = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz"


def load_human_genes() -> set:
    """
    Load all official human gene symbols from NCBI.
    Downloads once and caches locally in human_genes.txt.
    Returns a set of ~20,000 official gene symbols.
    """
    cache = os.path.abspath(GENE_CACHE_PATH)

    # Use cached version if exists
    if os.path.exists(cache):
        print("[NER Agent] Loading gene database from cache...")
        with open(cache, 'r') as f:
            genes = set(line.strip() for line in f if line.strip())
        print(f"[NER Agent] Loaded {len(genes)} human gene symbols.")
        return genes

    # Download from NCBI
    print("[NER Agent] Downloading human gene database from NCBI (one-time ~10MB)...")
    try:
        response = requests.get(NCBI_GENE_URL, stream=True, timeout=60)
        response.raise_for_status()

        gene_symbols = set()

        with gzip.open(response.raw, 'rt', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#'):
                    continue
                parts = line.strip().split('\t')
                if len(parts) < 3:
                    continue

                # Column 2 = official gene symbol
                # Column 4 = synonyms (pipe separated)
                symbol   = parts[2].strip()
                synonyms = parts[4].strip().split('|') if parts[4] != '-' else []

                if symbol and symbol != '-':
                    gene_symbols.add(symbol)

                # Also add synonyms for better coverage
                for syn in synonyms:
                    syn = syn.strip()
                    if syn and syn != '-' and len(syn) <= 15:
                        gene_symbols.add(syn)

        # Save to cache
        with open(cache, 'w') as f:
            for g in sorted(gene_symbols):
                f.write(g + '\n')

        print(f"[NER Agent] Downloaded and cached {len(gene_symbols)} gene symbols.")
        return gene_symbols

    except Exception as e:
        print(f"[NER Agent] Failed to download gene database: {e}")
        print("[NER Agent] Falling back to minimal known genes list...")
        return {
            "TP53", "BRCA1", "BRCA2", "EGFR", "KRAS", "HER2", "ERBB2",
            "MYC", "PIK3CA", "PTEN", "APC", "RB1", "VHL", "MLH1", "MSH2",
            "CDKN2A", "CDK4", "MDM2", "BCL2", "VEGF", "ALK", "RET", "MET",
            "BRAF", "NRAS", "HRAS", "NF1", "ATM", "CHEK2", "PALB2", "JAK2",
            "ABL1", "STAT3", "NOTCH1", "AKT1", "MTOR", "FGFR1", "FGFR2",
            "IDH1", "IDH2", "KIT", "PDGFRA", "FLT3", "NPM1", "DNMT3A"
        }


# Load gene database at startup
HUMAN_GENES = load_human_genes()

# Terms that look like genes but are not
NOT_GENES = {
    "SCLC", "NSCLC", "LCNEC", "LUAD", "LUSC", "ILD", "CNA", "TMB",
    "NGS", "IHC", "PCR", "WES", "FDA", "WHO", "DNA", "RNA", "MSI",
    "PFS", "OS", "HR", "CI", "OR", "WBC", "RBC", "CT", "MRI", "PET",
    "FISH", "GWAS", "SNP", "CNV", "LOH", "EMT", "ECM", "CAR", "CAM",
    "TSG", "TS", "MG", "PD", "OS", "HR"
}

# Bad disease name patterns
BAD_DISEASE_PATTERNS = [
    "funding", "ngs-detected", "mutations were", "index", "concordance",
    "national cancer", "ki-67", "immunostaining", "staining", "sequencing",
    "detection", "analysis", "patients", "treatment", "therapy",
    "expression", "antibody", "assay", "method", "p53 mutations"
]


def extract_genes(text: str) -> list:
    """
    Extract gene symbols from text using the full NCBI human gene database.
    Only returns symbols that are official human genes.
    """
    genes = []
    # Tokenize text into uppercase words
    words = re.findall(r'\b([A-Z][A-Z0-9\-]{1,14})\b', text)

    for word in words:
        if word in NOT_GENES:
            continue
        if len(word) < 3:  # skip 1-2 character matches
            continue
        if word in HUMAN_GENES:
            genes.append(word)

    return list(set(genes))


def split_sentences(text: str) -> list:
    """Split text into individual sentences."""
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def extract_pairs_from_abstract(abstract: str, pmid: str) -> list:
    pairs     = []
    sentences = split_sentences(abstract)

    for sentence in sentences:
        doc      = nlp(sentence)
        diseases = [ent.text.strip() for ent in doc.ents if ent.label_ == "DISEASE"]
        genes    = extract_genes(sentence)

        if genes and diseases:
            for gene in genes:
                for disease in diseases:
                    disease_lower = disease.lower()

                    # Skip bad disease extractions
                    if any(bad in disease_lower for bad in BAD_DISEASE_PATTERNS):
                        continue

                    # Skip if disease is too long
                    if len(disease.split()) > 5:
                        continue

                    # Skip if disease is actually a gene
                    if disease.upper() in HUMAN_GENES:
                        continue

                    if len(gene) >= 2 and len(disease) >= 3:
                        pairs.append({
                            "gene":     gene,
                            "disease":  disease,
                            "sentence": sentence.strip(),
                            "paper_id": pmid
                        })

    return pairs


def ner_agent(state: PipelineState) -> PipelineState:
    """
    LangGraph node function.
    Input:  state["papers"]   — list of {pmid, title, abstract}
    Output: state["entities"] — list of {gene, disease, sentence, paper_id}
    """
    papers = state.get("papers", [])

    if not papers:
        print("[NER Agent] No papers to process.")
        state["entities"] = []
        return state

    print(f"[NER Agent] Extracting entities from {len(papers)} papers...")

    all_entities = []

    for paper in papers:
        pmid     = paper.get("pmid", "")
        abstract = paper.get("abstract", "")
        if not abstract:
            continue

        pairs = extract_pairs_from_abstract(abstract, pmid)
        all_entities.extend(pairs)

        if pairs:
            print(f"  PMID {pmid}: {len(pairs)} gene-disease pairs")

    # Deduplicate
    seen    = set()
    deduped = []
    for e in all_entities:
        key = f"{e['gene']}_{e['disease']}_{e['sentence'][:50]}"
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    print(f"[NER Agent] Total: {len(deduped)} unique gene-disease pairs")
    state["entities"] = deduped
    return state