import xml.etree.ElementTree as ET
import spacy
import re
import os
import gzip
import requests
from agents.mesh_descriptors import descriptor_index
from state import PipelineState

print("[NER Agent] Loading BC5CDR biomedical NER model...")
nlp = spacy.load("en_ner_bc5cdr_md")
print("[NER Agent] Model loaded.")

GENE_CACHE_PATH = os.path.join(os.path.dirname(__file__), '..', 'human_genes.txt')
NCBI_GENE_URL   = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz"



def load_human_genes() -> set:
    cache = os.path.abspath(GENE_CACHE_PATH)
    if os.path.exists(cache):
        print("[NER Agent] Loading gene database from cache...")
        with open(cache, 'r') as f:
            genes = set(line.strip() for line in f if line.strip())
        print(f"[NER Agent] Loaded {len(genes)} human gene symbols.")
        return genes
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
                symbol   = parts[2].strip()
                synonyms = parts[4].strip().split('|') if parts[4] != '-' else []
                if symbol and symbol != '-':
                    gene_symbols.add(symbol)
                for syn in synonyms:
                    syn = syn.strip()
                    if syn and syn != '-' and len(syn) <= 15:
                        gene_symbols.add(syn)
        with open(cache, 'w') as f:
            for g in sorted(gene_symbols):
                f.write(g + '\n')
        print(f"[NER Agent] Downloaded and cached {len(gene_symbols)} gene symbols.")
        return gene_symbols
    except Exception as e:
        print(f"[NER Agent] Failed to download gene database: {e}")
        return {
            "TP53", "BRCA1", "BRCA2", "EGFR", "KRAS", "HER2", "ERBB2",
            "MYC", "PIK3CA", "PTEN", "APC", "RB1", "VHL", "MLH1", "MSH2",
            "CDKN2A", "CDK4", "MDM2", "BCL2", "VEGF", "ALK", "RET", "MET",
            "BRAF", "NRAS", "HRAS", "NF1", "ATM", "CHEK2", "PALB2", "JAK2",
            "ABL1", "STAT3", "NOTCH1", "AKT1", "MTOR", "FGFR1", "FGFR2",
            "IDH1", "IDH2", "KIT", "PDGFRA", "FLT3", "NPM1", "DNMT3A",
            "XPO1", "TRIB3", "PARP1", "PARP2", "EXO1", "MRE11", "EZH2", "AURKA"
        }


HUMAN_GENES = load_human_genes()

NOT_GENES = {
    "SCLC", "NSCLC", "LCNEC", "LUAD", "LUSC", "ILD", "CNA", "TMB",
    "NGS", "IHC", "PCR", "WES", "FDA", "WHO", "DNA", "RNA", "MSI",
    "PFS", "OS", "HR", "CI", "OR", "WBC", "RBC", "CT", "MRI", "PET",
    "FISH", "GWAS", "SNP", "CNV", "LOH", "EMT", "ECM", "CAR", "CAM",
    "TSG", "TS", "MG", "PD", "TNF", "ACE", "GFR", "HRR", "ORR"
}

BAD_DISEASE_PATTERNS = [
    "funding", "ngs-detected", "mutations were", "index", "concordance",
    "national cancer", "ki-67", "immunostaining", "staining", "sequencing",
    "detection", "analysis", "patients", "treatment", "therapy",
    "expression", "antibody", "assay", "method", "p53 mutations"
]

GENERIC_DISEASES = {
    "cancer", "cancers", "tumor", "tumors", "neoplasm", "neoplasms",
    "malignancy", "malignancies", "disease", "disorder", "carcinoma",
    "solid tumor", "solid tumors"
}

CELL_LINE_PATTERN = re.compile(r'^[A-Z]{1,5}[0-9]{1,4}[A-Z]?$')


def is_disease_tree(tree_numbers: list) -> bool:
    """
    FIX: Extract tree code from full URL if necessary before checking.
    'http://id.nlm.nih.gov/mesh/C15.604...' → 'C15.604...' → starts with C
    """
    for tn in tree_numbers:
        code = str(tn).split("/")[-1].strip()
        if code.startswith("C"):
            return True
    return False


def classify_disease(disease: str, mesh_cache: dict) -> dict:
    """
    Classify disease into: clinical_disease, generic_disease,
    research_concept, or invalid_entity.
    Original disease text is NEVER replaced with mesh_label.
    """
    disease_lower = disease.lower().strip()
    mesh_info     = mesh_cache.get(disease_lower.casefold()) or {
        "exists": False, "mesh_id": "", "mesh_label": "", "tree_numbers": []
    }

    # Step 1: Generic disease check first
    if disease_lower in GENERIC_DISEASES:
        return {
            "disease_category": "generic_disease",
            "mesh_id":          mesh_info.get("mesh_id", ""),
            "mesh_label":       mesh_info.get("mesh_label", disease),
            "disease_source":   "mesh" if mesh_info.get("exists") else "heuristic"
        }

    # Step 2: Clinical disease — MeSH hit under C tree
    if mesh_info.get("exists") and is_disease_tree(mesh_info.get("tree_numbers", [])):
        return {
            "disease_category": "clinical_disease",
            "mesh_id":          mesh_info.get("mesh_id", ""),
            "mesh_label":       mesh_info.get("mesh_label", disease),
            "disease_source":   "mesh"
        }

    # Step 3: Cell line detection
    disease_upper = disease.upper().replace("-", "").replace(" ", "")
    if CELL_LINE_PATTERN.match(disease_upper) and disease_upper not in HUMAN_GENES:
        return {
            "disease_category": "invalid_entity",
            "mesh_id":          "",
            "mesh_label":       disease,
            "disease_source":   "invalid"
        }

    # A recognized mention may lack a unique descriptor match.
    return {
        "disease_category": "research_concept" if mesh_info["exists"] else "unmapped_disease",
        "mesh_id":          mesh_info.get("mesh_id", ""),
        "mesh_label":       mesh_info.get("mesh_label") or disease,
        "disease_source":   "mesh" if mesh_info["exists"] else "unmapped"
    }


def extract_genes(text: str) -> list:
    genes = []
    words = re.findall(r'\b([A-Z](?:[A-Z0-9]|-(?=[A-Z0-9])){1,14})\b', text)
    for word in words:
        if word in NOT_GENES:
            continue
        if len(word) < 3:
            continue
        if CELL_LINE_PATTERN.match(word) and word not in HUMAN_GENES:
            continue
        if word in HUMAN_GENES:
            genes.append(word)
    return list(dict.fromkeys(genes))


def split_sentences(text: str) -> list:
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def ner_agent(state: PipelineState) -> PipelineState:
    papers = state.get("papers", [])
    if not papers:
        print("[NER Agent] No papers to process.")
        state["entities"] = []
        return state

    print(f"[NER Agent] Extracting entities from {len(papers)} papers...")

    # ── Step 1: Extract all raw pairs ────────────────────────
    raw_pairs = []
    for paper in papers:
        pmid     = paper.get("pmid", "")
        abstract = paper.get("abstract", "")
        if not abstract:
            continue
        sentences = split_sentences(abstract)
        for sentence in sentences:
            doc      = nlp(sentence)
            diseases = {}
            for ent in doc.ents:
                if ent.label_ == "DISEASE" and ent.text.strip():
                    mention = ent.text.strip()
                    start = ent.start_char + len(ent.text) - len(ent.text.lstrip())
                    diseases.setdefault(mention, []).append((start, start + len(mention)))
            genes    = extract_genes(sentence)
            if not genes or not diseases:
                continue
            for gene in genes:
                for disease in diseases:
                    disease_lower = disease.lower()
                    if any(bad in disease_lower for bad in BAD_DISEASE_PATTERNS):
                        continue
                    if len(disease.split()) > 8:
                        continue
                    if disease.upper() in HUMAN_GENES:
                        continue
                    if len(gene) >= 2 and len(disease) >= 3:
                        raw_pairs.append({
                            "gene":     gene,
                            "disease":  disease,  # original text always preserved
                            "disease_spans": diseases[disease],
                            "sentence": sentence.strip(),
                            "paper_id": pmid
                        })

    # ── Step 2: Batch MeSH lookup for all unique diseases ────
    mesh_cache = {}
    if raw_pairs:
        try:
            mesh_cache = descriptor_index()
        except (OSError, EOFError, ValueError, ET.ParseError) as error:
            print(f"[NER Agent] MeSH descriptors unavailable: {error}")

    # ── Step 3: Classify and filter ──────────────────────────
    all_entities  = []
    invalid_count = 0

    for pair in raw_pairs:
        classification = classify_disease(pair["disease"], mesh_cache)

        if classification["disease_category"] == "invalid_entity":
            invalid_count += 1
            print(f"  [NER] Discarded: {pair['gene']} → {pair['disease']} "
                  f"(cell line detected)")
            continue

        all_entities.append({
            **pair,
            "disease_category": classification["disease_category"],
            "mesh_id":          classification["mesh_id"],
            "mesh_label":       classification["mesh_label"],
            "disease_source":   classification["disease_source"],
        })

    print(f"[NER Agent] Discarded {invalid_count} invalid entities")

    # Keep a separate evidence record for each paper and sentence.
    seen    = set()
    deduped = []
    for e in all_entities:
        key = (e["paper_id"], e["sentence"], e["gene"], e["disease"].casefold())
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    pmid_counts = {}
    for e in deduped:
        pmid_counts[e["paper_id"]] = pmid_counts.get(e["paper_id"], 0) + 1
    for pmid, count in sorted(pmid_counts.items()):
        print(f"  PMID {pmid}: {count} gene-disease pairs")

    print(f"[NER Agent] Total: {len(deduped)} unique gene-disease pairs")
    print(f"  Categories: "
          f"clinical={sum(1 for e in deduped if e['disease_category']=='clinical_disease')} "
          f"generic={sum(1 for e in deduped if e['disease_category']=='generic_disease')} "
          f"research={sum(1 for e in deduped if e['disease_category']=='research_concept')}")

    state["entities"] = deduped
    return state
