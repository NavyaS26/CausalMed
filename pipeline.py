# pipeline.py
# N's work — Main LangGraph pipeline
# Wires all agents together into a single executable graph.
# This is the entry point for the entire system.

from langgraph.graph import StateGraph, END
from state import PipelineState

# Import all agents
from agents.ingestion_agent       import ingestion_agent
from agents.ner_agent             import ner_agent
from agents.chain_assembly_agent  import chain_assembly_agent

# These will be built by S, R, P
# Importing with fallback stubs so pipeline runs even if not built yet
try:
    from agents.normalization_agent   import normalization_agent
except ImportError:
    def normalization_agent(state):
        print("[Stub] Normalization agent not built yet")
        state["normalized_entities"] = state.get("entities", [])
        return state

try:
    from agents.causal_reasoning_agent import causal_reasoning_agent
except ImportError:
    def causal_reasoning_agent(state):
        print("[Stub] Causal reasoning agent not built yet")
        state["causal_relations"] = []
        return state

try:
    from agents.analyst_critic_agent  import analyst_agent, critic_agent
except ImportError:
    def analyst_agent(state):
        print("[Stub] Analyst agent not built yet")
        return state
    def critic_agent(state):
        print("[Stub] Critic agent not built yet")
        state["analyst_critic_iterations"] = state.get("analyst_critic_iterations", 0) + 1
        return state

try:
    from agents.validation_agent      import validation_agent
except ImportError:
    def validation_agent(state):
        print("[Stub] Validation agent not built yet")
        state["validated_relations"] = state.get("causal_relations", [])
        return state

try:
    from agents.contradiction_agent   import contradiction_agent
except ImportError:
    def contradiction_agent(state):
        print("[Stub] Contradiction agent not built yet")
        return state

try:
    from agents.output_agent          import output_agent
except ImportError:
    def output_agent(state):
        print("[Stub] Output agent not built yet")
        state["final_output"] = {"chains": state.get("chains", [])}
        return state


# ── Conditional edge: should analyst-critic loop continue? ──
def should_continue_loop(state: PipelineState) -> str:
    """
    Decides whether to keep looping between analyst and critic
    or move on to validation.
    Stops after max_iterations (default 3).
    """
    iterations = state.get("analyst_critic_iterations", 0)
    max_iter   = state.get("max_iterations", 3)

    if iterations >= max_iter:
        print(f"[Loop Control] Reached max iterations ({max_iter}), moving to validation")
        return "proceed_to_validation"
    else:
        print(f"[Loop Control] Iteration {iterations}/{max_iter}, continuing loop")
        return "continue_loop"


# ── Build the LangGraph ──
def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    # Add all agent nodes
    graph.add_node("ingestion",      ingestion_agent)
    graph.add_node("ner",            ner_agent)
    graph.add_node("normalization",  normalization_agent)
    graph.add_node("causal_reason",  causal_reasoning_agent)
    graph.add_node("analyst",        analyst_agent)
    graph.add_node("critic",         critic_agent)
    graph.add_node("validation",     validation_agent)
    graph.add_node("contradiction",  contradiction_agent)
    graph.add_node("chain_assembly", chain_assembly_agent)
    graph.add_node("output",         output_agent)

    # Define the flow
    graph.set_entry_point("ingestion")

    graph.add_edge("ingestion",     "ner")
    graph.add_edge("ner",           "normalization")
    graph.add_edge("normalization", "causal_reason")
    graph.add_edge("causal_reason", "analyst")
    graph.add_edge("analyst",       "critic")

    # Conditional loop between analyst and critic
    graph.add_conditional_edges(
        "critic",
        should_continue_loop,
        {
            "continue_loop":        "analyst",
            "proceed_to_validation": "validation"
        }
    )

    graph.add_edge("validation",     "contradiction")
    graph.add_edge("contradiction",  "chain_assembly")
    graph.add_edge("chain_assembly", "output")
    graph.add_edge("output",         END)

    return graph.compile()


# ── Run the pipeline ──
def run_pipeline(query: str) -> dict:
    """
    Entry point to run the full pipeline.
    Pass a gene-disease query string.
    Returns the final output dict.
    """
    pipeline = build_pipeline()

    initial_state: PipelineState = {
        "user_query":                 query,
        "papers":                     [],
        "entities":                   [],
        "normalized_entities":        [],
        "causal_relations":           [],
        "chains":                     [],
        "validated_relations":        [],
        "final_output":               {},
        "analyst_critic_iterations":  0,
        "max_iterations":             3,
    }

    print(f"\n{'='*50}")
    print(f"Running CausalMed pipeline for: {query}")
    print(f"{'='*50}\n")

    final_state = pipeline.invoke(initial_state)
    return final_state["final_output"]


# ── Quick test ──
if __name__ == "__main__":
    result = run_pipeline("TP53 lung cancer causal")
    print("\nFinal Output:")
    import json
    print(json.dumps(result, indent=2))