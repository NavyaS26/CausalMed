# agents/analyst_critic_agent.py
# S's work — Agents 5a and 5b
# Analyst proposes reasoning for each gene-disease relation.
# Critic challenges or confirms that reasoning.
# Loop runs 3 times max. Final label after loop goes to validation.
# Uses Groq API (Llama-3) for fast LLM inference.

import os
from groq import Groq
from state import PipelineState
from dotenv import load_dotenv
import time

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL  = "llama-3.1-8b-instant"


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call Groq Llama-3 and return response text."""
    for attempt in range(3):  # retry up to 3 times
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt}
                ],
                max_tokens=200,  # reduced from 300
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e):
                time.sleep(3)  # wait 3 seconds and retry
                continue
            print(f"[Analyst-Critic] LLM error: {e}")
            return ""
    return ""


def analyst_reasoning(relation: dict) -> str:
    """
    Analyst proposes reasoning for whether gene-disease relation is causal.
    Considers both causal and non-causal initial predictions.
    """
    system = """You are a biomedical expert analyzing gene-disease relationships.
Your job is to reason about whether a relationship between a gene and disease is CAUSAL or merely ASSOCIATIVE.
A causal relationship means the gene DIRECTLY causes, drives, or leads to the disease through a biological mechanism.
An associative relationship means they co-occur but causality is not established.
Be concise — 2-3 sentences maximum."""

    user = f"""Gene: {relation['gene']}
Disease: {relation['disease']}
Sentence from paper: "{relation['sentence']}"
Initial model prediction: {relation['causal_label']} (confidence: {relation['confidence']})

Provide your reasoning about whether this is truly a CAUSAL relationship."""

    return call_llm(system, user)


def critic_challenge(relation: dict, analyst_reasoning: str) -> dict:
    """
    Critic evaluates analyst reasoning and either confirms or overturns it.
    Returns updated label and feedback.
    """
    system = """You are a critical biomedical reviewer.
Your job is to evaluate whether the analyst's reasoning about a gene-disease causal relationship is sound.
You must respond in EXACTLY this format:
VERDICT: CAUSAL or NON-CAUSAL
FEEDBACK: Your one sentence feedback explaining your verdict."""

    user = f"""Gene: {relation['gene']}
Disease: {relation['disease']}
Sentence: "{relation['sentence']}"
Analyst reasoning: {analyst_reasoning}

Critically evaluate this reasoning. Is this relationship truly CAUSAL?
Remember: respond ONLY in the format:
VERDICT: CAUSAL or NON-CAUSAL
FEEDBACK: one sentence"""

    response = call_llm(system, user)

    # Parse verdict
    new_label = relation['causal_label']  # default keep original
    feedback  = response

    if "VERDICT:" in response:
        lines = response.split('\n')
        for line in lines:
            if line.startswith("VERDICT:"):
                verdict = line.replace("VERDICT:", "").strip().upper()
                if "NON-CAUSAL" in verdict:
                    new_label = "non-causal"
                elif "CAUSAL" in verdict:
                    new_label = "causal"
            if line.startswith("FEEDBACK:"):
                feedback = line.replace("FEEDBACK:", "").strip()

    return {
        "new_label": new_label,
        "feedback":  feedback
    }


def analyst_agent(state: PipelineState) -> PipelineState:
    """
    LangGraph node function — Analyst.
    Generates reasoning for every relation.
    """
    relations = state.get("causal_relations", [])
    if not relations:
        return state

    iteration = state.get("analyst_critic_iterations", 0)
    print(f"[Analyst Agent] Iteration {iteration + 1} — reasoning on {len(relations)} relations...")

    for i, rel in enumerate(relations):
        reasoning = analyst_reasoning(rel)
        relations[i]["analyst_reasoning"] = reasoning

    state["causal_relations"] = relations
    return state


def critic_agent(state: PipelineState) -> PipelineState:
    """
    LangGraph node function — Critic.
    Challenges analyst reasoning and updates labels.
    """
    relations = state.get("causal_relations", [])
    if not relations:
        state["analyst_critic_iterations"] = state.get("analyst_critic_iterations", 0) + 1
        return state

    iteration = state.get("analyst_critic_iterations", 0)
    print(f"[Critic Agent] Iteration {iteration + 1} — challenging {len(relations)} relations...")

    flipped = 0
    for i, rel in enumerate(relations):
        reasoning = rel.get("analyst_reasoning", "")
        if not reasoning:
            continue

        result    = critic_challenge(rel, reasoning)
        new_label = result["new_label"]

        # Track if label was flipped
        if new_label != rel["causal_label"]:
            flipped += 1
            print(f"  FLIPPED: {rel['gene']} → {rel['disease']} "
                  f"({rel['causal_label']} → {new_label})")

        relations[i]["causal_label"]     = new_label
        relations[i]["critic_feedback"]  = result["feedback"]

    print(f"[Critic Agent] {flipped} labels flipped this iteration")
    state["causal_relations"]           = relations
    state["analyst_critic_iterations"]  = iteration + 1
    return state