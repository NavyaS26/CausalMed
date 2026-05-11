# agents/ingestion_agent.py
# N's work — Agent 1
# Fetches papers from PubMed based on user query.
# Cleans and returns abstract text + metadata.

import requests
import xml.etree.ElementTree as ET
from state import PipelineState
from dotenv import load_dotenv
import os

load_dotenv(override=True)
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"



def fetch_pubmed_ids(query: str, max_results: int = 20) -> list:
    """Search PubMed and return a list of PMIDs for the query."""
    url = f"{PUBMED_BASE}/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    return data["esearchresult"]["idlist"]


def fetch_paper_details(pmid: str) -> dict:
    """Fetch title and abstract for a single PMID."""
    url = f"{PUBMED_BASE}/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "xml"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    article = root.find(".//PubmedArticle")

    title = ""
    abstract = ""

    title_el = article.find(".//ArticleTitle")
    if title_el is not None:
        title = "".join(title_el.itertext()).strip()

    abstract_el = article.find(".//AbstractText")
    if abstract_el is not None:
        abstract = "".join(abstract_el.itertext()).strip()

    return {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
    }


def clean_text(text: str) -> str:
    """Basic text cleaning — remove extra whitespace and non-ASCII."""
    text = " ".join(text.split())
    text = text.encode("ascii", errors="ignore").decode()
    return text.strip()


def ingestion_agent(state: PipelineState) -> PipelineState:
    """
    LangGraph node function.
    Input:  state["user_query"]
    Output: state["papers"] — list of cleaned paper dicts
    """
    print(f"[Ingestion Agent] Fetching papers for: {state['user_query']}")

    pmids = fetch_pubmed_ids(state["user_query"], max_results=20)
    print(f"[Ingestion Agent] Found {len(pmids)} papers")

    papers = []
    for pmid in pmids:
        try:
            paper = fetch_paper_details(pmid)
            paper["abstract"] = clean_text(paper["abstract"])
            paper["title"] = clean_text(paper["title"])
            if paper["abstract"]:  # skip papers with no abstract
                papers.append(paper)
        except Exception as e:
            print(f"[Ingestion Agent] Skipping PMID {pmid}: {e}")

    print(f"[Ingestion Agent] Cleaned {len(papers)} papers with abstracts")
    state["papers"] = papers
    return state