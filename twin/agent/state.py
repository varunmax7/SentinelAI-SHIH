"""The graph's shared state."""

import operator
from typing import Any, Dict, List

try:
    from typing import Annotated, TypedDict
except ImportError:  # pragma: no cover - Python < 3.9
    from typing_extensions import Annotated, TypedDict  # type: ignore


class TriageState(TypedDict, total=False):
    """State threaded through the triage graph.

    `operator.add` on the list fields lets nodes append without reading first,
    which is what makes the graph safe to extend with parallel branches later.
    """

    city_slug: str
    raw_items: List[Dict[str, Any]]           # straight from alerts + reports
    # NOT operator.add. This is a transform pipeline, not a fan-in: `extract`
    # produces the list and `geo_resolve` enriches and re-emits it. With an
    # additive reducer the second node appended its copy to the first's, so a
    # single report became six identical citations on the brief.
    extracted: List[Dict[str, Any]]
    clusters: List[Dict[str, Any]]
    scored: List[Dict[str, Any]]              # deterministic, from twin/scoring.py
    flagged: List[Dict[str, Any]]             # above the configured cutoff
    briefs: List[Dict[str, Any]]
    approved: List[Dict[str, Any]]
    flagged_keys: List[str]
    unchanged: bool                           # feed identical to the last run
    llm_calls: int                            # asserted to be 0 on a quiet run
    used_llm: bool
    errors: Annotated[List[str], operator.add]
