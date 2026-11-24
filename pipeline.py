from langgraph.graph import StateGraph, END
from state import PipelineState

from agents.analyst_critic_agent import analyst_agent, critic_agent
from agents.causal_reasoning_agent import causal_reasoning_agent
from agents.chain_assembly_agent import chain_assembly_agent
from agents.contradiction_agent import contradiction_agent
from agents.ingestion_agent import ingestion_agent
from agents.ner_agent import ner_agent
from agents.normalization_agent import normalization_agent
from agents.output_agent import output_agent
from agents.validation_agent import validation_agent


def should_continue_loop(state: PipelineState) -> str:
    iterations = state.get("analyst_critic_iterations", 0)
    max_iter   = state.get("max_iterations", 1)
    if iterations >= max_iter:
        print(f"[Loop Control] Reached max iterations ({max_iter}), checking contradictions")
        return "check_contradictions"
    print(f"[Loop Control] Iteration {iterations}/{max_iter}, continuing loop")
    return "continue_loop"


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

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

    graph.set_entry_point("ingestion")

    graph.add_edge("ingestion",     "ner")
    graph.add_edge("ner",           "normalization")
    graph.add_edge("normalization", "causal_reason")
    graph.add_edge("causal_reason", "analyst")
    graph.add_edge("analyst",       "critic")

    graph.add_conditional_edges(
        "critic",
        should_continue_loop,
        {
            "continue_loop":         "analyst",
            "check_contradictions": "contradiction"
        }
    )

    graph.add_edge("contradiction",  "validation")
    graph.add_edge("validation",     "chain_assembly")
    graph.add_edge("chain_assembly", "output")
    graph.add_edge("output",         END)

    return graph.compile()


def run_pipeline(query: str) -> dict:
    pipeline = build_pipeline()

    initial_state: PipelineState = {
        "user_query":                query,
        "papers":                    [],
        "entities":                  [],
        "normalized_entities":       [],
        "causal_relations":          [],
        "chains":                    [],
        "validated_relations":       [],
        "final_output":              {},
        "analyst_critic_iterations": 0,
        "max_iterations":            1,
    }

    print(f"\n{'='*50}")
    print(f"Running CausalMed pipeline for: {query}")
    print(f"{'='*50}\n")

    final_state = pipeline.invoke(initial_state)
    return final_state["final_output"]


if __name__ == "__main__":
    import json
    result = run_pipeline("TP53 lung cancer causal")
    print("\nFinal Output:")
    print(json.dumps(result, indent=2))
