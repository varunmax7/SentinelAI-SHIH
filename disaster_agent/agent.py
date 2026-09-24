"""Step 3 - NARRATE, and the three-step orchestrator.

    INGEST (ingest.py)  ->  PROJECT (advect.py)  ->  NARRATE (this module)

`run_prediction_cycle` is the whole agent in one call: pull live wind/cloud/
heat signal for every watched region, deterministically project it downwind
into ranked hotspots, then ask an LLM to turn the top hotspots into an
analyst-facing brief - falling back to a template narrative when no LLM key is
configured, so the feature is fully functional with zero external keys, only
less articulate about it (the same trade-off `twin/` makes everywhere).
"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from . import advect, config as agent_config, ingest
from .schemas import PredictionBrief

SEVERITY_BANDS = (
    (85.0, 'critical'),
    (70.0, 'high'),
    (55.0, 'medium'),
)


def severity_for(risk_score):
    for cutoff, label in SEVERITY_BANDS:
        if risk_score >= cutoff:
            return label
    return 'low'


def run_prediction_cycle(db, models, now=None, llm=None):
    """The full cycle. Returns a summary dict; never raises into the caller -

    a bad cycle leaves yesterday's predictions in place rather than wiping the
    panel, matching the rest of the app's "degrade, never crash" rule.
    """
    now = now or datetime.utcnow()
    try:
        signals = ingest.fetch_region_signals()
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'stage': 'ingest', 'error': str(exc)}

    if not signals:
        return {'ok': True, 'stage': 'ingest', 'regions': 0, 'hotspots': 0, 'narrated': 0}

    try:
        hotspots = advect.project_hotspots(signals)
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'stage': 'project', 'error': str(exc)}

    narrated = hotspots[:agent_config.MAX_NARRATED_HOTSPOTS]
    to_narrate, reused = _split_by_reuse(models, narrated)

    llm = llm if llm is not None else _default_llm()
    fresh = _narrate_concurrently(to_narrate, llm)

    briefs = fresh + reused
    persisted = _persist(db, models, now, briefs)
    return {
        'ok': True, 'regions': len(signals), 'hotspots': len(hotspots),
        'narrated': len(narrated), 'llm_calls': len(to_narrate),
        'reused': len(reused), 'persisted': persisted,
        'ran_at': now.isoformat(),
    }


# --- reuse: skip the LLM when nothing material changed --------------------------
def _split_by_reuse(models, hotspots):
    """Hotspots into (needs a fresh narrative, can reuse the last one).

    A quiet cycle - risk scores drifting a couple of points, same leading
    source - should cost zero LLM calls, the same principle
    twin/agent/graph.py applies to its own triage runs.
    """
    if not hotspots:
        return [], []

    # A plain single-column IN, not a composite (region, hazard) tuple IN -
    # portable across every DB backend this app might run on, at the cost of
    # a handful of extra rows fetched (filtered out in Python below).
    slugs = {h['target_slug'] for h in hotspots}
    candidates = (models.DisasterPrediction.query
                  .filter(models.DisasterPrediction.region_slug.in_(slugs))
                  .filter(models.DisasterPrediction.status == 'active')
                  .all())
    existing_by_key = {(row.region_slug, row.hazard_type): row for row in candidates}

    to_narrate, reused = [], []
    for hotspot in hotspots:
        row = existing_by_key.get((hotspot['target_slug'], hotspot['hazard_type']))
        if _needs_fresh_narrative(hotspot, row):
            to_narrate.append(hotspot)
        else:
            reused.append(dict(hotspot,
                              headline=row.headline,
                              narrative=row.narrative,
                              recommended_action=row.recommended_action,
                              confidence_label=row.confidence_label,
                              citation_sources=[s.get('region') for s in row.contributing_sources()],
                              generated_offline=row.generated_offline))
    return to_narrate, reused


def _needs_fresh_narrative(hotspot, row):
    if row is None or not row.narrative:
        return True
    # A template brief is upgraded to an LLM one the moment a key becomes
    # available, rather than staying template-worded indefinitely.
    if row.generated_offline and agent_config.llm_available():
        return True
    if abs(hotspot['risk_score'] - (row.risk_score or 0.0)) > agent_config.REUSE_RISK_DELTA:
        return True
    # A window that has shifted is exactly the kind of change an analyst is
    # watching for - "eases by 20:00" turning into "eases by 04:00" must not be
    # hidden behind a reused narrative just because the score barely moved.
    window = hotspot.get('window') or {}
    if _iso(window.get('ends_at')) != _iso(row.window_ends_at):
        return True
    if _iso(window.get('starts_at')) != _iso(row.window_starts_at):
        return True

    previous_top_source = (row.contributing_sources() or [{}])[0].get('region')
    current_top_source = (hotspot['sources'] or [{}])[0].get('region')
    return previous_top_source != current_top_source


def _iso(value):
    return value.replace(microsecond=0).isoformat() if isinstance(value, datetime) else None


# --- narration -----------------------------------------------------------------
def _narrate_concurrently(hotspots, llm):
    """Every hotspot that needs a fresh brief, narrated in parallel.

    LLM calls are network-bound HTTP round-trips, not CPU work, so a thread
    pool turns N sequential round-trips into roughly one round-trip's worth
    of wall-clock time.
    """
    if not hotspots:
        return []
    workers = min(agent_config.NARRATE_MAX_WORKERS, len(hotspots))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda h: _narrate(h, llm=llm), hotspots))


def _narrate(hotspot, llm=None):
    """One hotspot -> a dict ready to persist, with or without an LLM."""
    if llm is None:
        llm = _default_llm()

    brief = None
    if llm is not None and llm.available():
        prompt = _build_prompt(hotspot)
        brief = llm.invoke(PredictionBrief, prompt, system=_SYSTEM_PROMPT)

    if brief is None:
        return dict(hotspot, **_offline_brief(hotspot), generated_offline=True)

    return dict(hotspot,
               headline=brief.headline,
               narrative=brief.narrative,
               recommended_action=brief.recommended_action,
               confidence_label=brief.confidence_label,
               citation_sources=brief.citation_sources,
               generated_offline=False)


def _default_llm():
    try:
        from twin.llm import StructuredLLM
    except Exception:  # noqa: BLE001 - langgraph/pydantic stack not installed
        return None
    if not agent_config.llm_available():
        return None
    return StructuredLLM(api_key=agent_config.llm_api_key(),
                         model=agent_config.llm_model(),
                         timeout=agent_config.llm_timeout_s())


_SYSTEM_PROMPT = (
    "You write short operational briefs for disaster-management analysts from "
    "a deterministic wind/cloud/fire-danger projection. You never invent a "
    "number, place or time that was not supplied. If the supplied sources "
    "disagree or are weak, say so and lower your confidence_label rather than "
    "asserting certainty."
)


def _build_prompt(hotspot):
    lines = [
        'Region projected to be affected: %s, %s' % (
            hotspot.get('target_name') or hotspot['target_slug'], hotspot.get('target_state', '')),
        'Hazard type: %s' % hotspot['hazard_type'],
        'Time horizon: next %d hour(s)' % hotspot['horizon_hours'],
        'Deterministic projected risk: %.0f/100' % hotspot['risk_score'],
        'Contributing source regions:',
    ]
    for src in hotspot['sources']:
        bits = ['  - %s, %s (%s)' % (src['region'], src['state'], src['role'])]
        if 'distance_km' in src:
            bits.append('distance %.0f km, bearing alignment %.0f%%' % (
                src['distance_km'], src['bearing_alignment_pct']))
        if src.get('wind_speed_kmh') is not None:
            bits.append('wind %.0f km/h from %s deg' % (
                src['wind_speed_kmh'], _fmt(src.get('wind_dir_deg'))))
        if src.get('cloud_cover_pct') is not None:
            bits.append('cloud cover %.0f%%' % src['cloud_cover_pct'])
        if src.get('fire_weather_index') is not None:
            bits.append('fire weather index %.0f/100' % src['fire_weather_index'])
        if src.get('temperature_c') is not None:
            bits.append('temperature %.1f C' % src['temperature_c'])
        lines.append(', '.join(bits))
    if hotspot.get('window_text'):
        lines.append('')
        lines.append('Timing (already computed from the hourly forecast - quote it, never '
                     'recompute or round it): %s' % hotspot['window_text'])
    lines.append('')
    lines.append('Write the brief for this hotspot only, grounded strictly in the numbers above.')
    return '\n'.join(lines)


def _fmt(value):
    return 'n/a' if value is None else ('%.0f' % value)


def _offline_brief(hotspot):
    """Deterministic template narrative - no LLM required, no confidence

    invented beyond what the sources already say.
    """
    top_source = hotspot['sources'][0] if hotspot['sources'] else {}
    region = hotspot.get('target_name') or hotspot['target_slug']
    hazard = hotspot['hazard_type'].replace('_', ' ')
    origin = top_source.get('role') == 'origin'

    if origin:
        headline = '%s: elevated %s signal, next %dh' % (region, hazard, hotspot['horizon_hours'])
        narrative = (
            '%s itself is showing an elevated %s signal (projected risk %.0f/100). '
            'This is a local reading, not a downwind projection from another region.'
            % (region, hazard, hotspot['risk_score'])
        )
    else:
        headline = '%s: %s risk projected from %s, next %dh' % (
            region, hazard, top_source.get('region', 'an upwind region'), hotspot['horizon_hours'])
        narrative = (
            '%s carries a projected %s risk of %.0f/100 over the next %d hour(s), '
            'driven by conditions at %s (%.0f km away, %.0f%% bearing alignment with '
            'the prevailing wind).' % (
                region, hazard, hotspot['risk_score'], hotspot['horizon_hours'],
                top_source.get('region', 'an upwind source'),
                top_source.get('distance_km', 0.0), top_source.get('bearing_alignment_pct', 0.0))
        )

    if hotspot.get('window_text'):
        narrative += ' ' + hotspot['window_text']

    confidence = 'high' if len(hotspot['sources']) > 1 and hotspot['risk_score'] >= 70 else (
        'medium' if hotspot['risk_score'] >= 55 else 'low')

    return {
        'headline': headline,
        'narrative': narrative,
        'recommended_action': (
            'Cross-check against official IMD/SACHET warnings for %s before alerting the public.'
            % region
        ),
        'confidence_label': confidence,
        'citation_sources': [s['region'] for s in hotspot['sources']],
    }


# --- persistence -----------------------------------------------------------------
def _persist(db, models, now, briefs):
    """Upsert each brief keyed on (region, hazard, horizon); anything not

    refreshed this cycle is marked expired rather than deleted, so a
    dismissed-then-recomputed prediction still has an audit trail.
    """
    touched_ids = []
    for brief in briefs:
        row = (models.DisasterPrediction.query
               .filter_by(region_slug=brief['target_slug'], hazard_type=brief['hazard_type'])
               .filter(models.DisasterPrediction.status != 'dismissed')
               .first())
        if row is None:
            row = models.DisasterPrediction(
                region_slug=brief['target_slug'], hazard_type=brief['hazard_type'])
            db.session.add(row)

        row.region_name = brief.get('target_name') or brief['target_slug']
        row.state = brief.get('target_state')
        row.latitude = brief.get('target_lat')
        row.longitude = brief.get('target_lon')
        row.horizon_hours = brief['horizon_hours']
        row.predicted_for = now + timedelta(hours=brief['horizon_hours'])
        row.risk_score = brief['risk_score']
        row.severity = severity_for(brief['risk_score'])
        row.headline = brief['headline']
        row.narrative = brief['narrative']
        row.recommended_action = brief['recommended_action']
        row.confidence_label = brief['confidence_label']
        row.contributing_json = json.dumps(brief['sources'], default=str)
        window = brief.get('window') or {}
        row.window_starts_at = window.get('starts_at')
        row.window_ends_at = window.get('ends_at')
        row.window_peak_at = window.get('peak_at')
        row.window_peak_strength = window.get('peak_strength')
        row.window_state = window.get('state')
        row.window_open_ended = bool(window.get('open_ended'))
        row.window_text = brief.get('window_text')
        row.generated_offline = bool(brief.get('generated_offline'))
        row.status = 'active'
        row.updated_at = now
        db.session.flush()
        touched_ids.append(row.id)

    stale_query = models.DisasterPrediction.query.filter(
        models.DisasterPrediction.status == 'active')
    if touched_ids:
        stale_query = stale_query.filter(~models.DisasterPrediction.id.in_(touched_ids))
    for row in stale_query.all():
        row.status = 'expired'

    db.session.commit()
    return len(touched_ids)
