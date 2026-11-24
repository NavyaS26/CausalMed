"""Screen each gene–disease pair in its original sentence context."""
import os
import re

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from state import PipelineState

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
    Classify one marked input or abstain if it exceeds the checkpoint's context.
    Label 1 = causal, Label 0 = non-causal.
    """
    inputs = tokenizer(
        sentence,
        return_tensors="pt",
        truncation=False,
    )
    if inputs["input_ids"].shape[1] > model.config.max_position_embeddings:
        return {"causal_label": "unresolved", "confidence": None,
                "review_reason": "The passage exceeds the classifier's input length."}

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


def mark_pair(sentence: str, gene: str, disease: str, disease_spans=None) -> str | None:
    """Mask the two target mentions using CRED's input format, preserving other entities."""
    if not gene or not disease or "@GeneSrc$" in sentence or "@DiseaseTgt$" in sentence:
        return None
    gene_spans = [m.span() for m in re.finditer(r"(?<!\w)" + re.escape(gene) + r"(?!\w)", sentence)]
    if disease_spans is None:
        disease_spans = [m.span() for m in re.finditer(
            r"(?<!\w)" + re.escape(disease) + r"(?!\w)", sentence, re.I)]
    if not gene_spans or not disease_spans:
        return None
    if any(not (0 <= start < end <= len(sentence)) or sentence[start:end].casefold() != disease.casefold()
           for start, end in disease_spans):
        return None
    spans = sorted([(s, e, "@GeneSrc$") for s, e in gene_spans] +
                   [(s, e, "@DiseaseTgt$") for s, e in disease_spans])
    parts = []
    previous = 0
    for start, end, marker in spans:
        if start < previous:
            return None
        parts.extend((sentence[previous:start], marker))
        previous = end
    return "".join(parts) + sentence[previous:]


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

    seen_pairs = set()
    predictions = {}
    causal_relations = []
    for entity in entities:
        sentence = entity.get("sentence", "")
        if not sentence:
            continue

        pair_key = (entity.get("paper_id"), sentence, entity["gene"], entity["disease"])
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        marked = mark_pair(sentence, entity["gene"], entity["disease"], entity.get("disease_spans"))
        if marked is None:
            result = {"causal_label": "unresolved", "confidence": None,
                      "review_reason": "The two target mentions could not be located separately in the passage."}
        else:
            if marked not in predictions:
                predictions[marked] = predict_causal(marked)
            result = predictions[marked]
        relation = {
            **entity,
            "causal_label": result["causal_label"],
            "confidence": result["confidence"],
            "needs_review": result["causal_label"] == "unresolved",
            "review_reason": result.get("review_reason", ""),
            "biobert_label": result["causal_label"] if result["confidence"] is not None else None,
            "biobert_confidence": result["confidence"],
            # These will be filled by analyst-critic agent
            "analyst_reasoning": "",
            "critic_feedback":   "",
            # These will be filled by validation agent
            "validated":         False,
            "clinvar_score":     0.0,
            "classification":    "",
            "contradictions":    [],
            "clinical_trials":   [],
            "drug_candidates":   [],
            "chain":             []
        }

        causal_relations.append(relation)

    causal_count = sum(rel["causal_label"] == "causal" for rel in causal_relations)
    print(f"[Causal Reasoning Agent] Found {causal_count} causal relations out of {len(causal_relations)}")
    state["causal_relations"] = causal_relations
    return state
