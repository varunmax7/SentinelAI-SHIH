"""Graph assembly.

    fetch ─(any items?)─▶ normalize ─▶ extract(LLM) ─▶ geo_resolve
                │                                          │
                └────────────▶ END                    correlate(LLM)
                                                           │
                                              score (DETERMINISTIC)
                                                           │
                                                      threshold
                                                           │
                                        ┌──(anything over the cutoff?)──┐
                                        ▼                               ▼
                                 draft_brief(LLM)                      END
                                        │
                                  persist_flags
                                        │
                                  human_gate  ⏸ interrupt()
                                        │
                                    publish

Two conditional edges short-circuit to END *before* any LLM node. A quiet feed
is the normal case - most polls have nothing new - and it must cost zero
tokens, not one cheap call.
"""

import os

from langgraph.graph import END, StateGraph

from . import nodes
from .state import TriageState

# The checkpointer lives here so a run paused at the human gate survives a
# restart. Same directory as the app database.
CHECKPOINT_DIR = 'instance'
CHECKPOINT_PATH = os.path.join(CHECKPOINT_DIR, 'twin_agent_checkpoints.sqlite')


def build_graph(ctx, checkpointer=None):
    """Compile the triage graph for one city."""
    graph = StateGraph(TriageState)

    graph.add_node('fetch', nodes.make_fetch(ctx))
    graph.add_node('normalize', nodes.normalize)
    graph.add_node('extract', nodes.make_extract(ctx))
    graph.add_node('geo_resolve', nodes.geo_resolve)
    graph.add_node('correlate', nodes.make_correlate(ctx))
    graph.add_node('score', nodes.make_score(ctx))
    graph.add_node('threshold', nodes.threshold)
    graph.add_node('draft_brief', nodes.make_draft_brief(ctx))
    graph.add_node('persist_flags', nodes.make_persist_flags(ctx))

    graph.set_entry_point('fetch')

    # Nothing came in: stop here, before the first token is spent.
    graph.add_conditional_edges('fetch', nodes.has_work,
                                {'normalize': 'normalize', '__end__': END})

    graph.add_edge('normalize', 'extract')
    graph.add_edge('extract', 'geo_resolve')
    graph.add_edge('geo_resolve', 'correlate')
    graph.add_edge('correlate', 'score')
    graph.add_edge('score', 'threshold')

    # Nothing cleared the cutoff: stop before the brief writer.
    graph.add_conditional_edges('threshold', nodes.has_flags,
                                {'draft_brief': 'draft_brief', '__end__': END})

    graph.add_edge('draft_brief', 'persist_flags')
    graph.add_edge('persist_flags', END)

    return graph.compile(checkpointer=checkpointer)


def open_checkpointer():
    """A SqliteSaver, or None if it cannot be opened.

    The graph runs fine without one - it simply cannot be resumed across a
    restart, and the DB-backed flag queue is the durable gate either way.
    """
    try:
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver

        os.makedirs(CHECKPOINT_DIR, exist_ok=True)
        # check_same_thread=False: the scheduler runs this on a worker thread.
        connection = sqlite3.connect(CHECKPOINT_PATH, check_same_thread=False)
        return SqliteSaver(connection)
    except Exception:  # noqa: BLE001
        return None
