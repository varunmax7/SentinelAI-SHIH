"""The forecast graph's shared state. Same shape convention as state.py -

see that file's comment on why the list fields are plain assignment, not
`operator.add`: sample/advect/detect/threshold form a transform pipeline,
each stage replacing the previous stage's list, not fanning in copies of it.
"""

from typing import Any, Dict, List

try:
    from typing import TypedDict
except ImportError:  # pragma: no cover - Python < 3.9
    from typing_extensions import TypedDict  # type: ignore


class ForecastState(TypedDict, total=False):
    city_slug: str
    windfield: Dict[str, Any]          # by sample point, from ingest/windfield.py
    projections: List[Dict[str, Any]]  # raw advect() output, before grouping
    events: List[Dict[str, Any]]       # detect() output, grouped
    flagged: List[Dict[str, Any]]      # threshold() output
    briefs: List[Dict[str, Any]]
    flagged_keys: List[str]
    llm_calls: int
    used_llm: bool
