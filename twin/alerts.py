"""External alert ingest: feed -> alert row -> grid cells -> incident score.

This is the layer that turns "IMD issued a thunderstorm warning for Bengaluru
Urban" into "these 340 hexagons carry a medium-priority, 0.5-confidence hazard
contribution until 23:06 IST".

Two invariants run through it:

  * **Idempotence.** Re-polling a feed must create zero new rows. Every alert is
    keyed on (source, source_uid), and a CAP `msgType=Update` supersedes the
    alert it references rather than adding beside it.
  * **Expiry is authoritative.** `cap:expires` ends a contribution. A warning
    that keeps a ward amber after it has lapsed is worse than no warning,
    because it teaches operators to ignore the colour.
"""

import json
from datetime import datetime

import h3

from . import config as twin_config
from .ingest.base import record_snapshot
from .ingest.global_events import GdacsAdapter, UsgsQuakeAdapter
from .ingest.sachet import (SachetCapAdapter, SachetFeedAdapter,
                            SachetPolygonAdapter)


def poll_alerts(db, models, force=False):
    """Fetch every configured feed and reconcile it into the database."""
    cities = models.TwinCity.query.all()
    if not cities:
        return {'error': 'no cities seeded'}

    summary = {'sachet': {}, 'gdacs': {}, 'usgs': {}}
    cell_index = {city.id: {c.h3_index for c in city.cells} for city in cities}

    for state in twin_config.SACHET_STATES:
        summary['sachet'][state] = _poll_sachet_state(
            db, models, cities, cell_index, state, force=force)

    if twin_config.GLOBAL_FEEDS_ENABLED:
        summary['gdacs'] = _poll_point_feed(
            db, models, cities, cell_index, GdacsAdapter(), 'gdacs', force=force)
        summary['usgs'] = _poll_point_feed(
            db, models, cities, cell_index, UsgsQuakeAdapter(), 'usgs', force=force)

    db.session.commit()
    return summary


# --- SACHET ----------------------------------------------------------------
def _poll_sachet_state(db, models, cities, cell_index, state, force=False):
    feed = SachetFeedAdapter().run(state=state, force=force)
    record_snapshot(db, models, None, feed)
    if not feed.ok:
        return {'status': feed.status, 'error': feed.error}

    cap_adapter = SachetCapAdapter()
    polygon_adapter = SachetPolygonAdapter()

    created = updated = skipped = 0
    for item in feed.data:
        cap = cap_adapter.run(identifier=item['source_uid'], force=force)
        if not cap.ok or not cap.data:
            skipped += 1
            continue
        payload = dict(cap.data)
        payload['source_uid'] = item['source_uid']
        payload['raw_url'] = item.get('link')

        polygon_pairs = None
        if payload.get('polygon_url'):
            polygon = polygon_adapter.run(identifier=item['source_uid'],
                                          url=payload['polygon_url'], force=force)
            if polygon.ok and polygon.data:
                polygon_pairs = polygon.data['pairs']

        alert, is_new = _upsert_alert(db, models, 'sachet', payload, polygon_pairs)
        if alert is None:
            skipped += 1
            continue
        created += 1 if is_new else 0
        updated += 0 if is_new else 1

        _apply_supersede(db, models, alert, payload.get('references') or [])
        _resolve_cells(db, models, alert, cities, cell_index,
                       polygon_pairs=polygon_pairs,
                       district_codes=payload.get('district_codes') or [],
                       area_desc=payload.get('area_desc'))

    db.session.commit()
    return {'status': feed.status, 'items': len(feed.data),
            'created': created, 'updated': updated, 'skipped': skipped}


def _apply_supersede(db, models, alert, references):
    """A CAP Update replaces the alerts it references; it does not add to them.

    Superseded rows are kept for audit but `is_live()` excludes them, so the
    same warning is never counted twice.
    """
    if not references or (alert.msg_type or '').lower() not in ('update', 'cancel'):
        return
    (models.TwinExternalAlert.query
     .filter(models.TwinExternalAlert.cap_identifier.in_(references),
             models.TwinExternalAlert.id != alert.id)
     .update({'superseded_by_id': alert.id}, synchronize_session=False))


# --- point feeds -----------------------------------------------------------
def _poll_point_feed(db, models, cities, cell_index, adapter, source, force=False):
    result = adapter.run(force=force)
    record_snapshot(db, models, None, result)
    if not result.ok:
        return {'status': result.status, 'error': result.error}

    created = updated = 0
    considered = 0
    for row in result.data:
        # Filter to the cities before touching the database. These are global
        # feeds; a quake in Chile is not a row worth storing.
        city = _city_for_point(cities, row.get('lat'), row.get('lon'))
        if city is None:
            continue
        considered += 1
        alert, is_new = _upsert_alert(db, models, source, row, None)
        if alert is None:
            continue
        created += 1 if is_new else 0
        updated += 0 if is_new else 1
        _resolve_cells(db, models, alert, cities, cell_index,
                       point=(row['lat'], row['lon']), only_city=city)

    db.session.commit()
    return {'status': result.status, 'fetched': len(result.data),
            'in_cities': considered, 'created': created, 'updated': updated}


def _city_for_point(cities, lat, lon):
    if lat is None or lon is None:
        return None
    for city in cities:
        if city.bbox_min_lon is None:
            continue
        min_lon, min_lat, max_lon, max_lat = city.bbox
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            return city
    return None


# --- persistence -----------------------------------------------------------
def _upsert_alert(db, models, source, payload, polygon_pairs):
    """Insert or update one alert, keyed on (source, source_uid)."""
    source_uid = payload.get('source_uid')
    if not source_uid:
        return None, False

    alert = (models.TwinExternalAlert.query
             .filter_by(source=source, source_uid=str(source_uid)).first())
    is_new = alert is None
    if is_new:
        alert = models.TwinExternalAlert(source=source, source_uid=str(source_uid))
        db.session.add(alert)

    alert.cap_identifier = payload.get('cap_identifier')
    alert.sender = payload.get('sender')
    alert.event = payload.get('event')
    alert.category = payload.get('category')
    alert.severity = payload.get('severity')
    alert.certainty = payload.get('certainty')
    alert.urgency = payload.get('urgency')
    alert.status = payload.get('status')
    alert.msg_type = payload.get('msg_type')
    alert.priority = payload.get('priority') or 'low'
    alert.confidence = float(payload.get('confidence') or 0.5)
    alert.effective_at = payload.get('effective_at') or payload.get('sent_at')
    alert.expires_at = payload.get('expires_at')
    alert.headline = payload.get('headline')
    alert.description = payload.get('description')
    alert.instruction = payload.get('instruction')
    alert.area_desc = payload.get('area_desc')
    alert.raw_url = payload.get('raw_url')
    alert.fetched_at = datetime.utcnow()

    if polygon_pairs:
        alert.geometry_kind = 'polygon'
        ring = [[lon, lat] for lat, lon in polygon_pairs]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        alert.geometry_geojson = json.dumps(
            {'type': 'Polygon', 'coordinates': [ring]}, separators=(',', ':'))
    elif payload.get('lat') is not None:
        alert.geometry_kind = 'point'
        alert.geometry_geojson = json.dumps(
            {'type': 'Point', 'coordinates': [payload['lon'], payload['lat']]},
            separators=(',', ':'))
    elif alert.geometry_geojson is None:
        alert.geometry_kind = 'district'

    db.session.flush()
    return alert, is_new


def _resolve_cells(db, models, alert, cities, cell_index, polygon_pairs=None,
                   district_codes=None, area_desc=None, point=None, only_city=None):
    """Work out which grid cells an alert covers, and record them.

    A three-step fallback, most precise first. Anything that resolves to no
    cell in either city is dropped rather than stored - the twin models two
    cities, and an alert for a district it does not cover is not its business.
    """
    resolution = cities[0].h3_resolution if cities else twin_config.H3_RESOLUTION
    targets = [only_city] if only_city is not None else cities

    covered = {}

    if polygon_pairs:
        # h3 takes (lat, lng) natively, which is the order CAP publishes -
        # no conversion, and no chance of transposing it.
        try:
            cells = set(h3.polygon_to_cells(h3.LatLngPoly(polygon_pairs), res=resolution))
        except Exception:  # noqa: BLE001 - a malformed polygon degrades, never raises
            cells = set()
        for city in targets:
            hit = cells & cell_index.get(city.id, set())
            if hit:
                covered[city.id] = hit

    if not covered and point:
        index = h3.latlng_to_cell(point[0], point[1], resolution)
        for city in targets:
            if index in cell_index.get(city.id, set()):
                covered[city.id] = {index}

    if not covered and (district_codes or area_desc):
        # District-scoped, no usable polygon: the alert genuinely applies to the
        # whole district, so it covers the whole of that city's grid. Recorded
        # as geometry_kind='district' so the UI can say the footprint is coarse
        # rather than implying this precision was measured.
        haystack = (area_desc or '').lower()
        for city in targets:
            config = twin_config.CITIES_BY_SLUG.get(city.slug, {})
            code_hit = set(district_codes or ()) & set(config.get('lgd_district_codes', ()))
            name_hit = any(name in haystack for name in config.get('district_names', ()))
            if code_hit or name_hit:
                covered[city.id] = set(cell_index.get(city.id, set()))
                if alert.geometry_kind != 'polygon':
                    alert.geometry_kind = 'district'

    # Replace rather than accumulate: an Update can shrink a footprint, and
    # leaving the old cells behind would keep scoring ground the authority has
    # since cleared.
    models.TwinAlertCell.query.filter_by(alert_id=alert.id).delete(synchronize_session=False)
    for city_id, cells in covered.items():
        for index in cells:
            db.session.add(models.TwinAlertCell(
                alert_id=alert.id, city_id=city_id, h3_index=index))

    return sum(len(v) for v in covered.values())


# --- scoring ---------------------------------------------------------------
def alert_contributions(models, city, now=None):
    """Live alert contributions for one city, keyed by H3 index.

    Returns the same dict shape `scoring.incident_load` already consumes for
    citizen reports, so official alerts and citizen reports feed one sub-score
    through one code path - while staying distinguishable in the data model.
    """
    now = now or datetime.utcnow()

    rows = (models.TwinAlertCell.query
            .join(models.TwinExternalAlert,
                  models.TwinExternalAlert.id == models.TwinAlertCell.alert_id)
            .filter(models.TwinAlertCell.city_id == city.id)
            .add_entity(models.TwinExternalAlert)
            .all())

    by_cell = {}
    for cell_row, alert in rows:
        if not alert.is_live(now):
            continue
        by_cell.setdefault(cell_row.h3_index, []).append({
            'source': 'official',
            'alert_id': alert.id,
            'sender': alert.sender,
            'severity': _PRIORITY_SEVERITY.get(alert.priority, 0.5),
            'confidence': float(alert.confidence or 0.5),
            # Alerts decay from when they took effect, exactly as reports decay
            # from when they were filed.
            'timestamp': alert.effective_at or alert.fetched_at or now,
        })
    return by_cell


# Same ladder the host app's reports use, so an IMD "Severe" and an operator's
# "high" contribute identically. Provenance differs; weight does not.
_PRIORITY_SEVERITY = {'critical': 1.0, 'high': 0.8, 'medium': 0.55, 'low': 0.3}


def live_alerts(models, city, now=None):
    """Every alert currently in force for a city, newest first."""
    now = now or datetime.utcnow()
    alerts = (models.TwinExternalAlert.query
              .join(models.TwinAlertCell,
                    models.TwinAlertCell.alert_id == models.TwinExternalAlert.id)
              .filter(models.TwinAlertCell.city_id == city.id)
              .order_by(models.TwinExternalAlert.effective_at.desc())
              .distinct()
              .all())
    return [a for a in alerts if a.is_live(now)]
