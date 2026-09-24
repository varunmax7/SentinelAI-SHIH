"""Graph assembly for the forecast agent.

    sample ─(windfield?)─▶ advect ─▶ detect ─▶ threshold
        │                                          │
        └──────────▶ END                ┌──(anything cleared severity+confidence?)──┐
                                         ▼                                           ▼
                                  draft_brief(LLM)                                  END
                                         │
                                   persist_flags   <- same human gate as triage, same table
                                         │
                                        END

Two conditional edges, same reasoning as `graph.py`'s triage DAG: a windless
or hazard-free forecast pass is the normal case and must cost zero tokens,
not one cheap call.
"""

from langgraph.graph import END, StateGraph

from . import forecast_nodes as nodes
from .forecast_state import ForecastState


def build_forecast_graph(ctx, checkpointer=None):
    graph = StateGraph(ForecastState)

    graph.add_node('sample', nodes.make_sample(ctx))
    graph.add_node('advect', nodes.make_advect(ctx))
    graph.add_node('detect', nodes.detect)
    graph.add_node('threshold', nodes.threshold)
    graph.add_node('draft_brief', nodes.make_draft_brief(ctx))
    graph.add_node('persist_flags', nodes.make_persist_flags(ctx))

    graph.set_entry_point('sample')
    graph.add_conditional_edges('sample', nodes.has_windfield,
                                {'advect': 'advect', '__end__': END})
    graph.add_edge('advect', 'detect')
    graph.add_edge('detect', 'threshold')
    graph.add_conditional_edges('threshold', nodes.has_events,
                                {'draft_brief': 'draft_brief', '__end__': END})
    graph.add_edge('draft_brief', 'persist_flags')
    graph.add_edge('persist_flags', END)

    return graph.compile(checkpointer=checkpointer)
