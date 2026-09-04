"""The compute pass: ingest -> score -> persist -> publish.

One `compute_city()` call refreshes every cell at every horizon for one city.
It is the only place that writes `TwinCellState`, and it is deliberately a
single function you can read top to bottom: the value of a digital twin is that
an operator can be told exactly why a hexagon is red, and that is only true if
the path from raw input to score is short enough to follow.
"""

import json
from datetime import datetime, timedelta

from . import config as twin_config
from . import scoring
from .grid import k_ring_neighbours
from .ingest.base import record_snapshot
from .ingest.internal_reports import collect_incidents
from .ingest.open_meteo import (AirQualityAdapter, FloodAdapter,
                                ForecastAdapter, sample_cells)
from .stream import publish

# How often a history row is appended per cell. The compute pass runs every
# 5 minutes; writing 7k history rows that often would grow the table by ~2M rows
# a day for no analytical gain.
HISTORY_INTERVAL_MINUTES = 30


def compute_city(db, models, city, Report, force=False):
    """Recompute every cell of `city` at every horizon. Returns a summary dict."""
    started = datetime.utcnow()
    cells = list(city.cells)
    if not cells:
        return {'city': city.slug, 'cells': 0, 'error': 'grid not seeded'}

    h3_indexes = [c.h3_index for c in cells]
    sample_by_cell, points = sample_cells(h3_indexes)

    forecast = ForecastAdapter().run(points=points, force=force)
    air_quality = AirQualityAdapter().run(points=points, force=force)
    flood = FloodAdapter().run(latitude=city.center_latitude,
                               longitude=city.center_longitude, force=force)

    for result in (forecast, air_quality, flood):
        record_snapshot(db, models, city.id, result)

    incidents_by_cell, incident_pins = collect_incidents(
        Report, city.bbox, resolution=city.h3_resolution, now=started)

    # Elevation range across this city, for the relative low-lying score.
    elevations = [c.elevation_m for c in cells if c.elevation_m is not None]
    elev_min = min(elevations) if elevations else None
    elev_max = max(elevations) if elevations else None

    # Criticality summed per cell, in one query rather than 919.
    criticality = _criticality_by_cell(db, models, city)

    # Incident load is needed for a cell's neighbours as well as itself, so
    # compute every cell's own load once up front.
    own_load = {index: scoring.incident_load(reports, started)
                for index, reports in incidents_by_cell.items()}

    discharge = (flood.data or {}).get('anomaly_score') or 0.0
    degraded_sources = [r.source_key for r in (forecast, air_quality, flood) if r.degraded]

    existing = _existing_states(models, cells)
    write_history = _should_write_history(models, city, started)

    counts = {'normal': 0, 'watch': 0, 'warning': 0, 'critical': 0}
    max_risk = 0.0
    risk_total = 0.0
    now_states = 0

    for cell in cells:
        sample_key = sample_by_cell.get(cell.h3_index)
        weather = (forecast.data or {}).get(sample_key) or {}
        air = (air_quality.data or {}).get(sample_key) or {}

        neighbour_load = sum(own_load.get(n, 0.0)
                             for n in k_ring_neighbours(cell.h3_index, 1))
        cell_load = own_load.get(cell.h3_index, 0.0)

        low_lying = scoring.low_lying_score(cell.elevation_m, elev_min, elev_max)
        water_proximity = scoring.water_proximity_score(cell.dist_to_water_m)
        drain_gap = scoring.drain_gap_score(cell.drain_length_m, cell.area_km2)
        terrain = scoring.terrain_sub_score(low_lying, water_proximity, drain_gap)
        infra = scoring.infra_sub_score(criticality.get(cell.id, 0))
        incident = scoring.incident_sub_score(cell_load, neighbour_load)
        env = scoring.env_sub_score(air.get('aqi'), weather.get('temperature_c'))

        rain_forecast = weather.get('rain_forecast_mm') or {}

        for horizon in twin_config.HORIZONS:
            hydro = scoring.hydro_sub_score(
                weather.get('rain_now_mm_h'),
                rain_forecast.get(str(horizon)),
                discharge,
                horizon,
            )
            risk, status, vulnerability = scoring.compose(
                hydro, incident, env, terrain, infra)

            state = existing.get((cell.id, horizon))
            if state is None:
                state = models.TwinCellState(cell_id=cell.id, horizon_hours=horizon)
                db.session.add(state)
                existing[(cell.id, horizon)] = state

            state.risk_score = round(risk, 2)
            state.status = status
            state.hydro_score = round(hydro, 2)
            state.incident_score = round(incident, 2)
            state.env_score = round(env, 2)
            state.terrain_score = round(terrain, 2)
            state.infra_score = round(infra, 2)
            state.degraded_inputs = bool(degraded_sources)
            state.computed_at = started
            state.raw_inputs = json.dumps({
                'sample_cell': sample_key,
                'rain_now_mm_h': weather.get('rain_now_mm_h'),
                'rain_forecast_mm': rain_forecast.get(str(horizon)),
                'temperature_c': weather.get('temperature_c'),
                'humidity': weather.get('humidity'),
                'wind_speed_kmh': weather.get('wind_speed_kmh'),
                'aqi': air.get('aqi'),
                'pm2_5': air.get('pm2_5'),
                'river_discharge_anomaly': discharge,
                'incident_count': len(incidents_by_cell.get(cell.h3_index, [])),
                'incident_load': round(cell_load, 4),
                'neighbour_load': round(neighbour_load, 4),
                'elevation_m': cell.elevation_m,
                'dist_to_water_m': cell.dist_to_water_m,
                'drain_length_m': cell.drain_length_m,
                'criticality_sum': criticality.get(cell.id, 0),
                'camera_count': cell.camera_count or 0,
                'vulnerability': round(vulnerability, 4),
                'degraded_sources': degraded_sources,
            }, separators=(',', ':'))

            if horizon == 0:
                counts[status] = counts.get(status, 0) + 1
                risk_total += risk
                max_risk = max(max_risk, risk)
                now_states += 1
                if write_history:
                    db.session.add(models.TwinCellHistory(
                        cell_id=cell.id, horizon_hours=0,
                        risk_score=round(risk, 2), status=status,
                        recorded_at=started))

    city.last_computed_at = started
    db.session.commit()

    summary = {
        'city': city.slug,
        'cells': len(cells),
        'horizons': list(twin_config.HORIZONS),
        'avg_risk': round(risk_total / now_states, 2) if now_states else 0.0,
        'max_risk': round(max_risk, 2),
        'status_counts': counts,
        'incidents': len(incident_pins),
        'degraded_sources': degraded_sources,
        'computed_at': started.isoformat() + 'Z',
        'duration_ms': int((datetime.utcnow() - started).total_seconds() * 1000),
    }
    publish(city.slug, 'state', summary)
    return summary


def compute_all(db, models, Report, force=False):
    out = {}
    for city in models.TwinCity.query.all():
        try:
            out[city.slug] = compute_city(db, models, city, Report, force=force)
        except Exception as exc:  # noqa: BLE001 - C1: one city must not stop the other
            db.session.rollback()
            out[city.slug] = {'city': city.slug, 'error': "%s: %s" % (type(exc).__name__, exc)}
    return out


def _criticality_by_cell(db, models, city):
    rows = (db.session.query(models.TwinInfrastructure.cell_id,
                             db.func.sum(models.TwinInfrastructure.criticality))
            .filter(models.TwinInfrastructure.city_id == city.id,
                    models.TwinInfrastructure.cell_id.isnot(None))
            .group_by(models.TwinInfrastructure.cell_id)
            .all())
    return {cell_id: float(total or 0) for cell_id, total in rows}


def _existing_states(models, cells):
    ids = [c.id for c in cells]
    out = {}
    # Chunked: SQLite caps a statement at 999 bound parameters, and a city has
    # more cells than that.
    for i in range(0, len(ids), 500):
        rows = (models.TwinCellState.query
                .filter(models.TwinCellState.cell_id.in_(ids[i:i + 500]))
                .all())
        for row in rows:
            out[(row.cell_id, row.horizon_hours)] = row
    return out


def _should_write_history(models, city, now):
    last = (models.TwinCellHistory.query
            .join(models.TwinCell, models.TwinCell.id == models.TwinCellHistory.cell_id)
            .filter(models.TwinCell.city_id == city.id)
            .order_by(models.TwinCellHistory.recorded_at.desc())
            .first())
    if last is None or last.recorded_at is None:
        return True
    return (now - last.recorded_at) >= timedelta(minutes=HISTORY_INTERVAL_MINUTES)
