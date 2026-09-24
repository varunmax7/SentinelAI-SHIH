"""The forecast graph's nodes.

Same rule as nodes.py: `twin/forecast.py` is pure, deterministic and
unit-tested on its own (advect/detect/threshold never touch the LLM). The
model's only job here is turning an already-decided event into a paragraph -
see `_forecast_prompt`'s explicit rule that it must quote the hour, value and
confidence rather than reason about them.

`make_persist_flags` is imported from `nodes.py`, not reimplemented: a
forecast event becomes a row in the exact same `twin_flag` table, through the
exact same human-gate function, that a triage cluster does. Two source
agents, one queue, one review flow - an official approving flags does not
need to know or care which agent drafted a given one.
"""

import hashlib

from .. import config as twin_config
from .. import forecast
from ..ingest.windfield import WindFieldAdapter
from .nodes import make_persist_flags  # noqa: F401 - re-exported for forecast_graph
from .schemas import Brief

SEVERITY_TO_SCORE = {'critical': 90.0, 'warning': 65.0, 'watch': 45.0}


class ForecastContext(object):
    """Same role as `nodes.TriageContext`, kept separate rather than shared:

    the forecast agent needs no `Report` model and a different system prompt,
    and forcing one context class to serve both would couple two independent
    agents together for no benefit.
    """

    def __init__(self, db, models, city):
        self.db = db
        self.models = models
        self.city = city
        self.llm_calls = 0
        self._llm = None

    SYSTEM = (
        "You are a forecast assistant for an Indian city emergency operations "
        "centre. A deterministic wind-advection model has already decided the "
        "hazard, its arrival hour, its severity band and its confidence - you "
        "quote those numbers, you never estimate or adjust them yourself. Say "
        "explicitly that this is a projection, not an observation. You never "
        "output a coordinate."
    )

    def invoke(self, schema, prompt):
        if not twin_config.agent_available():
            return None
        if self._llm is None:
            from ..llm import StructuredLLM
            self._llm = StructuredLLM()
        result = self._llm.invoke(schema, prompt, system=self.SYSTEM)
        self.llm_calls = self._llm.calls
        return result

    def llm_stats(self):
        return self._llm.stats() if self._llm else {'calls': 0, 'tokens': 0, 'cost_usd': 0.0}


# --- 1. sample ---------------------------------------------------------------
def make_sample(ctx):
    def sample(state):
        """Hourly wind/cloud/rain/apparent-temperature at the city's coarse

        lattice - the same sample points `ingest/open_meteo.py` already
        shares one weather reading across every child cell with.
        """
        from ..ingest.open_meteo import sample_cells

        h3_indexes = [c.h3_index for c in ctx.city.cells]
        _by_cell, points = sample_cells(h3_indexes)
        result = WindFieldAdapter().run(points=points)
        from ..ingest.base import record_snapshot
        record_snapshot(ctx.db, ctx.models, ctx.city.id, result)
        return {'windfield': forecast.sample(result.data or {})}
    return sample


def has_windfield(state):
    """First short-circuit: no wind data, nothing to advect. Zero tokens."""
    return 'advect' if state.get('windfield') else '__end__'


# --- 2. advect -----------------------------------------------------------------
def make_advect(ctx):
    def advect(state):
        cell_points = [(c.h3_index, c.center_latitude, c.center_longitude)
                       for c in ctx.city.cells]
        projections = forecast.advect(cell_points, state.get('windfield') or {})
        return {'projections': projections}
    return advect


# --- 3. detect -----------------------------------------------------------------
def detect(state):
    return {'events': forecast.detect(state.get('projections') or [])}


# --- 4. threshold ----------------------------------------------------------------
def threshold(state):
    return {'flagged': forecast.threshold(state.get('events') or [])}


def has_events(state):
    """Second short-circuit: nothing cleared the severity/confidence bar,

    the common case on a calm forecast pass. Must not reach the model.
    """
    return 'draft_brief' if state.get('flagged') else '__end__'


# --- 5. draft_brief (LLM) -------------------------------------------------------
def make_draft_brief(ctx):
    def draft_brief(state):
        briefs = []
        for event in state.get('flagged', []):
            sop_chunks = _sop_citations(event)
            result = ctx.invoke(Brief, _forecast_prompt(ctx.city, event, sop_chunks))

            if result is None:
                briefs.append(_offline_brief(ctx.city, event, sop_chunks))
                continue

            cited_ids = set(result.citation_ids)
            cited_sop = [c for c in sop_chunks if c['id'] in cited_ids]
            briefs.append({
                'cluster_key': _cluster_key(ctx.city, event),
                'title': result.headline,
                'hazard_type': event['hazard_type'],
                'severity': event['severity'],
                'risk_score': _risk_score(event),
                'h3_index': event['worst_cell'],
                'cells': event['cells'],
                'brief_md': '%s\n\n**Recommended action:** %s' % (
                    result.body_md, result.recommended_action),
                'citations': cited_sop,
                'generated_offline': False,
            })
        return {'briefs': briefs, 'used_llm': True}
    return draft_brief


def _sop_citations(event):
    from . import rag
    query = '%s forecast' % event['hazard_type']
    chunks = rag.retrieve(query, top_k=4)
    return [
        {'id': 'sop-%d' % i, 'kind': 'sop', 'sender': None,
         'title': chunk['source'], 'url': None, 'effective_at': None, 'text': chunk['text']}
        for i, chunk in enumerate(chunks)
    ]


def _forecast_prompt(city, event, sop_chunks):
    hazard_label = event['hazard_type'].replace('_', ' ')
    lines = [
        "Write a short brief for a city emergency official about a hazard a",
        "deterministic wind-advection model projects for %s." % city.name,
        "",
        "Rules:",
        "- Use ONLY the figures given below. Do not invent a number, place or time.",
        "- The hazard type, arrival hour, value, severity band and confidence were",
        "  all computed deterministically; quote them, do not reason about them.",
        "- State plainly that this is a projection, not an observation.",
        "- Cite SOP passage ids only if the recommended action actually draws on one.",
        "",
        "Hazard: %s" % hazard_label,
        "Projected arrival: in %d hour(s)" % event['hour'],
        "Severity band: %s" % event['severity'],
        "Value: %s%s" % (event['value'], ' mm/h' if event['hazard_type'] == 'flood' else ' degC'),
        "Confidence: %.0f%%" % (event['confidence'] * 100),
        "Grid cells affected: %d" % len(event['cells']),
    ]
    if sop_chunks:
        lines.append("")
        lines.append("Relevant SOP passages (cite by id if used):")
        for chunk in sop_chunks:
            lines.append("- id=%s | %s | %s" % (chunk['id'], chunk['source'], chunk['text'][:400]))
    return "\n".join(lines)


def _offline_brief(city, event, sop_chunks):
    hazard_label = event['hazard_type'].replace('_', ' ')
    unit = 'mm/h' if event['hazard_type'] == 'flood' else 'degC'
    body = [
        "**Projected %s, %s severity**" % (hazard_label, event['severity']),
        "",
        "- Deterministic wind-advection model projects **%s %s** arriving in "
        "**%d hour(s)**, confidence **%.0f%%**, across **%d** grid cells."
        % (event['value'], unit, event['hour'], event['confidence'] * 100, len(event['cells'])),
    ]
    if sop_chunks:
        body.append("- Related SOP passage(s): %s." %
                    ", ".join(sorted({c['title'] for c in sop_chunks})))
    body.append("")
    body.append("_No language model was available, so this brief is generated from "
                "the forecast model's own numbers only._")
    return {
        'cluster_key': _cluster_key(city, event),
        'title': '%s projected in %dh (%s)' % (hazard_label.capitalize(), event['hour'], event['severity']),
        'hazard_type': event['hazard_type'],
        'severity': event['severity'],
        'risk_score': _risk_score(event),
        'h3_index': event['worst_cell'],
        'cells': event['cells'],
        'brief_md': "\n".join(body),
        'citations': sop_chunks,
        'generated_offline': True,
    }


def _risk_score(event):
    """A synthetic, deterministic score for flag-queue sorting only - not

    `scoring.py`'s risk number (a forecast event has no hydro/incident/env
    sub-scores to compose), so it lives here, named as what it is, rather
    than pretending to be the same measurement.
    """
    base = SEVERITY_TO_SCORE.get(event['severity'], 50.0)
    return round(min(100.0, max(0.0, base + (event['confidence'] * 10.0 - 5.0))), 1)


def _cluster_key(city, event):
    """Keyed on (city, hazard, worst cell) - deliberately NOT on the arrival

    hour. The same physical system re-detected on the next 10-minute poll
    will usually have a *different* projected hour (closer, as time passes),
    and that must update the existing flag, not file a new one every cycle.
    """
    digest = hashlib.sha1(
        ('%s|%s|%s' % (city.slug, event['hazard_type'], event['worst_cell'])).encode('utf-8')
    ).hexdigest()[:16]
    return 'forecast-%s-%s-%s' % (city.slug, event['hazard_type'], digest)
