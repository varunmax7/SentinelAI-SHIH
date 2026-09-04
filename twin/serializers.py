"""Model -> GeoJSON/JSON, plus caching headers.

The risk grid is the hot payload: 919 polygons x 4 horizons, refetched by every
open console every few minutes. Two things keep it cheap - `geometry=false`
lets a client that already has the hexagons ask for scores only, and an ETag
turns an unchanged grid into a 304.
"""

import gzip
import hashlib
import io
import json

from flask import Response, request

from . import scoring


def cell_feature(cell, state, geometry=True):
    properties = {
        'h3': cell.h3_index,
        'zone_id': cell.zone_id,
        'risk': round(state.risk_score or 0.0, 1) if state else 0.0,
        'status': state.status if state else 'unknown',
        'degraded': bool(state.degraded_inputs) if state else True,
        'cameras': cell.camera_count or 0,
    }
    if state:
        properties.update({
            'hydro': round(state.hydro_score or 0.0, 1),
            'incident': round(state.incident_score or 0.0, 1),
            'env': round(state.env_score or 0.0, 1),
            'terrain': round(state.terrain_score or 0.0, 1),
            'infra': round(state.infra_score or 0.0, 1),
        })

    feature = {'type': 'Feature', 'id': cell.h3_index, 'properties': properties}
    if geometry:
        ring = cell.boundary_ring()
        feature['geometry'] = {'type': 'Polygon', 'coordinates': [ring]} if ring else None
    else:
        feature['geometry'] = None
        properties['lon'] = cell.center_longitude
        properties['lat'] = cell.center_latitude
    return feature


def state_collection(pairs, geometry=True):
    """`pairs` is an iterable of (TwinCell, TwinCellState|None)."""
    return {
        'type': 'FeatureCollection',
        'features': [cell_feature(cell, state, geometry) for cell, state in pairs],
    }


def zone_collection(zones):
    features = []
    for zone in zones:
        features.append({
            'type': 'Feature',
            'id': zone.slug,
            'properties': {
                'slug': zone.slug,
                'name': zone.name,
                'boundary_source': zone.boundary_source,
                # Surfaced so the UI can label it. These are nearest-centre
                # partitions of the hex grid, not surveyed ward boundaries.
                'approximate': zone.boundary_source != 'official',
            },
            'geometry': zone.boundary(),
        })
    return {'type': 'FeatureCollection', 'features': features}


# Priority ranked so a group can report its worst member rather than an
# average - averaging one critical report with nine low ones is how a critical
# report disappears.
_PRIORITY_RANK = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}


def incidents_collection(pins):
    """Report pins, plus one group pin per H3 cell holding more than one.

    Reports cluster hard in real data - a single campus produced twenty of the
    twenty-three in this database, all inside ~200 m. Drawn as bare points they
    overlap into one dot and an operator reads "one report here". Grouping is
    done here rather than with MapLibre's `cluster: true` for two reasons: a
    clustered geojson source created during style.load silently never produces
    tiles, and the H3 cell is already the unit the operator is looking at, so a
    group pin can open that cell's drawer and list every report in it.
    """
    by_cell = {}
    for pin in pins:
        by_cell.setdefault(pin['h3'], []).append(pin)

    features = []
    for pin in pins:
        members = by_cell.get(pin['h3'], ())
        features.append({
            'type': 'Feature',
            'id': pin['id'],
            'properties': {
                'kind': 'report',
                # True when this report shares its cell with others, so the
                # client can hold it back until the operator is zoomed in far
                # enough for the individual pins to separate.
                'grouped': len(members) > 1,
                'id': pin['id'],
                'title': pin['title'],
                'hazard_type': pin['hazard_type'],
                'status': pin['status'],
                'priority': pin['priority'],
                'confidence': round(pin['confidence'], 3),
                'location': pin['location'],
                'h3': pin['h3'],
                'timestamp': pin['timestamp'].isoformat() + 'Z' if pin.get('timestamp') else None,
            },
            'geometry': {'type': 'Point', 'coordinates': [pin['lon'], pin['lat']]},
        })

    for h3_index, members in by_cell.items():
        if len(members) < 2:
            continue
        worst = max(members, key=lambda p: _PRIORITY_RANK.get(p['priority'], 1))
        features.append({
            'type': 'Feature',
            'id': 'group-%s' % h3_index,
            'properties': {
                'kind': 'group',
                'h3': h3_index,
                'count': len(members),
                'approved': sum(1 for p in members if p['status'] == 'approved'),
                'priority': worst['priority'],
                'newest': max(
                    (p['timestamp'] for p in members if p.get('timestamp')),
                    default=None,
                ),
            },
            'geometry': {
                'type': 'Point',
                # Mean of the members: the group pin should sit where the
                # reports actually are, not at the geometric centre of a hex
                # they may all be clustered in one corner of.
                'coordinates': [
                    sum(p['lon'] for p in members) / len(members),
                    sum(p['lat'] for p in members) / len(members),
                ],
            },
        })

    for feature in features:
        newest = feature['properties'].get('newest')
        if newest is not None and not isinstance(newest, str):
            feature['properties']['newest'] = newest.isoformat() + 'Z'

    return {'type': 'FeatureCollection', 'features': features}


def infrastructure_collection(rows):
    return {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'id': row.id,
            'properties': {
                'asset_type': row.asset_type,
                'name': row.name,
                'criticality': row.criticality,
                'osm_id': row.osm_id,
            },
            'geometry': {'type': 'Point', 'coordinates': [row.longitude, row.latitude]},
        } for row in rows],
    }


def cameras_collection(cameras):
    return {
        'type': 'FeatureCollection',
        'attribution': '(c) OpenStreetMap contributors (ODbL)',
        'features': [{
            'type': 'Feature',
            'id': camera['osm_id'],
            'properties': {
                'osm_id': camera['osm_id'],
                'kind': camera.get('kind'),
                'camera_type': camera.get('camera_type'),
                'mount': camera.get('mount'),
                # None means OSM records no bearing. The client must draw a bare
                # dot for these, never a north-facing cone.
                'direction': camera.get('direction'),
                'operator': camera.get('operator'),
                'zone': camera.get('zone'),
                'stream_url': camera.get('stream_url'),
                'osm_url': camera.get('osm_url'),
            },
            'geometry': {'type': 'Point', 'coordinates': [camera['lon'], camera['lat']]},
        } for camera in cameras],
    }


def water_collection(data):
    """Water bodies as polygons, drains and channels as lines, in one payload."""
    features = []
    for body in data.get('bodies', []):
        features.append({
            'type': 'Feature',
            'properties': {'kind': 'water_body', 'name': body.get('name')},
            'geometry': {'type': 'Polygon', 'coordinates': [body['ring']]},
        })
    for channel in data.get('channels', []):
        features.append({
            'type': 'Feature',
            'properties': {'kind': channel.get('kind') or 'channel', 'name': channel.get('name')},
            'geometry': {'type': 'LineString', 'coordinates': channel['line']},
        })
    for drain in data.get('drains', []):
        features.append({
            'type': 'Feature',
            'properties': {'kind': 'drain'},
            'geometry': {'type': 'LineString', 'coordinates': drain['line']},
        })
    return {
        'type': 'FeatureCollection',
        'attribution': '(c) OpenStreetMap contributors (ODbL)',
        'features': features,
    }


def cell_detail(cell, states, assets, reports, zone=None):
    """Everything the drill-down drawer needs for one cell."""
    by_horizon = {}
    for state in states:
        inputs = state.inputs()
        by_horizon[str(state.horizon_hours)] = {
            'horizon_hours': state.horizon_hours,
            'risk': round(state.risk_score or 0.0, 1),
            'status': state.status,
            'degraded': bool(state.degraded_inputs),
            'sub_scores': {
                'hydro': round(state.hydro_score or 0.0, 1),
                'incident': round(state.incident_score or 0.0, 1),
                'env': round(state.env_score or 0.0, 1),
                'terrain': round(state.terrain_score or 0.0, 1),
                'infra': round(state.infra_score or 0.0, 1),
            },
            'inputs': inputs,
            'explanation': scoring.explain(
                inputs,
                {'hydro': state.hydro_score or 0.0,
                 'incident': state.incident_score or 0.0,
                 'env': state.env_score or 0.0,
                 'terrain': state.terrain_score or 0.0,
                 'infra': state.infra_score or 0.0},
                state.risk_score or 0.0,
                (inputs.get('vulnerability') or 1.0),
            ),
            'computed_at': state.computed_at.isoformat() + 'Z' if state.computed_at else None,
        }

    return {
        'h3': cell.h3_index,
        'center': [cell.center_longitude, cell.center_latitude],
        'area_km2': round(cell.area_km2 or 0.0, 3),
        'zone': {'slug': zone.slug, 'name': zone.name,
                 'boundary_source': zone.boundary_source} if zone else None,
        'terrain': {
            'elevation_m': cell.elevation_m,
            'dist_to_water_m': round(cell.dist_to_water_m, 1) if cell.dist_to_water_m is not None else None,
            'drain_length_m': round(cell.drain_length_m or 0.0, 1),
        },
        'surveillance': {
            'camera_count': cell.camera_count or 0,
            'source': 'OpenStreetMap man_made=surveillance (mapped cameras only)',
        },
        'horizons': by_horizon,
        'assets': [{
            'asset_type': a.asset_type, 'name': a.name, 'criticality': a.criticality,
            'lat': a.latitude, 'lon': a.longitude, 'osm_id': a.osm_id,
        } for a in assets],
        'reports': [{
            'id': r['id'], 'title': r['title'], 'hazard_type': r['hazard_type'],
            'status': r['status'], 'priority': r['priority'],
            'confidence': round(r['confidence'], 3),
            'timestamp': r['timestamp'].isoformat() + 'Z' if r.get('timestamp') else None,
        } for r in reports],
    }


# --- transport -------------------------------------------------------------
GZIP_THRESHOLD_BYTES = 8 * 1024


def json_response(payload, max_age=0, etag=True):
    """Serialise once, then ETag and gzip that exact byte string.

    Hashing the serialised bytes rather than the object is what makes the ETag
    trustworthy - two dicts that differ only in key order must not produce
    different tags, and two that differ in a float must not collide.
    """
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')

    headers = {'Content-Type': 'application/json'}
    if max_age:
        headers['Cache-Control'] = 'private, max-age=%d' % max_age
    else:
        headers['Cache-Control'] = 'no-cache'

    tag = None
    if etag:
        tag = '"%s"' % hashlib.md5(body).hexdigest()
        headers['ETag'] = tag
        if request.headers.get('If-None-Match') == tag:
            return Response(status=304, headers=headers)

    if len(body) >= GZIP_THRESHOLD_BYTES and 'gzip' in (request.headers.get('Accept-Encoding') or ''):
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=6) as handle:
            handle.write(body)
        body = buffer.getvalue()
        headers['Content-Encoding'] = 'gzip'
        headers['Vary'] = 'Accept-Encoding'

    headers['Content-Length'] = str(len(body))
    return Response(body, headers=headers)
