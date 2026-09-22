"""The triage agent.

A LangGraph pipeline that turns live official alerts and citizen reports into
briefs an admin reviews. Four language jobs - extract, correlate, summarise,
cite - and one arithmetic job that is deliberately not the model's:
`twin/scoring.py` computes the risk, exactly as it does for the map.

Switching it off is a supported steady state. With `TWIN_AGENT_ENABLED=0` the
job is never scheduled, `run_triage` returns immediately, and the rest of the
twin behaves exactly as it does without this package.
"""

from datetime import datetime

from .. import config as twin_config

__all__ = ['run_triage', 'agent_status']


def agent_status():
    return {
        'enabled': twin_config.AGENT_ENABLED,
        # Enabled without a key is a real state, not an error: the pipeline
        # still runs, on deterministic fallbacks, and says so on every brief.
        'llm_available': twin_config.agent_available(),
        'provider': 'openrouter',
        'model': twin_config.AGENT_MODEL if twin_config.agent_available() else None,
        'flag_threshold': twin_config.FLAG_THRESHOLD,
    }


def run_triage(db, models, city_slug=None):
    """Run triage over one city, or every city. Returns a summary per city."""
    if not twin_config.AGENT_ENABLED:
        return {'enabled': False,
                'note': 'TWIN_AGENT_ENABLED=0 - triage did not run.'}

    from .graph import build_graph, open_checkpointer
    from .nodes import TriageContext
    from ..ingest.internal_reports import LOOKBACK_HOURS  # noqa: F401  (documents the window)

    query = models.TwinCity.query
    if city_slug:
        query = query.filter_by(slug=city_slug)
    cities = query.all()
    if not cities:
        return {'error': 'no cities seeded'}

    from models import Report  # host application model

    checkpointer = open_checkpointer()
    out = {'enabled': True, 'llm_available': twin_config.agent_available(), 'cities': {}}

    for city in cities:
        ctx = TriageContext(db, models, city, Report)
        try:
            graph = build_graph(ctx, checkpointer=checkpointer)
            config = {'configurable': {'thread_id': 'twin-triage-%s' % city.slug}}
            state = graph.invoke({'raw_items': [], 'extracted': [], 'errors': []},
                                 config=config)
            # Record what was processed so the next poll can tell whether
            # anything actually changed. Only on a run that got past fetch -
            # a skipped run must not overwrite the fingerprint it skipped on.
            if ctx.fingerprint is not None and not state.get('unchanged'):
                city.last_triage_fingerprint = ctx.fingerprint
                city.last_triage_at = datetime.utcnow()
                db.session.commit()

            out['cities'][city.slug] = {
                'items': len(state.get('raw_items') or []),
                'unchanged': bool(state.get('unchanged')),
                'clusters': len(state.get('clusters') or []),
                'scored': len(state.get('scored') or []),
                'flagged': len(state.get('flagged') or []),
                'briefs': len(state.get('briefs') or []),
                'pending_written': state.get('flagged_keys') or [],
                # Asserted by the acceptance criteria: a quiet cycle is zero.
                'llm_calls': ctx.llm_calls,
                'llm': ctx.llm_stats(),
            }
        except Exception as exc:  # noqa: BLE001 - one city must not stop the other
            db.session.rollback()
            out['cities'][city.slug] = {'error': '%s: %s' % (type(exc).__name__, exc)}

    return out
