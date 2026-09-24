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

__all__ = ['run_triage', 'run_forecast', 'agent_status']


def agent_status():
    from . import rag
    return {
        'enabled': twin_config.AGENT_ENABLED,
        'forecast_enabled': twin_config.FORECAST_ENABLED,
        # Enabled without a key is a real state, not an error: the pipeline
        # still runs, on deterministic fallbacks, and says so on every brief.
        'llm_available': twin_config.agent_available(),
        'provider': 'openrouter',
        'model': twin_config.AGENT_MODEL if twin_config.agent_available() else None,
        'flag_threshold': twin_config.FLAG_THRESHOLD,
        'rag_corpus_chunks': rag.corpus_size(),
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


def run_forecast(db, models, city_slug=None):
    """Run the forecast agent over one city, or every city.

    Independent of `run_triage` - either can be switched off without
    affecting the other - but both write to the same `twin_flag` queue
    through the same human-gated `persist_flags`, so an official reviews one
    list regardless of which agent drafted a given flag.
    """
    if not twin_config.FORECAST_ENABLED:
        return {'enabled': False,
                'note': 'TWIN_FORECAST_ENABLED=0 - forecast did not run.'}

    from .forecast_graph import build_forecast_graph
    from .forecast_nodes import ForecastContext
    from .graph import open_checkpointer

    query = models.TwinCity.query
    if city_slug:
        query = query.filter_by(slug=city_slug)
    cities = query.all()
    if not cities:
        return {'error': 'no cities seeded'}

    checkpointer = open_checkpointer()
    out = {'enabled': True, 'llm_available': twin_config.agent_available(), 'cities': {}}

    for city in cities:
        if not list(city.cells):
            out['cities'][city.slug] = {'error': 'grid not seeded'}
            continue
        ctx = ForecastContext(db, models, city)
        try:
            graph = build_forecast_graph(ctx, checkpointer=checkpointer)
            config = {'configurable': {'thread_id': 'twin-forecast-%s' % city.slug}}
            # Every key seeded explicitly, not `{}` - the checkpointer resumes
            # from the last checkpoint under this same thread_id on every
            # scheduled cycle, and a node that does not touch a key (e.g.
            # `threshold` returning an empty `flagged` list still touches it,
            # but a node that raised before running at all would not) must
            # never silently inherit a previous cycle's stale value.
            state = graph.invoke({
                'windfield': {}, 'projections': [], 'events': [],
                'flagged': [], 'briefs': [], 'flagged_keys': [],
            }, config=config)

            out['cities'][city.slug] = {
                'sample_points': len(state.get('windfield') or {}),
                'projections': len(state.get('projections') or []),
                'events': len(state.get('events') or []),
                'flagged': len(state.get('flagged') or []),
                'briefs': len(state.get('briefs') or []),
                'pending_written': state.get('flagged_keys') or [],
                'llm_calls': ctx.llm_calls,
                'llm': ctx.llm_stats(),
            }
        except Exception as exc:  # noqa: BLE001 - one city must not stop the other
            db.session.rollback()
            out['cities'][city.slug] = {'error': '%s: %s' % (type(exc).__name__, exc)}

    return out
