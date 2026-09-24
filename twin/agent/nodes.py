"""The graph's nodes.

The rule this file exists to enforce: **the LLM never computes risk.**

`twin/scoring.py` is pure, deterministic and unit-testable. When an official
acts on a flag and is asked why a zone was flagged, the answer has to be
"62 mm/3h against a 30 mm threshold", not "the model said so". So `score_node`
reads the numbers the deterministic scorer already produced and does arithmetic
in Python. The model's four jobs are all language jobs: classify, group,
summarise, cite.

Every LLM node has a deterministic fallback that runs when the agent has no API
key. The fallback is not a simulation of the model - it is a plainer, dumber
path that produces honest output marked `generated_offline`, so the feature is
demonstrable and auditable with no key configured at all.
"""

import hashlib
import json
from datetime import datetime, timedelta

from .. import config as twin_config
from ..alerts import live_alerts
from ..ingest.internal_reports import collect_incidents
from .schemas import (Brief, CorrelationResult, ExtractionResult,
                      HAZARD_TYPES, SEVERITY_LABELS)

# How far back a citizen report is still considered part of "what is happening
# now" for triage purposes. Shorter than the scorer's 72 h lookback: triage is
# about the live picture, not the decayed tail.
REPORT_WINDOW_HOURS = 12


class TriageContext(object):
    """Everything the nodes need that is not graph state.

    Held outside `TriageState` on purpose: a SQLAlchemy session is not
    serialisable, and the checkpointer has to be able to write the state to
    disk between the draft and the human decision.
    """

    def __init__(self, db, models, city, Report):
        self.db = db
        self.models = models
        self.city = city
        self.Report = Report
        self.llm_calls = 0
        self._llm = None
        self.fingerprint = None

    # -- LLM plumbing -------------------------------------------------------
    SYSTEM = (
        "You are a triage assistant for an Indian city emergency operations centre. "
        "You classify, group and summarise. You never estimate danger yourself: a "
        "separate deterministic model computes every risk score, and you quote its "
        "numbers rather than reasoning about them. You never output coordinates."
    )

    def invoke(self, schema, prompt):
        """Ask the model for one structured object, or None to fall back.

        `None` is a normal outcome, not an error path: no key configured, the
        service being down, or a reply that fails schema validation all land
        here, and every caller has a deterministic route for it.
        """
        if not twin_config.agent_available():
            return None
        if self._llm is None:
            from ..llm import StructuredLLM
            self._llm = StructuredLLM()

        result = self._llm.invoke(schema, prompt, system=self.SYSTEM)
        # Counted from the client so the tally reflects requests actually sent,
        # including the ones that failed - a quiet-cycle assertion of "zero
        # calls" is only meaningful if failures count too.
        self.llm_calls = self._llm.calls
        return result

    def llm_stats(self):
        return self._llm.stats() if self._llm else {'calls': 0, 'tokens': 0, 'cost_usd': 0.0}


# --- 1. gather -------------------------------------------------------------
def make_fetch(ctx):
    def fetch(state):
        """Live official alerts plus recent citizen reports for this city."""
        now = datetime.utcnow()
        items = []

        for alert in live_alerts(ctx.models, ctx.city, now):
            cells = [c.h3_index for c in alert.cells.filter_by(city_id=ctx.city.id)]
            items.append({
                'id': 'alert:%s' % alert.id,
                'kind': 'official_alert',
                'source': alert.source,
                'sender': alert.sender,
                'title': alert.headline or alert.event,
                'text': ' '.join(filter(None, [alert.event, alert.headline,
                                               alert.description, alert.area_desc])),
                'priority': alert.priority,
                'confidence': alert.confidence,
                'severity_raw': alert.severity,
                'certainty_raw': alert.certainty,
                'category': alert.category,
                'effective_at': _iso(alert.effective_at),
                'expires_at': _iso(alert.expires_at),
                'cells': cells,
                'url': alert.raw_url,
            })

        _scoring, pins = collect_incidents(
            ctx.Report, ctx.city.bbox, resolution=ctx.city.h3_resolution, now=now)
        cutoff = now - timedelta(hours=REPORT_WINDOW_HOURS)
        for pin in pins:
            if pin['status'] != 'approved' or pin['timestamp'] < cutoff:
                continue
            items.append({
                'id': 'report:%s' % pin['id'],
                'kind': 'citizen_report',
                'source': 'internal',
                'sender': 'citizen',
                'title': pin['title'],
                'text': ' '.join(filter(None, [pin['title'], pin['hazard_type'], pin['location']])),
                'priority': pin['priority'],
                'confidence': pin['confidence'],
                'hazard_type': pin['hazard_type'],
                'effective_at': _iso(pin['timestamp']),
                'expires_at': None,
                'cells': [pin['h3']],
                'url': '/report/%s' % pin['id'],
            })

        fingerprint = _fingerprint(items)
        unchanged = bool(items) and fingerprint == (ctx.city.last_triage_fingerprint or '')
        if unchanged:
            # Same items as last time. Nothing an LLM could say about them has
            # changed either, so stop before spending anything. Without this the
            # single standing report in this database would be re-extracted
            # every five minutes, for ever, for an identical answer.
            items = []

        ctx.fingerprint = fingerprint
        return {'raw_items': items, 'city_slug': ctx.city.slug,
                'unchanged': unchanged, 'llm_calls': 0, 'used_llm': False}
    return fetch


def _fingerprint(items):
    """Identity of an item set: which items, and when each took effect.

    Includes effective_at so a re-issued alert with the same id is treated as
    new work, and excludes anything that changes on every fetch (row ids,
    fetch timestamps) so an unchanged feed really does hash the same.
    """
    if not items:
        return ''
    seed = '|'.join(sorted('%s@%s' % (i['id'], i.get('effective_at') or '')
                           for i in items))
    return hashlib.sha1(seed.encode('utf-8')).hexdigest()


def has_work(state):
    """Conditional edge, and the main cost control.

    Routes to END when the feed is empty *or* unchanged since the last run -
    which is the normal case on a five-minute poll - so a quiet cycle costs
    zero tokens rather than one cheap call.
    """
    return 'normalize' if state.get('raw_items') else '__end__'


# --- 2. normalize ----------------------------------------------------------
def normalize(state):
    """Cap the batch. One unusually loud feed day must not become an unbounded
    bill, so the highest-priority items win and the rest wait for the next run."""
    rank = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    items = sorted(state['raw_items'],
                   key=lambda i: (rank.get(i.get('priority'), 9),
                                  -(i.get('confidence') or 0)))
    return {'raw_items': items[:twin_config.AGENT_MAX_ITEMS]}


# --- 3. extract (LLM, job 1) ----------------------------------------------
def make_extract(ctx):
    def extract(state):
        items = state['raw_items']
        result = ctx.invoke(ExtractionResult, _extraction_prompt(items))

        if result is None:
            # Deterministic fallback. CAP is already structured - severity and
            # certainty are fixed enumerations - so for official alerts this
            # loses almost nothing. It is the free-text nuance that goes.
            extracted = [{
                'item_id': item['id'],
                'hazard_type': _guess_hazard(item),
                'severity_label': item.get('priority') or 'low',
                'summary': (item.get('title') or '')[:220],
                'area_phrase': item.get('area_desc'),
                'time_window': None,
                'offline': True,
            } for item in items]
            return {'extracted': extracted}

        by_id = {i['id'] for i in items}
        extracted = []
        for row in result.items:
            # The model may only label items it was given. Anything else is a
            # hallucinated id and is dropped rather than trusted.
            if row.item_id not in by_id:
                continue
            extracted.append({
                'item_id': row.item_id,
                'hazard_type': row.hazard_type if row.hazard_type in HAZARD_TYPES else 'other',
                'severity_label': row.severity_label if row.severity_label in SEVERITY_LABELS else 'low',
                'summary': row.summary,
                'area_phrase': row.area_phrase,
                'time_window': row.time_window,
                'offline': False,
            })
        return {'extracted': extracted, 'used_llm': True}
    return extract


def _extraction_prompt(items):
    lines = [
        "You are triaging live disaster alerts for an Indian city emergency operations centre.",
        "For each item below, classify the hazard and severity and write one plain sentence.",
        "",
        "Rules:",
        "- Use only the item ids given. Do not invent ids.",
        "- Never output coordinates, latitudes, longitudes or risk scores.",
        "- Copy any place name verbatim from the text; do not infer places not written there.",
        "- If the text does not say, leave the field empty rather than guessing.",
        "",
        "Items:",
    ]
    for item in items:
        lines.append("- id=%s | source=%s (%s) | %s" % (
            item['id'], item.get('source'), item.get('sender'), (item.get('text') or '')[:600]))
    return "\n".join(lines)


def _guess_hazard(item):
    """Keyword fallback. Crude on purpose - it is a stand-in for job 1, not a
    replacement, and it is marked offline wherever its output surfaces."""
    if item.get('hazard_type') in HAZARD_TYPES:
        return item['hazard_type']
    text = (item.get('text') or '').lower()
    for needle, hazard in (
        ('thunderstorm', 'thunderstorm'), ('lightning', 'thunderstorm'),
        ('heavy rain', 'heavy_rain'), ('rainfall', 'heavy_rain'),
        ('flood', 'flood'), ('inundat', 'flood'),
        ('cyclone', 'cyclone'), ('depression', 'cyclone'),
        ('heat wave', 'heat_wave'), ('heatwave', 'heat_wave'),
        ('earthquake', 'earthquake'), ('quake', 'earthquake'),
        ('fire', 'wildfire'), ('tsunami', 'tsunami'),
    ):
        if needle in text:
            return hazard
    return 'other'


# --- 4. geo_resolve (plain) ------------------------------------------------
def geo_resolve(state):
    """Attach the cells each item already resolved to at ingest.

    The model is never asked where something is. Geography comes from the CAP
    polygon and the H3 grid, both of which are checkable.
    """
    cells_by_item = {i['id']: i.get('cells') or [] for i in state['raw_items']}
    extracted = []
    for row in state.get('extracted', []):
        row = dict(row)
        row['cells'] = cells_by_item.get(row['item_id'], [])
        extracted.append(row)
    return {'extracted': extracted, 'clusters': []}


# --- 5. correlate (LLM, job 2) --------------------------------------------
def make_correlate(ctx):
    def correlate(state):
        extracted = state.get('extracted', [])
        if not extracted:
            return {'clusters': []}

        items_by_id = {i['id']: i for i in state['raw_items']}
        result = ctx.invoke(CorrelationResult, _correlation_prompt(extracted, items_by_id))

        if result is None:
            # Fallback: group by hazard type plus overlapping cells. Cheap and
            # explainable, and it catches the common case - one IMD warning and
            # the citizen reports underneath it.
            groups = {}
            for row in extracted:
                groups.setdefault(row['hazard_type'], {})[row['item_id']] = row
            clusters = [{
                'cluster_id': hazard,
                'item_ids': sorted(rows.keys()),
                'title': '%s affecting %s' % (hazard.replace('_', ' ').title(),
                                              ctx.city.name),
                'hazard_type': hazard,
                'rationale': 'Grouped by hazard type (no language model available).',
                'offline': True,
            } for hazard, rows in groups.items()]
            return {'clusters': clusters}

        valid = {r['item_id'] for r in extracted}
        clusters = []
        for cluster in result.clusters:
            members = sorted({i for i in cluster.item_ids if i in valid})
            if not members:
                continue
            clusters.append({
                'cluster_id': cluster.cluster_id,
                'item_ids': members,
                'title': cluster.title,
                'hazard_type': cluster.hazard_type if cluster.hazard_type in HAZARD_TYPES else 'other',
                'rationale': cluster.rationale,
                'offline': False,
            })
        return {'clusters': clusters, 'used_llm': True}
    return correlate


def _correlation_prompt(extracted, items_by_id):
    lines = [
        "Group the items below into real-world events. One IMD warning plus the",
        "citizen reports underneath it are ONE event, not four.",
        "",
        "Rules:",
        "- Every item id must appear in exactly one cluster.",
        "- Use only the ids given.",
        "- Do not output coordinates or risk scores.",
        "",
        "Items:",
    ]
    for row in extracted:
        source = items_by_id.get(row['item_id'], {})
        lines.append("- id=%s | %s | hazard=%s severity=%s | area=%s | %s" % (
            row['item_id'], source.get('kind'), row['hazard_type'],
            row['severity_label'], row.get('area_phrase') or 'unstated',
            (row.get('summary') or '')[:220]))
    return "\n".join(lines)


# --- 6. score (DETERMINISTIC - never an LLM) ------------------------------
def make_score(ctx):
    def score(state):
        """Read the risk the deterministic scorer already computed.

        This node is the reason the whole design holds together. It does not ask
        a model anything. It looks up `TwinCellState` - written by
        `twin/engine.py` from `twin/scoring.py` - and takes the worst cell in
        each cluster's footprint. Reproducible, auditable, and explainable to
        somebody who has to justify an evacuation.
        """
        models = ctx.models
        cells_by_item = {i['id']: i.get('cells') or [] for i in state['raw_items']}

        scored = []
        for cluster in state.get('clusters', []):
            cells = sorted({c for item_id in cluster['item_ids']
                            for c in cells_by_item.get(item_id, [])})
            if not cells:
                continue

            worst_score, worst_cell, worst_status = 0.0, None, 'normal'
            # Chunked: SQLite caps a statement at 999 bound parameters and an
            # alert footprint routinely exceeds that.
            for start in range(0, len(cells), 500):
                rows = (ctx.db.session.query(models.TwinCell.h3_index,
                                             models.TwinCellState.risk_score,
                                             models.TwinCellState.status)
                        .join(models.TwinCellState,
                              models.TwinCellState.cell_id == models.TwinCell.id)
                        .filter(models.TwinCell.city_id == ctx.city.id,
                                models.TwinCell.h3_index.in_(cells[start:start + 500]),
                                models.TwinCellState.horizon_hours == 0)
                        .all())
                for h3_index, risk, status in rows:
                    if (risk or 0.0) > worst_score:
                        worst_score, worst_cell, worst_status = risk or 0.0, h3_index, status

            entry = dict(cluster)
            entry.update({
                'cells': cells,
                'cell_count': len(cells),
                'risk_score': round(worst_score, 2),
                'worst_cell': worst_cell,
                'status': worst_status,
            })
            scored.append(entry)

        scored.sort(key=lambda c: c['risk_score'], reverse=True)
        return {'scored': scored}
    return score


# --- 7. threshold (plain) --------------------------------------------------
def threshold(state):
    cutoff = twin_config.FLAG_THRESHOLD
    return {'flagged': [c for c in state.get('scored', [])
                        if c['risk_score'] >= cutoff]}


def has_flags(state):
    """Second short-circuit. Nothing above the cutoff is the common case, and
    it must not reach the brief-writing model."""
    return 'draft_brief' if state.get('flagged') else '__end__'


# --- 8. draft_brief (LLM, job 4) ------------------------------------------
def make_draft_brief(ctx):
    def draft_brief(state):
        items_by_id = {i['id']: i for i in state['raw_items']}
        briefs = []

        for cluster in state['flagged']:
            # Deduplicated and order-stable: a cluster must never cite the same
            # source twice, and a brief's citation list is read by a human.
            seen = set()
            sources = []
            for item_id in cluster['item_ids']:
                if item_id in items_by_id and item_id not in seen:
                    seen.add(item_id)
                    sources.append(items_by_id[item_id])
            sop_chunks = _sop_citations(cluster)
            result = ctx.invoke(Brief, _brief_prompt(cluster, sources, ctx.city, sop_chunks))

            if result is None:
                briefs.append(_offline_brief(cluster, sources, ctx.city, sop_chunks))
                continue

            cited_ids = set(result.citation_ids)
            cited = [s for s in sources if s['id'] in cited_ids]
            # A brief that cites nothing is a brief nobody can check. If the
            # model cited nothing valid, fall back to citing everything it was
            # shown rather than publishing an uncheckable claim.
            if not cited:
                cited = sources
            cited_sop = [c for c in sop_chunks if c['id'] in cited_ids]
            briefs.append({
                'cluster_key': _cluster_key(ctx.city, cluster),
                'title': result.headline,
                'hazard_type': cluster['hazard_type'],
                'severity': cluster['status'],
                'risk_score': cluster['risk_score'],
                'h3_index': cluster.get('worst_cell'),
                'cells': cluster.get('cells') or [],
                'brief_md': '%s\n\n**Recommended action:** %s' % (
                    result.body_md, result.recommended_action),
                'citations': [_citation(s) for s in cited] + cited_sop,
                'generated_offline': False,
            })
        return {'briefs': briefs, 'used_llm': True}
    return draft_brief


def _brief_prompt(cluster, sources, city, sop_chunks=None):
    lines = [
        "Write a short brief for a city emergency official who must decide whether",
        "to act on this event in %s." % city.name,
        "",
        "Rules:",
        "- Use ONLY the figures given below. Do not compute or invent any number.",
        "- The risk score was produced by a deterministic model; quote it, do not reason about it.",
        "- Say plainly what is uncertain.",
        "- Cite the source ids your claims rest on.",
        "",
        "Event: %s (hazard: %s)" % (cluster['title'], cluster['hazard_type']),
        "Deterministic risk score: %.1f/100 (status: %s) over %d grid cells." % (
            cluster['risk_score'], cluster['status'], cluster['cell_count']),
        "",
        "Sources:",
    ]
    for source in sources:
        lines.append("- id=%s | %s from %s | valid %s to %s | %s" % (
            source['id'], source.get('kind'), source.get('sender'),
            source.get('effective_at') or 'unstated',
            source.get('expires_at') or 'unstated',
            (source.get('text') or '')[:400]))
    if sop_chunks:
        lines.append("")
        lines.append("Relevant SOP passages (cite by id if the recommended action draws on one):")
        for chunk in sop_chunks:
            lines.append("- id=%s | %s | %s" % (chunk['id'], chunk['source'], chunk['text'][:400]))
    return "\n".join(lines)


def _sop_citations(cluster):
    """Up to 4 corpus passages relevant to this event, as citation-shaped

    dicts (same shape `_citation()` produces for alerts/reports) so the
    review UI needs no special case for a SOP source. `[]` when the corpus is
    empty - see rag.py's own docstring on why that is the fully-supported
    default, not degraded behaviour.
    """
    from . import rag
    query = '%s %s' % (cluster.get('title') or '', cluster.get('hazard_type') or '')
    chunks = rag.retrieve(query, top_k=4)
    out = []
    for i, chunk in enumerate(chunks):
        out.append({
            'id': 'sop-%d' % i, 'kind': 'sop', 'sender': None,
            'title': chunk['source'], 'url': None, 'effective_at': None,
            'text': chunk['text'],
        })
    return out


def _offline_brief(cluster, sources, city, sop_chunks=None):
    """A template brief, written when no model is available.

    Marked `generated_offline` everywhere it surfaces. It states only facts
    already in the database - no interpretation - because a template that
    editorialises would be worse than no brief at all.
    """
    sop_chunks = sop_chunks or []
    senders = sorted({s.get('sender') for s in sources if s.get('sender')})
    official = [s for s in sources if s['kind'] == 'official_alert']
    reports = [s for s in sources if s['kind'] == 'citizen_report']

    body = [
        "**%s**" % cluster['title'],
        "",
        "- Deterministic risk score **%.1f/100** (%s) across **%d** grid cells."
        % (cluster['risk_score'], cluster['status'], cluster['cell_count']),
        "- Evidence: %d official alert(s), %d verified citizen report(s)."
        % (len(official), len(reports)),
    ]
    if senders:
        body.append("- Issued by: %s." % ", ".join(senders))
    if sop_chunks:
        body.append("- Related SOP passage(s): %s." %
                    ", ".join(sorted({c['title'] for c in sop_chunks})))
    body.append("")
    body.append("_No language model was available, so this brief is generated from "
                "database fields only and carries no interpretation._")

    return {
        'cluster_key': _cluster_key(city, cluster),
        'title': cluster['title'],
        'hazard_type': cluster['hazard_type'],
        'severity': cluster['status'],
        'risk_score': cluster['risk_score'],
        'h3_index': cluster.get('worst_cell'),
        'cells': cluster.get('cells') or [],
        'brief_md': "\n".join(body),
        'citations': [_citation(s) for s in sources] + sop_chunks,
        'generated_offline': True,
    }


def _citation(source):
    return {
        'id': source['id'],
        'kind': source.get('kind'),
        'sender': source.get('sender'),
        'title': source.get('title'),
        'url': source.get('url'),
        'effective_at': source.get('effective_at'),
    }


def _cluster_key(city, cluster):
    """A stable identity for a cluster, so re-running triage updates the same
    flag rather than filing a duplicate every poll."""
    digest = hashlib.sha1(
        ('%s|%s|%s' % (city.slug, cluster['hazard_type'],
                       '|'.join(sorted(cluster['item_ids'])))).encode('utf-8')
    ).hexdigest()[:16]
    return '%s-%s-%s' % (city.slug, cluster['hazard_type'], digest)


# --- 9. human gate ---------------------------------------------------------
def make_persist_flags(ctx):
    def persist_flags(state):
        """Write the briefs as `pending` flags. This IS the gate.

        Nothing here is visible on an operator's map. A flag becomes visible
        only when a human POSTs a decision to /api/twin/flags/<id>, which
        mirrors the `verification_status` gate the host app already applies to
        citizen reports.
        """
        models = ctx.models
        written = []
        for brief in state.get('briefs', []):
            flag = models.TwinFlag.query.filter_by(cluster_key=brief['cluster_key']).first()
            if flag is None:
                flag = models.TwinFlag(cluster_key=brief['cluster_key'])
                ctx.db.session.add(flag)
            elif flag.status != 'pending':
                # Already decided by a human. Re-running triage must never
                # silently resurrect something an admin rejected.
                continue

            flag.city_id = ctx.city.id
            flag.h3_index = brief.get('h3_index')
            flag.title = brief['title'][:240] if brief.get('title') else None
            flag.hazard_type = brief.get('hazard_type')
            flag.severity = brief.get('severity')
            flag.risk_score = brief.get('risk_score') or 0.0
            flag.brief_md = brief.get('brief_md')
            flag.citations_json = json.dumps(brief.get('citations') or [],
                                             separators=(',', ':'))
            flag.generated_offline = bool(brief.get('generated_offline'))
            flag.status = 'pending'
            ctx.db.session.flush()  # flag.id is needed below on the first save

            # Replace rather than accumulate: a re-run's cluster membership can
            # shrink (an item aged out of the window) as well as grow, and
            # dispatch must compute its blast radius from the current
            # footprint, not every footprint this cluster_key has ever had.
            models.TwinFlagCell.query.filter_by(flag_id=flag.id).delete(synchronize_session=False)
            for h3_index in brief.get('cells') or []:
                ctx.db.session.add(models.TwinFlagCell(flag_id=flag.id, h3_index=h3_index))

            written.append(brief['cluster_key'])

        ctx.db.session.commit()

        if written:
            from ..stream import publish
            publish(ctx.city.slug, 'state', {
                'city': ctx.city.slug,
                'reason': 'flags_pending',
                'count': len(written),
            })
        return {'approved': [], 'flagged_keys': written}
    return persist_flags


def _iso(value):
    return value.isoformat() + 'Z' if value else None
