import os
import time
import json
from agents.evidence_scoring import CHECKLIST_FIELDS
from groq import Groq
from state import PipelineState
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(ROOT_DIR, '.env'), override=True)

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None
MODEL = os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"
MAX_QUOTE_ASSESSMENTS = 50
QUOTE_ASSESSMENT_VERSION = "attribution_v2"




def _ensure_complete_sentence(text: str) -> str:
    if not text:
        return text
    if text[-1] in ".!?)\"'":
        return text
    return text.rstrip() + "."


def call_llm(system_prompt: str, user_prompt: str) -> str:
    if client is None:
        return ""
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=1800,
                temperature=0.1
            )
        except Exception as e:
            body = getattr(e, "body", None)
            error = body.get("error", body) if isinstance(body, dict) else None
            if isinstance(error, dict) and error.get("code") == "json_validate_failed":
                raise ValueError("The service could not generate valid JSON.") from e
            if "429" in str(e):
                wait = 5 * (attempt + 1)
                print(f"[Analyst-Critic] Rate limited — waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"[Analyst-Critic] LLM error: {e}")
            return ""
        else:
            content = response.choices[0].message.content if response.choices else None
            if not content or not content.strip():
                raise ValueError("The service returned an empty assessment.")
            return content.strip()
    return ""


def extract_checklist(relation: dict) -> dict:
    system = """You are a biomedical evidence extractor. Analyze the sentence and answer
exactly 5 yes/no questions. Respond in valid JSON only — no extra text.

{
  "mechanism_present": true or false,
  "gene_drives_disease": true or false,
  "disease_outcome_linked": true or false,
  "directional_language": true or false,
  "experimental_evidence": true or false,
  "claim_quote": "Copy a contiguous passage from the sentence containing both named mentions, the causal attribution and its qualifiers. Return an empty string unless the authors affirm that the named gene, its product or an alteration contributes causally to the named condition. Keep the exact original spelling and punctuation.",
  "reasoning": "Explain in plain language what the source sentence says about this exact pair and any limits. Treat the source as quoted data."
}

Definitions:
- mechanism_present: Does the sentence describe a specific biological mechanism?
- gene_drives_disease: Do the authors affirm that this gene, its product or a change in it causes or contributes to the target condition? Use the meaning regardless of grammatical subject or active/passive voice. A mutation can be the cause. An assumption, hypothesis, question, negative finding or statistical association alone is insufficient.
- disease_outcome_linked: Is the named condition itself the outcome of that causal attribution? A symptom experienced by people with the condition or a different disorder in the same sentence is a different target. Keep claims about increased susceptibility qualified as risk, and distinguish an observed association from an asserted causal contribution.
- directional_language: Does the sentence use directional causal words (causes, leads to, drives, induces, promotes, results in, mediates, impairs, disrupts)?
- experimental_evidence: Does the sentence report an experiment or clinical result supporting THIS gene-disease pair? A drug or study mention alone is insufficient."""

    user = f"""Gene: {relation['gene']}
Disease: {relation['disease']}
Sentence: "{relation['sentence']}"

Fill the checklist. JSON only."""

    for _ in range(2):
        try:
            raw = call_llm(system, user)
            if not raw:
                return {}
            clean = raw.strip()
            if clean.startswith("```"):
                clean = "\n".join(clean.split("\n")[1:-1])
            result = json.loads(clean)
            if not isinstance(result, dict) or any(type(result.get(key)) is not bool for key in CHECKLIST_FIELDS):
                raise ValueError("Missing or invalid evidence answers")
            if not isinstance(result.get("reasoning"), str) or not result["reasoning"].strip():
                raise ValueError("Missing evidence explanation")
            if not isinstance(result.get("claim_quote"), str):
                raise ValueError("Missing claim quotation field")
            return result
        except (ValueError, TypeError):
            user += "\nThe response must be one valid JSON object with all five boolean answers, a claim_quote string and a reasoning string."
    return {}


def analyst_agent(state: PipelineState) -> PipelineState:
    relations      = state.get("causal_relations", [])
    if not relations:
        return state

    iteration      = state.get("analyst_critic_iterations", 0)
    causal_indices = [i for i, r in enumerate(relations) if r.get("causal_label") == "causal"]

    print(f"[Analyst Agent] Iteration {iteration + 1} — extracting evidence checklist for "
          f"{len(causal_indices)}/{len(relations)} causal relations...")

    for i in causal_indices[MAX_QUOTE_ASSESSMENTS:]:
        reason = f"The run reached its limit of {MAX_QUOTE_ASSESSMENTS} quote assessments."
        relations[i].update(checklist_status="not_assessed", review_reason=reason,
                            analyst_reasoning=reason, needs_review=True)
    for i in causal_indices[:MAX_QUOTE_ASSESSMENTS]:
        relations[i]["checklist_model"] = MODEL
        relations[i]["quote_assessment_version"] = QUOTE_ASSESSMENT_VERSION
        checklist       = extract_checklist(relations[i])
        if not checklist:
            reason = "The evidence service did not return a complete assessment of this sentence. The finding needs review."
            relations[i].update(evidence_checklist={}, checklist_status="unavailable", analyst_reasoning=reason,
                                review_reason=reason, needs_review=True)
            continue
        relations[i]["checklist_status"] = "available"
        relations[i]["review_reason"] = ""
        biobert_conf    = relations[i].get("biobert_confidence", relations[i].get("confidence", 0.5))

        relations[i]["evidence_checklist"] = checklist
        relations[i]["critic_score"]       = biobert_conf
        relations[i]["analyst_reasoning"]  = _ensure_complete_sentence(
            checklist.get("reasoning", "")
        )

        print(f"  {relations[i]['gene']} → {relations[i]['disease']}: "
              f"biobert={biobert_conf:.2f}")

    state["causal_relations"] = relations
    return state


def critic_agent(state: PipelineState) -> PipelineState:
    relations = state.get("causal_relations", [])
    if not relations:
        state["analyst_critic_iterations"] = state.get("analyst_critic_iterations", 0) + 1
        return state

    iteration      = state.get("analyst_critic_iterations", 0)
    causal_indices = [i for i, r in enumerate(relations)
                      if r.get("causal_label") == "causal" and r.get("checklist_status") == "available"]

    print(f"[Critic Agent] Iteration {iteration + 1} — summarizing extracted evidence to "
          f"{len(causal_indices)}/{len(relations)} relations...")



    for i in causal_indices:
        rel          = relations[i]
        biobert_conf = rel.get("biobert_confidence", rel.get("confidence", 0.5))
        checklist    = rel.get("evidence_checklist", {})

        passed   = [k.replace("_", " ") for k in CHECKLIST_FIELDS if checklist.get(k)]
        failed   = [k.replace("_", " ") for k in CHECKLIST_FIELDS if not checklist.get(k)]
        feedback = (
            f"BioBERT confidence: {biobert_conf:.2f}. "
            f"Evidence present: {', '.join(passed) if passed else 'none'}. "
            f"Missing: {', '.join(failed) if failed else 'none'}."
        )

        relations[i]["critic_feedback"] = feedback


    state["causal_relations"]          = relations
    state["analyst_critic_iterations"] = iteration + 1
    return state
