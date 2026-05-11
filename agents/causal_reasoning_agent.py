# agents/causal_reasoning_agent.py
# S's work — Agent 3
# Loads the CRED fine-tuned BioBERT model and classifies
# each gene-disease sentence pair as causal or non-causal.

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from state import PipelineState
import os

# Path to S's fine-tuned model
MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'biobert_cred_finetuned')

# Load model once at startup
print("[Causal Reasoning Agent] Loading fine-tuned BioBERT model...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model     = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
model.eval()  # set to inference mode
print("[Causal Reasoning Agent] Model loaded.")


def predict_causal(sentence: str) -> dict:
    """
    Takes a sentence and returns causal label + confidence score.
    Label 1 = causal, Label 0 = non-causal.
    """
    inputs = tokenizer(
        sentence,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512
    )

    with torch.no_grad():
        outputs = model(**inputs)
        logits  = outputs.logits

    # Convert logits to probabilities
    probs      = torch.softmax(logits, dim=1).squeeze()
    label      = torch.argmax(probs).item()
    confidence = probs[label].item()

    return {
        "causal_label": "causal" if label == 1 else "non-causal",
        "confidence":   round(confidence, 4),
        "label_id":     label
    }


def causal_reasoning_agent(state: PipelineState) -> PipelineState:
    """
    LangGraph node function.
    Input:  state["normalized_entities"] — list of {gene, disease, sentence, paper_id}
    Output: state["causal_relations"]    — same list but with causal_label + confidence added
    """
    entities = state.get("normalized_entities", [])
    if not entities:
        print("[Causal Reasoning Agent] No entities to classify.")
        state["causal_relations"] = []
        return state

    # Deduplicate by sentence to avoid classifying same sentence multiple times
    seen_sentences  = set()
    unique_entities = []
    for e in entities:
        if e["sentence"] not in seen_sentences:
            seen_sentences.add(e["sentence"])
            unique_entities.append(e)

    # Limit to 50 pairs max for speed
    entities = unique_entities[:50]
    print(f"[Causal Reasoning Agent] Classifying {len(entities)} unique pairs (capped at 50)...")

    causal_relations = []
    causal_count     = 0

    for entity in entities:
        sentence = entity.get("sentence", "")
        if not sentence:
            continue

        result = predict_causal(sentence)

        # Merge prediction into entity dict
        relation = {
            **entity,
            "causal_label": result["causal_label"],
            "confidence":   result["confidence"],
            # These will be filled by analyst-critic agent
            "analyst_reasoning": "",
            "critic_feedback":   "",
            # These will be filled by validation agent
            "validated":         False,
            "disgenet_score":    0.0,
            "classification":    "",
            "contradictions":    [],
            "clinical_trials":   [],
            "drug_candidates":   [],
            "chain":             []
        }

        causal_relations.append(relation)

        if result["causal_label"] == "causal":
            causal_count += 1
            print(f"  CAUSAL ({result['confidence']:.2f}): {entity['gene']} → {entity['disease']}")

    print(f"[Causal Reasoning Agent] Found {causal_count} causal relations out of {len(causal_relations)}")
    state["causal_relations"] = causal_relations
    return state