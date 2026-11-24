import xml.etree.ElementTree as ET
from agents.ncbi_client import fetch_eutils
from state import PipelineState
from dotenv import load_dotenv

load_dotenv(override=True)


def fetch_pubmed_ids(query: str, max_results: int = 20) -> list:
    params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"}
    response = fetch_eutils("esearch.fcgi", params)
    return response.json()["esearchresult"]["idlist"]


def fetch_paper_details(pmid: str) -> dict:
    params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
    response = fetch_eutils("efetch.fcgi", params)

    root    = ET.fromstring(response.content)
    article = root.find(".//PubmedArticle")

    # FIX: guard against None article
    if article is None:
        return {"pmid": pmid, "title": "", "abstract": ""}

    title = ""

    title_el = article.find(".//ArticleTitle")
    if title_el is not None:
        title = "".join(title_el.itertext()).strip()

    abstract_el = article.find("./MedlineCitation/Article/Abstract")
    if abstract_el is None:
        abstract_el = article.find("./MedlineCitation/OtherAbstract")

    abstract_sections = []
    if abstract_el is not None:
        for section_el in abstract_el.findall("AbstractText"):
            section = "".join(section_el.itertext()).strip()
            if section:
                abstract_sections.append(section)
    abstract = " ".join(abstract_sections)

    return {"pmid": pmid, "title": title, "abstract": abstract}


def clean_text(text: str) -> str:
    return " ".join(text.split())


def ingestion_agent(state: PipelineState) -> PipelineState:
    print(f"[Ingestion Agent] Fetching papers for: {state['user_query']}")

    try:
        pmids = fetch_pubmed_ids(state["user_query"], max_results=20)
    except Exception as e:
        print(f"[Ingestion Agent] PubMed search failed: {e}")
        state["papers"] = []
        return state

    print(f"[Ingestion Agent] Found {len(pmids)} papers")

    papers = []
    for pmid in pmids:
        try:
            paper             = fetch_paper_details(pmid)
            paper["abstract"] = clean_text(paper["abstract"])
            paper["title"]    = clean_text(paper["title"])
            if paper["abstract"]:
                papers.append(paper)
        except Exception as e:
            print(f"[Ingestion Agent] Skipping PMID {pmid}: {e}")

    print(f"[Ingestion Agent] Cleaned {len(papers)} papers with abstracts")
    state["papers"] = papers
    return state
