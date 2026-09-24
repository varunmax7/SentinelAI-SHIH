"""Poll live stations + transit, upsert `twin_observation`, apply staleness.

Mirrors `alerts.py`'s shape (poll -> reconcile -> commit) for the same
reason: this is the layer that turns "OpenAQ has a reading" into "cell X's
env score can use it", and it needs the identical idempotence guarantee -
re-polling must update existing rows, not accumulate duplicates.
"""

from datetime import datetime, timedelta, timezone

from . import config as twin_config
from .geo import haversine_m
from .ingest.base import record_snapshot
from .ingest.stations import AqicnAdapter, CpcbAdapter, OpenAQAdapter
from .ingest.transit import TransitAdapter

STATION_SEARCH_RADIUS_M = 25000


def poll_stations(db, models, city):
    """Every configured AQ station source, for one city."""
    results = []
    written = 0

    openaq = OpenAQAdapter().run(lat=city.center_latitude, lon=city.center_longitude,
                                 radius_m=STATION_SEARCH_RADIUS_M)
    results.append(openaq)
    written += _upsert(db, models, city, 'openaq', 'air_quality', openaq.data, _station_fields)

    aqicn = AqicnAdapter().run(city_name=city.slug)
    results.append(aqicn)
    written += _upsert(db, models, city, 'aqicn', 'air_quality', aqicn.data, _station_fields)

    cpcb = CpcbAdapter().run(state_name=city.state)
    results.append(cpcb)
    written += _upsert(db, models, city, 'cpcb', 'air_quality', cpcb.data, _station_fields)

    for result in results:
        record_snapshot(db, models, city.id, result)
    db.session.commit()
    return {'written': written, 'sources': [r.to_dict() for r in results]}


def poll_transit(db, models, city):
    result = TransitAdapter().run(city_slug=city.slug)
    record_snapshot(db, models, city.id, result)
    written = _upsert(db, models, city, 'gtfs_rt', 'transit_vehicle', result.data, _vehicle_fields)
    dropped = _drop_stale_vehicles(db, models, city)
    db.session.commit()
    return {'written': written, 'dropped_stale': dropped, 'source': result.to_dict()}


def poll_all(db, models):
    stations = {}
    transit = {}
    for city in models.TwinCity.query.all():
        try:
            stations[city.slug] = poll_stations(db, models, city)
        except Exception as exc:  # noqa: BLE001 - one city must not stop the other
            db.session.rollback()
            stations[city.slug] = {'error': '%s: %s' % (type(exc).__name__, exc)}
        try:
            transit[city.slug] = poll_transit(db, models, city)
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            transit[city.slug] = {'error': '%s: %s' % (type(exc).__name__, exc)}
    return {'stations': stations, 'transit': transit}


# --- upsert --------------------------------------------------------------------
def _station_fields(obs, row):
    obs.name = row.get('name')
    obs.latitude = row.get('lat')
    obs.longitude = row.get('lon')
    obs.aqi = row.get('aqi')
    obs.pm2_5 = row.get('pm2_5')
    obs.observed_at = _parse_time(row.get('observed_at'))


def _vehicle_fields(obs, row):
    obs.latitude = row.get('lat')
    obs.longitude = row.get('lon')
    obs.route_id = row.get('route_id')
    obs.speed_kmh = row.get('speed_kmh')
    obs.stalled = bool(row.get('stalled'))
    obs.observed_at = _parse_gtfs_timestamp(row.get('observed_at'))


def _upsert(db, models, city, source, kind, rows, apply_fields):
    if not rows:
        return 0
    written = 0
    for row in rows:
        external_id = row.get('external_id')
        if not external_id:
            continue
        obs = (models.TwinObservation.query
               .filter_by(city_id=city.id, source=source, external_id=external_id)
               .first())
        if obs is None:
            obs = models.TwinObservation(city_id=city.id, source=source,
                                         external_id=external_id, kind=kind)
            db.session.add(obs)
        apply_fields(obs, row)
        obs.fetched_at = datetime.utcnow()
        written += 1
    return written


def _drop_stale_vehicles(db, models, city):
    """A vehicle silent past this age is gone, not stalled - shown frozen on

    the map would be actively misleading, so it is deleted rather than kept
    and marked stale the way a station reading is.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=twin_config.TRANSIT_VEHICLE_MAX_AGE_MIN)
    return (models.TwinObservation.query
            .filter(models.TwinObservation.city_id == city.id,
                    models.TwinObservation.kind == 'transit_vehicle',
                    models.TwinObservation.observed_at < cutoff)
            .delete(synchronize_session=False))


# --- reads -----------------------------------------------------------------------
def live_stations(models, city, now=None):
    """Every air-quality station for a city, each carrying `stale` -

    `observed_at` older than `TWIN_STATION_STALE_MIN` - so the UI can show an
    old number as what it is rather than silently dropping it.
    """
    now = now or datetime.utcnow()
    cutoff = now - timedelta(minutes=twin_config.STATION_STALE_MIN)
    rows = (models.TwinObservation.query
            .filter_by(city_id=city.id, kind='air_quality').all())
    out = []
    for row in rows:
        out.append({
            'source': row.source, 'external_id': row.external_id, 'name': row.name,
            'lat': row.latitude, 'lon': row.longitude,
            'aqi': row.aqi, 'pm2_5': row.pm2_5,
            'observed_at': row.observed_at.isoformat() + 'Z' if row.observed_at else None,
            'stale': row.observed_at is None or row.observed_at < cutoff,
        })
    return out


def live_vehicles(models, city):
    rows = (models.TwinObservation.query
            .filter_by(city_id=city.id, kind='transit_vehicle').all())
    return [{
        'external_id': row.external_id, 'route_id': row.route_id,
        'lat': row.latitude, 'lon': row.longitude,
        'speed_kmh': row.speed_kmh, 'stalled': bool(row.stalled),
        'observed_at': row.observed_at.isoformat() + 'Z' if row.observed_at else None,
    } for row in rows]


def station_aqi_near(models, city, lat, lon, radius_m=None, now=None):
    """The nearest non-stale station's AQI within `radius_m`, or None.

    Called from `engine.py` per cell - cheap in practice, since real-world
    station and vehicle counts near either city are small (often zero; see
    the module docstring on why these sources are untested).
    """
    radius_m = radius_m or STATION_SEARCH_RADIUS_M
    for station in live_stations(models, city, now=now):
        if station['stale'] or station['aqi'] is None or station['lat'] is None:
            continue
        if haversine_m(lat, lon, station['lat'], station['lon']) <= radius_m:
            return station['aqi']
    return None


def disruption_sub_score(models, city, lat, lon, radius_m=1500):
    """0-100: the share of nearby transit vehicles currently stalled.

    None (not 0.0) when there are no vehicles nearby to judge from - "no
    disruption measured" must stay distinct from "measured as calm", the
    same rule every other sub-score in this app follows.
    """
    nearby = [v for v in live_vehicles(models, city)
             if v['lat'] is not None
             and haversine_m(lat, lon, v['lat'], v['lon']) <= radius_m]
    if not nearby:
        return None
    stalled = sum(1 for v in nearby if v['stalled'])
    return round(100.0 * stalled / len(nearby), 1)


# --- parsing -----------------------------------------------------------------------
def _parse_time(value):
    """OpenAQ reports UTC ('...Z'); AQICN reports local time with a real

    offset ('...+05:30'). Both have to be CONVERTED to UTC before the
    timezone is dropped - naively stripping tzinfo on an IST timestamp
    silently keeps the 17:00 wall-clock number and calls it 17:00 UTC,
    5.5 hours wrong. Caught by inspecting a real AQICN response, not found
    in testing beforehand (there was no key to test AQICN's specific format
    against until this key was provided).
    """
    if not value:
        return None
    text = str(value).replace('Z', '+00:00')
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _parse_gtfs_timestamp(value):
    if not value:
        return None
    try:
        return datetime.utcfromtimestamp(int(value))
    except (TypeError, ValueError, OSError):
        return None
