"""Idempotent seeding: cities, zones, the H3 grid, and the static terrain and
infrastructure inputs that feed the vulnerability half of the risk score.

Everything here is safe to re-run. Re-running after changing
`TWIN_H3_RESOLUTION` or `TWIN_GRID_RINGS` rebuilds the grid; re-running with the
same settings is close to a no-op.
"""

import json
import math
from datetime import datetime

from . import config as twin_config
from .geo import haversine_m
from .grid import (cell_for_point, dumps_ring, generate_cells, grid_bbox,
                   nearest_zone, zone_hull_geojson)
from .ingest.base import record_snapshot
from .ingest.open_meteo import fetch_elevations
from .ingest.overpass import AssetsAdapter, CameraAdapter, WaterAdapter

# Bin size for the water proximity index, in degrees (~2.2 km). Must exceed the
# WATER_PROXIMITY_MAX_M cap so a 3x3 bin scan can never miss a closer feature.
_BIN_DEG = 0.02


def seed_cities(db, models):
    """Upsert TwinCity/TwinZone rows from config. Returns the city rows."""
    cities = []
    for cfg in twin_config.CITIES:
        city = models.TwinCity.query.filter_by(slug=cfg['slug']).first()
        if city is None:
            city = models.TwinCity(slug=cfg['slug'])
            db.session.add(city)
        city.name = cfg['name']
        city.state = cfg.get('state')
        city.center_latitude = cfg['center_latitude']
        city.center_longitude = cfg['center_longitude']
        city.default_zoom = cfg.get('default_zoom', 10.6)
        city.default_pitch = cfg.get('default_pitch', 45.0)
        city.default_bearing = cfg.get('default_bearing', -12.5)
        city.h3_resolution = twin_config.H3_RESOLUTION
        db.session.flush()

        for slug, name, lat, lon in cfg.get('zones', []):
            zone = models.TwinZone.query.filter_by(city_id=city.id, slug=slug).first()
            if zone is None:
                zone = models.TwinZone(city_id=city.id, slug=slug)
                db.session.add(zone)
            zone.name = name
            zone.center_latitude = lat
            zone.center_longitude = lon
            zone.boundary_source = 'approximate'
        cities.append(city)

    db.session.commit()
    return cities


def seed_grid(db, models, city, rebuild=False):
    """Build (or rebuild) the H3 grid for one city.

    Existing cells are matched by h3_index and updated in place so their
    accumulated terrain data and state rows survive a re-seed.
    """
    cfg = twin_config.CITIES_BY_SLUG[city.slug]
    generated = generate_cells(cfg, resolution=city.h3_resolution)

    bbox = grid_bbox(generated)
    city.bbox_min_lon, city.bbox_min_lat, city.bbox_max_lon, city.bbox_max_lat = bbox

    zones = list(city.zones)
    existing = {c.h3_index: c for c in city.cells}

    if rebuild:
        wanted = {g['h3'] for g in generated}
        for index, cell in existing.items():
            if index not in wanted:
                db.session.delete(cell)

    created = 0
    for item in generated:
        cell = existing.get(item['h3'])
        if cell is None:
            cell = models.TwinCell(h3_index=item['h3'], city_id=city.id)
            db.session.add(cell)
            created += 1
        cell.center_latitude = item['lat']
        cell.center_longitude = item['lon']
        cell.boundary_geojson = dumps_ring(item['ring'])
        cell.area_km2 = item['area_km2']
        zone = nearest_zone(item['lat'], item['lon'], zones)
        cell.zone_id = zone.id if zone else None

    db.session.commit()

    # Now that every cell has a zone, give each zone a boundary unioned from its
    # own cells. Still 'approximate' - it is the hull of a nearest-centre
    # partition, not a surveyed ward - and the UI says so.
    for zone in zones:
        hull = zone_hull_geojson(list(zone.cells))
        zone.boundary_geojson = json.dumps(hull, separators=(',', ':')) if hull else None
    db.session.commit()

    return {'cells': len(generated), 'created': created, 'bbox': bbox}


def seed_elevation(db, models, city, force=False):
    """Fill TwinCell.elevation_m from Open-Meteo's terrain model."""
    cells = list(city.cells)
    pending = cells if force else [c for c in cells if c.elevation_m is None]
    if not pending:
        return {'updated': 0, 'status': 'skipped'}

    points = [(c.h3_index, c.center_latitude, c.center_longitude) for c in pending]
    values, results = fetch_elevations(points, force=force)
    for result in results:
        record_snapshot(db, models, city.id, result)

    updated = 0
    for cell in pending:
        value = values.get(cell.h3_index)
        if value is not None:
            cell.elevation_m = float(value)
            updated += 1
    db.session.commit()

    # Status reports the *outcome*, not the attempt list: a primary that 429s
    # and a fallback that answers is a success, and calling it degraded trains
    # operators to ignore the health pill.
    missing = len(pending) - updated
    providers_used = sorted({r.source_key for r in results if r.ok})
    first_error = next((r.error for r in results if not r.ok and r.error), None)
    return {
        'updated': updated,
        'missing': missing,
        'status': 'ok' if missing == 0 else ('degraded' if updated else 'failed'),
        'providers': providers_used,
        'error': _short(first_error) if missing else None,
    }


def _short(text, limit=160):
    if not text:
        return None
    text = ' '.join(str(text).split())
    return text if len(text) <= limit else text[:limit] + '...'


def seed_water(db, models, city, force=False):
    """Derive dist_to_water_m and drain_length_m per cell from OSM hydrology."""
    result = WaterAdapter().run(bbox=city.bbox, force=force)
    record_snapshot(db, models, city.id, result)
    if not result.ok:
        db.session.commit()
        return {'status': result.status, 'error': result.error}

    data = result.data
    index = _build_water_index(data)

    # Drain length is accumulated per cell by walking each segment and charging
    # its length to the cell its midpoint falls in. Splitting by midpoint keeps
    # a 2 km drain from being credited entirely to whichever cell holds its
    # first vertex.
    drain_by_cell = {}
    for drain in data.get('drains', []):
        line = drain.get('line') or []
        for a, b in zip(line, line[1:]):
            length = haversine_m(a[1], a[0], b[1], b[0])
            mid_lat = (a[1] + b[1]) / 2.0
            mid_lon = (a[0] + b[0]) / 2.0
            key = cell_for_point(mid_lat, mid_lon, city.h3_resolution)
            drain_by_cell[key] = drain_by_cell.get(key, 0.0) + length

    touched = 0
    for cell in city.cells:
        cell.drain_length_m = drain_by_cell.get(cell.h3_index, 0.0)
        cell.dist_to_water_m = _nearest_water_m(index, cell.center_latitude,
                                                cell.center_longitude)
        touched += 1
    db.session.commit()
    return {
        'status': result.status,
        'cells': touched,
        'bodies': len(data.get('bodies', [])),
        'drains': len(data.get('drains', [])),
        'channels': len(data.get('channels', [])),
    }


def _build_water_index(data):
    """Bin every water vertex into a coarse lat/lon grid.

    A linear scan of ~100k vertices for each of 919 cells is 90M haversines.
    Binning at 0.02 degrees turns that into a 3x3 bin lookup per cell.
    """
    bins = {}
    def add(lat, lon):
        key = (int(math.floor(lat / _BIN_DEG)), int(math.floor(lon / _BIN_DEG)))
        bins.setdefault(key, []).append((lat, lon))

    for body in data.get('bodies', []):
        for lon, lat in body.get('ring', []):
            add(lat, lon)
    for channel in data.get('channels', []):
        for lon, lat in channel.get('line', []):
            add(lat, lon)
    return bins


def _nearest_water_m(bins, lat, lon):
    if not bins:
        return None
    row = int(math.floor(lat / _BIN_DEG))
    col = int(math.floor(lon / _BIN_DEG))
    best = None
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            for (plat, plon) in bins.get((row + dr, col + dc), ()):
                d = haversine_m(lat, lon, plat, plon)
                if best is None or d < best:
                    best = d
    # Nothing within ~2 km of this cell: report the cap rather than None, which
    # would be read as "unknown" and score a neutral 50.
    return best if best is not None else 2200.0


def seed_assets(db, models, city, force=False):
    """Replace this city's TwinInfrastructure rows from OSM."""
    result = AssetsAdapter().run(bbox=city.bbox, force=force)
    record_snapshot(db, models, city.id, result)
    if not result.ok:
        db.session.commit()
        return {'status': result.status, 'error': result.error}

    cells_by_h3 = {c.h3_index: c for c in city.cells}
    models.TwinInfrastructure.query.filter_by(city_id=city.id).delete()

    kept = 0
    for asset in result.data:
        key = cell_for_point(asset['lat'], asset['lon'], city.h3_resolution)
        cell = cells_by_h3.get(key)
        if cell is None:
            continue  # inside the bbox but outside the hex disk
        db.session.add(models.TwinInfrastructure(
            city_id=city.id,
            cell_id=cell.id,
            osm_id=asset['osm_id'],
            asset_type=asset['asset_type'],
            name=(asset.get('name') or None),
            criticality=asset['criticality'],
            latitude=asset['lat'],
            longitude=asset['lon'],
            updated_at=datetime.utcnow(),
        ))
        kept += 1
    db.session.commit()
    return {'status': result.status, 'assets': kept, 'fetched': len(result.data)}


def seed_cameras(db, models, city, force=False):
    """Count OSM surveillance cameras per cell.

    Surveillance coverage is an operational question - 'which critical cells
    have no camera at all' - so it is stored on the cell rather than recomputed
    client-side. The counts are of *mapped* cameras and nothing else; sparse
    coverage in a city means OSM is sparse there, and is never padded.
    """
    result = CameraAdapter().run(bbox=city.bbox, force=force)
    record_snapshot(db, models, city.id, result)
    if not result.ok:
        db.session.commit()
        return {'status': result.status, 'error': result.error}

    counts = {}
    for camera in result.data:
        key = cell_for_point(camera['lat'], camera['lon'], city.h3_resolution)
        counts[key] = counts.get(key, 0) + 1

    for cell in city.cells:
        cell.camera_count = counts.get(cell.h3_index, 0)
    db.session.commit()
    return {'status': result.status, 'cameras': len(result.data),
            'covered_cells': sum(1 for v in counts.values() if v)}


def seed_all(db, models, rebuild=False, skip_slow=False):
    """Full seed. `skip_slow` omits the Overpass passes (minutes on a cold cache)."""
    report = {}
    for city in seed_cities(db, models):
        entry = {'grid': seed_grid(db, models, city, rebuild=rebuild)}
        entry['elevation'] = seed_elevation(db, models, city)
        if not skip_slow:
            entry['water'] = seed_water(db, models, city)
            entry['assets'] = seed_assets(db, models, city)
            entry['cameras'] = seed_cameras(db, models, city)
        report[city.slug] = entry
    return report
