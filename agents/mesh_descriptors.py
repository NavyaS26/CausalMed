"""Resolve exact preferred names and entry terms against NLM descriptor records."""
import gzip
import os
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
import xml.etree.ElementTree as ET

import requests


ARCHIVE = Path(__file__).resolve().parents[1] / "mesh_data" / "desc2026.gz"
URL = "https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.gz"


def read_index(path):
    index = {}
    with gzip.open(path, "rb") as stream:
        for _, record in ET.iterparse(stream):
            if record.tag != "DescriptorRecord":
                continue
            identifier = record.findtext("DescriptorUI")
            label = record.findtext("DescriptorName/String")
            if not identifier or not label:
                raise ValueError("Incomplete MeSH descriptor")
            entry = {
                "exists": True, "mesh_id": identifier, "mesh_label": label,
                "tree_numbers": [node.text for node in record.findall("TreeNumberList/TreeNumber")],
            }
            names = {label, *(node.text for node in record.findall("ConceptList/Concept/TermList/Term/String"))}
            for name in names:
                key = name.strip().casefold()
                # Ambiguous synonyms stay unresolved.
                if key in index and index[key] != entry:
                    index[key] = None
                else:
                    index[key] = entry
            record.clear()
    if not index:
        raise ValueError("Empty MeSH descriptor release")
    return index


@lru_cache(maxsize=1)
def descriptor_index():
    if ARCHIVE.exists():
        return read_index(ARCHIVE)
    ARCHIVE.parent.mkdir(exist_ok=True)
    with NamedTemporaryFile(dir=ARCHIVE.parent, delete=False) as download:
        temp_path = Path(download.name)
    try:
        with requests.get(URL, stream=True, timeout=(10, 60)) as response:
            response.raise_for_status()
            chunks = response.iter_content(1024 * 1024)
            first = next(chunks, b"")
            # Some mirrors serve the archive with HTTP Content-Encoding: gzip.
            writer = open if first.startswith(b"\x1f\x8b") else gzip.open
            with writer(temp_path, "wb") as stream:
                stream.write(first)
                for chunk in chunks:
                    stream.write(chunk)
        index = read_index(temp_path)
        os.replace(temp_path, ARCHIVE)
        return index
    finally:
        temp_path.unlink(missing_ok=True)
