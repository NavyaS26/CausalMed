# debug_pubtator.py
# Run this to see exactly what PubTator returns
# so we can fix the parsing in ner_agent.py

import requests
import json

# Test with a known TP53 paper
TEST_PMID = "25569183"

url = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson"

response = requests.get(
    url,
    params={"pmids": TEST_PMID, "concepts": "gene,disease"},
    timeout=30
)

print(f"Status code: {response.status_code}")
print(f"\nRaw response (first 3000 chars):")
print(response.text[:3000])

print("\n\nParsed structure:")
data = response.json()
print(f"Type: {type(data)}")

if isinstance(data, list):
    print(f"List length: {len(data)}")
    if data:
        first = data[0]
        print(f"\nFirst item keys: {list(first.keys())}")
        passages = first.get("passages", [])
        print(f"Number of passages: {len(passages)}")
        if passages:
            print(f"\nFirst passage keys: {list(passages[0].keys())}")
            print(f"First passage text: {passages[0].get('text', '')[:200]}")
            annotations = passages[0].get("annotations", [])
            print(f"\nAnnotations in first passage: {len(annotations)}")
            if annotations:
                print(f"First annotation: {json.dumps(annotations[0], indent=2)}")
elif isinstance(data, dict):
    print(f"Dict keys: {list(data.keys())}")
    passages = data.get("passages", [])
    print(f"Number of passages: {len(passages)}")
    if passages:
        annotations = passages[0].get("annotations", [])
        print(f"Annotations in first passage: {len(annotations)}")
        if annotations:
            print(f"First annotation: {json.dumps(annotations[0], indent=2)}")