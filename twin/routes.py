"""HTTP surface. Two blueprints: HTML pages and the JSON/GeoJSON API.

Both are built by a factory so every view closes over the host's `db`, the
generated twin models and the host's `Report` class - the twin never reaches
back into the application module, which is what keeps it importable and
testable on its own.
"""

import json
from datetime import datetime, timedelta

from flask import Blueprint, Response, render_template, request, stream_with_context

from . import config as twin_config
from . import aerial, engine, seed, serializers
from .geo import haversine_m
from .ingest.overpass import CameraAdapter, WaterAdapter
from .ingest.rainviewer import RainViewerAdapter
from .ingest.streetview import StreetViewAdapter
from .security import twin_access_required
from .stream import format_sse, subscribe, subscriber_count, unsubscribe

# NASA GIBS. Imagery is native to about zoom 9; MapLibre over-zooms the last
# valid tile above that rather than 404ing, which is correct behaviour and is
# surfaced in the UI as a note rather than left to look like a broken control.
GIBS_TEMPLATE = ('https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/'
                 '{layer}/default/{date}/GoogleMapsCompatible_Level9/{{z}}/{{y}}/{{x}}.jpg')
GIBS_LAYERS = {
    'viirs': 'VIIRS_SNPP_CorrectedReflectance_TrueColor',
    'modis_terra': 'MODIS_Terra_CorrectedReflectance_TrueColor',
    'modis_aqua': 'MODIS_Aqua_CorrectedReflectance_TrueColor',
}
GIBS_NATIVE_MAX_ZOOM = 9

ATTRIBUTIONS = [
    {'data': 'OpenStreetMap', 'text': '(c) OpenStreetMap contributors (ODbL)'},
    {'data': 'Esri World Imagery', 'text': '(c) Esri, Maxar, Earthstar Geographics'},
    {'data': 'OpenFreeMap', 'text': '(c) OpenMapTiles (c) OpenStreetMap contributors'},
    {'data': 'NASA GIBS', 'text': 'NASA EOSDIS GIBS'},
    {'data': 'KartaView', 'text': '(c) KartaView contributors (CC BY-SA)'},
    {'data': 'Mapillary', 'text': '(c) Mapillary contributors (CC BY-SA)'},
    {'data': 'Esri World Imagery (aerial crops)',
     'text': '(c) Esri, Maxar, Earthstar Geographics'},
    {'data': 'OpenSky Network', 'text': 'Aircraft positions (c) OpenSky Network, CC BY-SA 4.0'},
    {'data': 'EMSC', 'text': 'Seismicity (c) EMSC-CSEM (seismicportal.eu)'},
    {'data': 'NASA EONET / FIRMS', 'text': 'Natural events and thermal anomalies: NASA, open data'},
    {'data': 'GDELT', 'text': 'Geocoded news: The GDELT Project'},
    {'data': 'Windy Webcams', 'text': 'Live webcam frames via Windy Webcams API, (c) their respective operators'},
    {'data': 'RainViewer', 'text': 'RainViewer.com'},
    {'data': 'Open-Meteo', 'text': 'Open-Meteo.com (CC BY 4.0)'},
]


def build_blueprints(db, models, Report):
    pages = Blueprint('twin_pages', __name__)
    api = Blueprint('twin_api', __name__, url_prefix='/api/twin')

    # -- helpers ------------------------------------------------------------
    def get_city_or_404(slug):
        city = models.TwinCity.query.filter_by(slug=slug).first()
        if city is None:
            return None, serializers.json_response(
                {'error': 'Unknown city "%s"' % slug,
                 'known': [c.slug for c in models.TwinCity.query.all()]}, etag=False)
        return city, None

    def requested_horizon():
        try:
            value = int(request.args.get('horizon', 0))
        except (TypeError, ValueError):
            return 0
        return value if value in twin_config.HORIZONS else 0

    def zone_filter(city, cells_query):
        """Filter a cell query by ?zone=<slug>, degrading to no filter.

        A zone slug that does not resolve returns the whole city rather than an
        empty map - the zone layer is approximate by construction and must never
        be able to hide the city from an operator.
        """
        slug = request.args.get('zone')
        if not slug or slug in ('all', ''):
            return cells_query, None
        zone = models.TwinZone.query.filter_by(city_id=city.id, slug=slug).first()
        if zone is None:
            return cells_query, None
        return cells_query.filter(models.TwinCell.zone_id == zone.id), zone

    # -- pages --------------------------------------------------------------
    @pages.route('/digital-twin')
    @twin_access_required()
    def digital_twin_page():
        return render_template('digital_twin.html')

    # -- metadata -----------------------------------------------------------
    @api.route('/cities')
    @twin_access_required()
    def cities():
        payload = []
        for city in models.TwinCity.query.order_by(models.TwinCity.name).all():
            payload.append({
                'slug': city.slug,
                'name': city.name,
                'state': city.state,
                'camera': city.camera_config(),
                'bbox': list(city.bbox) if city.bbox_min_lon is not None else None,
                'h3_resolution': city.h3_resolution,
                'cell_count': city.cells.count(),
                'last_computed_at': city.last_computed_at.isoformat() + 'Z' if city.last_computed_at else None,
                'zones': [{'slug': z.slug, 'name': z.name,
                           'center': [z.center_longitude, z.center_latitude],
                           'boundary_source': z.boundary_source}
                          for z in city.zones.order_by(models.TwinZone.name)],
            })
        return serializers.json_response({
            'cities': payload,
            'horizons': list(twin_config.HORIZONS),
            'status_bands': [{'status': s, 'floor': f} for s, f in twin_config.STATUS_BANDS],
            'attributions': ATTRIBUTIONS,
            'gibs_native_max_zoom': GIBS_NATIVE_MAX_ZOOM,
        }, max_age=60)

    @api.route('/<city_slug>/zones')
    @twin_access_required()
    def zones(city_slug):
        city, error = get_city_or_404(city_slug)
        if error:
            return error
        return serializers.json_response(
            serializers.zone_collection(city.zones.order_by(models.TwinZone.name)),
            max_age=300)

    # -- the risk grid ------------------------------------------------------
    @api.route('/<city_slug>/state')
    @twin_access_required()
    def state(city_slug):
        city, error = get_city_or_404(city_slug)
        if error:
            return error

        horizon = requested_horizon()
        include_geometry = request.args.get('geometry', 'true').lower() != 'false'

        query = models.TwinCell.query.filter_by(city_id=city.id)
        query, zone = zone_filter(city, query)

        pairs = (query
                 .outerjoin(models.TwinCellState,
                            db.and_(models.TwinCellState.cell_id == models.TwinCell.id,
                                    models.TwinCellState.horizon_hours == horizon))
                 .add_entity(models.TwinCellState)
                 .all())

        collection = serializers.state_collection(pairs, geometry=include_geometry)
        collection['meta'] = {
            'city': city.slug,
            'horizon_hours': horizon,
            'zone': zone.slug if zone else None,
            'cells': len(collection['features']),
            'last_computed_at': city.last_computed_at.isoformat() + 'Z' if city.last_computed_at else None,
        }
        return serializers.json_response(collection)

    @api.route('/<city_slug>/cell/<h3_index>')
    @twin_access_required()
    def cell_detail(city_slug, h3_index):
        city, error = get_city_or_404(city_slug)
        if error:
            return error

        cell = models.TwinCell.query.filter_by(city_id=city.id, h3_index=h3_index).first()
        if cell is None:
            return serializers.json_response({'error': 'Unknown cell', 'h3': h3_index}, etag=False)

        states = list(cell.states)
        assets = models.TwinInfrastructure.query.filter_by(cell_id=cell.id).all()

        # Reports are read live rather than from the compute pass so a drawer
        # opened seconds after a submission already shows it.
        from .ingest.internal_reports import collect_incidents
        _scoring, pins = collect_incidents(Report, city.bbox, resolution=city.h3_resolution)
        reports = [p for p in pins if p['h3'] == h3_index]

        payload = serializers.cell_detail(cell, states, assets, reports, zone=cell.zone)
        # Instant, and of this exact cell. The imagery panel is a separate,
        # much slower request (five to seventeen KartaView round trips on a
        # cold cell); without this the drawer shows "Loading..." and no
        # picture at all for that whole time.
        payload['aerial'] = aerial.crop_for_point(cell.center_latitude,
                                                  cell.center_longitude)
        return serializers.json_response(payload, etag=False)

    @api.route('/<city_slug>/summary')
    @twin_access_required()
    def summary(city_slug):
        city, error = get_city_or_404(city_slug)
        if error:
            return error
        horizon = requested_horizon()

        rows = (db.session.query(models.TwinCellState.status,
                                 db.func.count(models.TwinCellState.id),
                                 db.func.avg(models.TwinCellState.risk_score),
                                 db.func.max(models.TwinCellState.risk_score))
                .join(models.TwinCell, models.TwinCell.id == models.TwinCellState.cell_id)
                .filter(models.TwinCell.city_id == city.id,
                        models.TwinCellState.horizon_hours == horizon)
                .group_by(models.TwinCellState.status)
                .all())

        counts = {'normal': 0, 'watch': 0, 'warning': 0, 'critical': 0}
        total, weighted, peak = 0, 0.0, 0.0
        for status_name, count, avg, mx in rows:
            counts[status_name] = count
            total += count
            weighted += (avg or 0.0) * count
            peak = max(peak, mx or 0.0)

        degraded = (models.TwinCellState.query
                    .join(models.TwinCell, models.TwinCell.id == models.TwinCellState.cell_id)
                    .filter(models.TwinCell.city_id == city.id,
                            models.TwinCellState.horizon_hours == horizon,
                            models.TwinCellState.degraded_inputs.is_(True))
                    .count())

        _scoring, pins = _incidents(city)
        return serializers.json_response({
            'city': city.slug,
            'horizon_hours': horizon,
            'cells': total,
            'status_counts': counts,
            'avg_risk': round(weighted / total, 2) if total else 0.0,
            'max_risk': round(peak, 2),
            'degraded_cells': degraded,
            'incidents': len(pins),
            'incidents_approved': sum(1 for p in pins if p['status'] == 'approved'),
            'cameras': int(db.session.query(db.func.sum(models.TwinCell.camera_count))
                           .filter(models.TwinCell.city_id == city.id).scalar() or 0),
            'assets': models.TwinInfrastructure.query.filter_by(city_id=city.id).count(),
            'last_computed_at': city.last_computed_at.isoformat() + 'Z' if city.last_computed_at else None,
        }, etag=False)

    def _incidents(city):
        from .ingest.internal_reports import collect_incidents
        return collect_incidents(Report, city.bbox, resolution=city.h3_resolution)

    @api.route('/<city_slug>/incidents')
    @twin_access_required()
    def incidents(city_slug):
        city, error = get_city_or_404(city_slug)
        if error:
            return error
        _scoring, pins = _incidents(city)
        return serializers.json_response(serializers.incidents_collection(pins), etag=False)

    @api.route('/<city_slug>/infrastructure')
    @twin_access_required()
    def infrastructure(city_slug):
        city, error = get_city_or_404(city_slug)
        if error:
            return error
        rows = models.TwinInfrastructure.query.filter_by(city_id=city.id).all()
        return serializers.json_response(
            serializers.infrastructure_collection(rows), max_age=600)

    # -- official alerts ----------------------------------------------------
    @api.route('/<city_slug>/alerts')
    @twin_access_required()
    def alerts(city_slug):
        city, error = get_city_or_404(city_slug)
        if error:
            return error

        include_expired = request.args.get('expired', 'false').lower() == 'true'
        now = datetime.utcnow()

        query = (models.TwinExternalAlert.query
                 .join(models.TwinAlertCell,
                       models.TwinAlertCell.alert_id == models.TwinExternalAlert.id)
                 .filter(models.TwinAlertCell.city_id == city.id)
                 .order_by(models.TwinExternalAlert.effective_at.desc())
                 .distinct())
        rows = query.all()
        if not include_expired:
            rows = [a for a in rows if a.is_live(now)]

        collection = serializers.alerts_collection(rows, now=now)
        collection['meta'] = {
            'city': city.slug,
            'live': sum(1 for f in collection['features'] if f['properties']['live']),
            'total': len(collection['features']),
            'includes_expired': include_expired,
        }
        return serializers.json_response(collection, etag=False)

    @api.route('/alerts/poll', methods=['POST'])
    @twin_access_required(admin=True)
    def alerts_poll():
        body = request.get_json(silent=True) or {}
        from . import alerts as alert_service
        return serializers.json_response(
            {'polled': alert_service.poll_alerts(db, models, force=bool(body.get('force')))},
            etag=False)

    # -- live stations & transit ---------------------------------------------
    @api.route('/<city_slug>/live')
    @twin_access_required()
    def live_all(city_slug):
        city, error = get_city_or_404(city_slug)
        if error:
            return error
        from . import live
        return serializers.json_response({
            'city': city.slug,
            'stations': live.live_stations(models, city),
            'vehicles': live.live_vehicles(models, city),
        }, etag=False)

    @api.route('/<city_slug>/live/<kind>')
    @twin_access_required()
    def live_kind(city_slug, kind):
        city, error = get_city_or_404(city_slug)
        if error:
            return error
        from . import live
        if kind == 'stations':
            return serializers.json_response({'city': city.slug, 'stations': live.live_stations(models, city)}, etag=False)
        if kind == 'transit':
            return serializers.json_response({'city': city.slug, 'vehicles': live.live_vehicles(models, city)}, etag=False)
        return serializers.json_response({'error': 'kind must be "stations" or "transit"'}, etag=False)

    @api.route('/live/refresh', methods=['POST'])
    @twin_access_required(admin=True)
    def live_refresh():
        from . import live
        return serializers.json_response(live.poll_all(db, models), etag=False)

    # -- agent flag queue ---------------------------------------------------
    @api.route('/flags')
    @twin_access_required()
    def flags():
        status = request.args.get('status', 'pending')
        query = models.TwinFlag.query
        if status and status != 'all':
            query = query.filter(models.TwinFlag.status == status)
        rows = query.order_by(models.TwinFlag.risk_score.desc(),
                              models.TwinFlag.created_at.desc()).limit(100).all()

        slugs = {c.id: c.slug for c in models.TwinCity.query.all()}
        return serializers.json_response({
            'flags': [serializers.flag_payload(f, slugs.get(f.city_id)) for f in rows],
            'pending': models.TwinFlag.query.filter_by(status='pending').count(),
            'agent_enabled': twin_config.AGENT_ENABLED,
            # Distinguishes "switched off" from "switched on but keyless" - the
            # second is a configuration mistake worth surfacing, the first is a
            # supported steady state.
            'agent_available': twin_config.agent_available(),
        }, etag=False)

    @api.route('/<city_slug>/flags/areas')
    @twin_access_required()
    def flag_areas(city_slug):
        """A circle footprint per active flag, for the map's 3D flag walls.

        Reuses `dispatch.flag_footprint` rather than recomputing a shape -
        the same circle a dispatch would actually alert around is the one
        drawn as "this area is under review", so the map never shows a
        footprint that disagrees with what Send would really reach.
        """
        city, error = get_city_or_404(city_slug)
        if error:
            return error

        from . import dispatch as dispatch_service

        rows = (models.TwinFlag.query
                .filter_by(city_id=city.id)
                .filter(models.TwinFlag.status.in_(('pending', 'approved')))
                .all())

        areas = []
        for flag in rows:
            footprint = dispatch_service.flag_footprint(models, flag)
            if footprint is None:
                continue
            lat, lon, radius_km = footprint
            areas.append({
                'id': flag.id, 'hazard_type': flag.hazard_type,
                'severity': flag.severity, 'status': flag.status,
                'lat': lat, 'lon': lon, 'radius_m': round(radius_km * 1000.0, 1),
            })
        return serializers.json_response({'city': city.slug, 'areas': areas}, etag=False)

    @api.route('/flags/<int:flag_id>', methods=['POST'])
    @twin_access_required(admin=True)
    def review_flag(flag_id):
        """The human gate. Nothing reaches the map without passing through here."""
        from flask_login import current_user

        flag = models.TwinFlag.query.get(flag_id)
        if flag is None:
            return serializers.json_response({'error': 'Unknown flag'}, etag=False)

        body = request.get_json(silent=True) or {}
        decision = (body.get('decision') or '').lower()
        if decision not in ('approve', 'reject'):
            return serializers.json_response(
                {'error': 'decision must be "approve" or "reject"'}, etag=False)

        flag.status = 'approved' if decision == 'approve' else 'rejected'
        flag.review_note = body.get('note')
        flag.reviewed_at = datetime.utcnow()
        flag.reviewed_by = getattr(current_user, 'id', None)
        db.session.commit()

        city = models.TwinCity.query.get(flag.city_id) if flag.city_id else None
        if city is not None:
            from .stream import publish
            publish(city.slug, 'state', {
                'city': city.slug,
                'reason': 'flag_%s' % flag.status,
                'flag_id': flag.id,
            })
        return serializers.json_response(
            {'flag': serializers.flag_payload(flag, city.slug if city else None)}, etag=False)

    @api.route('/flags/<int:flag_id>/dispatch/preview')
    @twin_access_required(admin=True)
    def dispatch_preview(flag_id):
        """How many people a dispatch would reach, before anything sends."""
        from . import dispatch as dispatch_service

        flag = models.TwinFlag.query.get(flag_id)
        if flag is None:
            return serializers.json_response({'error': 'Unknown flag'}, etag=False)

        try:
            return serializers.json_response(dispatch_service.preview(models, flag), etag=False)
        except dispatch_service.DispatchError as exc:
            return serializers.json_response({'error': str(exc)}, etag=False), 400

    @api.route('/flags/<int:flag_id>/dispatch', methods=['POST'])
    @twin_access_required(admin=True)
    def dispatch_flag(flag_id):
        """Send. The only route in the twin that can reach a real phone."""
        from flask_login import current_user

        from . import dispatch as dispatch_service

        flag = models.TwinFlag.query.get(flag_id)
        if flag is None:
            return serializers.json_response({'error': 'Unknown flag'}, etag=False)

        body = request.get_json(silent=True) or {}
        try:
            result = dispatch_service.send(
                db, models, flag, getattr(current_user, 'id', None),
                note=body.get('note'), force=bool(body.get('force')))
        except dispatch_service.DispatchError as exc:
            return serializers.json_response({'error': str(exc)}, etag=False), 400

        city = models.TwinCity.query.get(flag.city_id) if flag.city_id else None
        if city is not None:
            from .stream import publish
            publish(city.slug, 'state', {
                'city': city.slug, 'reason': 'flag_dispatched', 'flag_id': flag.id,
            })
        return serializers.json_response(result, etag=False)

    @api.route('/flags/<int:flag_id>/dispatch/history')
    @twin_access_required(admin=True)
    def dispatch_history(flag_id):
        from . import dispatch as dispatch_service
        return serializers.json_response(
            {'dispatches': dispatch_service.dispatch_history(models, flag_id)}, etag=False)

    @api.route('/agent/run', methods=['POST'])
    @twin_access_required(admin=True)
    def agent_run():
        from .agent import run_forecast, run_triage
        body = request.get_json(silent=True) or {}
        slug = body.get('city')
        return serializers.json_response({
            'triage': run_triage(db, models, city_slug=slug),
            'forecast': run_forecast(db, models, city_slug=slug),
        }, etag=False)

    @api.route('/agent/status')
    @twin_access_required()
    def agent_status_route():
        from .agent import agent_status
        return serializers.json_response(agent_status(), etag=False)

    # -- lazy OSM layers ----------------------------------------------------
    @api.route('/<city_slug>/cameras')
    @twin_access_required()
    def cameras(city_slug):
        city, error = get_city_or_404(city_slug)
        if error:
            return error
        result = CameraAdapter().run_cached_only(bbox=city.bbox)
        if not result.ok:
            return serializers.json_response({
                'type': 'FeatureCollection', 'features': [],
                'pending': True,
                'message': 'Camera layer has not been ingested yet for this city.',
            }, etag=False)
        collection = serializers.cameras_collection(result.data)
        collection['stale'] = result.status != 'ok'
        return serializers.json_response(collection, max_age=1800)

    @api.route('/<city_slug>/water')
    @twin_access_required()
    def water(city_slug):
        city, error = get_city_or_404(city_slug)
        if error:
            return error
        result = WaterAdapter().run_cached_only(bbox=city.bbox)
        if not result.ok:
            return serializers.json_response({
                'type': 'FeatureCollection', 'features': [],
                'pending': True,
                'message': 'Hydrology layer has not been ingested yet for this city.',
            }, etag=False)
        collection = serializers.water_collection(result.data)
        collection['stale'] = result.status != 'ok'
        return serializers.json_response(collection, max_age=1800)

    @api.route('/<city_slug>/timeline')
    @twin_access_required()
    def timeline(city_slug):
        city, error = get_city_or_404(city_slug)
        if error:
            return error
        try:
            hours = max(1, min(168, int(request.args.get('hours', 24))))
        except (TypeError, ValueError):
            hours = 24
        since = datetime.utcnow() - timedelta(hours=hours)

        rows = (db.session.query(models.TwinCellHistory.recorded_at,
                                 db.func.avg(models.TwinCellHistory.risk_score),
                                 db.func.max(models.TwinCellHistory.risk_score),
                                 db.func.count(models.TwinCellHistory.id))
                .join(models.TwinCell, models.TwinCell.id == models.TwinCellHistory.cell_id)
                .filter(models.TwinCell.city_id == city.id,
                        models.TwinCellHistory.horizon_hours == 0,
                        models.TwinCellHistory.recorded_at >= since)
                .group_by(models.TwinCellHistory.recorded_at)
                .order_by(models.TwinCellHistory.recorded_at)
                .all())

        return serializers.json_response({
            'city': city.slug,
            'hours': hours,
            'buckets': [{
                'at': at.isoformat() + 'Z',
                'avg_risk': round(avg or 0.0, 2),
                'max_risk': round(mx or 0.0, 2),
                'cells': count,
            } for at, avg, mx, count in rows],
        }, etag=False)

    def _report_photos_near(lat, lon, radius_m, limit=6):
        """Photos from this app's own reports within `radius_m` of a point.

        These are the only pictures in the drawer that are both recent AND
        genuinely of this exact place, so they lead the panel whenever one
        exists. Scanning is bounded by a lat/lon box first so the distance
        maths only ever runs over a handful of rows.
        """
        from urllib.parse import quote

        span = radius_m / 111000.0
        since = datetime.utcnow() - timedelta(hours=twin_config.GROUND_REPORT_LOOKBACK_H)
        try:
            rows = (Report.query
                    .filter(Report.timestamp >= since,
                            Report.image_file.isnot(None),
                            Report.image_file != '',
                            Report.latitude.between(lat - span, lat + span),
                            Report.longitude.between(lon - span, lon + span))
                    .order_by(Report.timestamp.desc())
                    .limit(50)
                    .all())
        except Exception:  # noqa: BLE001 - C1: a DB surprise hides this source, not the drawer
            return []

        out = []
        for report in rows:
            distance = haversine_m(lat, lon, report.latitude, report.longitude)
            if distance > radius_m:
                continue
            url = '/static/uploads/%s' % quote(report.image_file)
            out.append({
                'provider': 'Citizen report',
                'licence': 'reporter-submitted',
                'id': 'report:%s' % report.id,
                'lat': float(report.latitude),
                'lon': float(report.longitude),
                'heading': None,
                'title': report.title,
                'hazard_type': report.hazard_type,
                'status': report.verification_status,
                'captured_at': report.timestamp.isoformat() + 'Z' if report.timestamp else None,
                'thumb_url': url,
                'full_url': url,
                # /report/<id> does not exist in this app - the route is
                # /view_report/<id>, so the old link 404'd.
                'page_url': '/view_report/%s' % report.id,
                'distance_m': round(distance, 1),
                'live': False,
            })
            if len(out) >= limit:
                break
        return out

    # -- ground truth -------------------------------------------------------
    @api.route('/cctv')
    @twin_access_required()
    def cctv_near():
        """Cameras near a point, across whichever city's cache contains it."""
        lat, lon, bad = _point_args()
        if bad:
            return bad
        radius = _float_arg('radius', twin_config.CCTV_RADIUS_M)

        found = []
        for city in models.TwinCity.query.all():
            if city.bbox_min_lon is None:
                continue
            result = CameraAdapter().run_cached_only(bbox=city.bbox)
            if not result.ok:
                continue
            for camera in result.data:
                distance = haversine_m(lat, lon, camera['lat'], camera['lon'])
                if distance <= radius:
                    entry = dict(camera)
                    entry['distance_m'] = round(distance, 1)
                    entry['city'] = city.slug
                    found.append(entry)
        found.sort(key=lambda c: c['distance_m'])
        return serializers.json_response({
            'cameras': found[:50],
            'count': len(found),
            'radius_m': radius,
            'attribution': '(c) OpenStreetMap contributors (ODbL)',
            'note': 'Mapped camera locations only. Sentinel never connects to a camera device or proxies a stream.',
        }, etag=False)

    @api.route('/cctv/view')
    @twin_access_required()
    def cctv_view():
        """Nearest open street-level image facing roughly where a camera points.

        This is explicitly *not* a camera feed. The response carries provider,
        capture date and `live: false` so the UI can caption it honestly.
        """
        lat, lon, bad = _point_args()
        if bad:
            return bad
        direction = request.args.get('direction')
        try:
            direction = float(direction) if direction not in (None, '') else None
        except ValueError:
            direction = None

        # When the caller names a city, live webcams are searched around that
        # city's centre so every cell in it gets the city's live cameras.
        city_lat = city_lon = None
        city_slug = request.args.get('city')
        if city_slug:
            city = models.TwinCity.query.filter_by(slug=city_slug).first()
            if city is not None:
                city_lat, city_lon = city.center_latitude, city.center_longitude

        result = StreetViewAdapter().run(
            lat=lat, lon=lon, direction=direction,
            city_lat=city_lat, city_lon=city_lon,
            radius_m=_float_arg('radius', twin_config.STREETVIEW_RADIUS_M),
            # Live stills go stale; don't serve a cached frame as "now".
            force=request.args.get('fresh', 'false').lower() == 'true')
        payload = result.data or {'images': [], 'facing': None, 'nearest': None, 'live': []}
        payload['status'] = result.status
        payload['has_live'] = bool(payload.get('live'))
        # `best` is what the UI should lead with, and `best_kind` says what it
        # is. Previously the UI only ever rendered `facing`, so a camera whose
        # bearing matched nothing showed a caption and no picture at all - even
        # with a good photo of the same junction thirty metres away.
        # Report photos are the only imagery that is both recent and genuinely
        # of this exact spot, so they are fetched for every point and rendered
        # ahead of everything else when one exists.
        payload['reports'] = _report_photos_near(
            lat, lon, twin_config.STREETVIEW_REPORT_RADIUS_M)
        # The floor: every point gets a satellite crop of itself, so no
        # location is ever left showing only the shared city webcam. Ranked
        # below every ground-level source - it is the right answer to "what is
        # here" and the wrong answer to "what does this look like".
        payload['aerial'] = aerial.crop_for_point(lat, lon)
        payload['best'], payload['best_kind'] = _best_view(payload)
        payload['caption'] = _view_caption(payload, direction)
        payload['live_source_available'] = bool(twin_config.WINDY_WEBCAMS_KEY)
        return serializers.json_response(payload, etag=False)

    @api.route('/cctv/caption')
    @twin_access_required()
    def cctv_caption():
        """A vision-model reading of the same 'best' image `/cctv/view` would
        lead with, for this exact point.

        Deliberately re-derives the image server-side from lat/lon rather
        than accepting an image URL from the client - that keeps this route
        from ever fetching an arbitrary caller-supplied URL (SSRF), and it
        only ever reads from the same three providers `/cctv/view` already
        trusts. Called lazily by the drawer, never from the compute pass.
        """
        from . import vision
        if not vision.vision_available():
            return serializers.json_response(
                {'available': False,
                 'reason': 'No NVIDIA_API_KEY/OPENROUTER_API_KEY configured.'}, etag=False)

        lat, lon, bad = _point_args()
        if bad:
            return bad
        direction = request.args.get('direction')
        try:
            direction = float(direction) if direction not in (None, '') else None
        except ValueError:
            direction = None

        city_lat = city_lon = None
        city_slug = request.args.get('city')
        if city_slug:
            city = models.TwinCity.query.filter_by(slug=city_slug).first()
            if city is not None:
                city_lat, city_lon = city.center_latitude, city.center_longitude

        result = StreetViewAdapter().run(
            lat=lat, lon=lon, direction=direction,
            city_lat=city_lat, city_lon=city_lon,
            radius_m=_float_arg('radius', twin_config.STREETVIEW_RADIUS_M))
        payload = result.data or {'images': [], 'facing': None, 'nearest': None, 'live': []}
        best, best_kind = _best_view(payload)
        if not best:
            return serializers.json_response(
                {'available': True, 'caption': None, 'reason': 'No imagery for this point.'}, etag=False)

        image_url = best.get('thumb_url') or best.get('full_url')
        caption = vision.caption_ground_image(image_url, label=best.get('title') or best.get('provider'))
        if caption is None or caption.get('error'):
            # Say which thing failed. "Vision model call failed" was reported
            # even when the real problem was the provider's own image URL
            # returning 404, which points an operator at the wrong fix.
            return serializers.json_response(
                {'available': True, 'caption': None,
                 'reason': (caption or {}).get(
                     'reason', 'Vision model call failed or timed out.')}, etag=False)
        caption['kind'] = best_kind
        return serializers.json_response({'available': True, 'caption': caption}, etag=False)

    @api.route('/cctv/streams')
    @twin_access_required()
    def cctv_streams():
        """Operator-supplied live feeds - see cameras.py's module docstring.

        Every URL is returned as-is for the browser to load directly; this
        route never fetches one itself.
        """
        from . import cameras
        city_slug = request.args.get('city')
        if not city_slug:
            return serializers.json_response({'error': 'city is required'}, etag=False)

        lat, lon = None, None
        try:
            lat = float(request.args.get('lat')) if request.args.get('lat') else None
            lon = float(request.args.get('lon')) if request.args.get('lon') else None
        except ValueError:
            pass

        radius = _float_arg('radius', None)
        streams = cameras.streams_near(city_slug, lat, lon, radius_m=radius)
        return serializers.json_response({'city': city_slug, 'streams': streams}, etag=False)

    @api.route('/<city_slug>/osint')
    @twin_access_required()
    def osint_feed(city_slug):
        """Open-source intelligence within OSINT_RADIUS_KM of this city.

        A GeoJSON FeatureCollection of located observations - live aircraft,
        regional seismicity, open natural-event tracks, satellite thermal
        anomalies - plus a `news` list, which is deliberately NOT geometry:
        GDELT says an article is about this city, never where in it. See
        twin/osint.py for what each source is and what was verified.

        Never an official warning. Official alerts stay on their own
        SACHET/IMD layer, and this route must never be mistaken for one.
        """
        from . import osint

        city, error = get_city_or_404(city_slug)
        if error:
            return error
        kinds = request.args.get('kinds')
        payload = osint.collect(
            city, kinds=[k.strip() for k in kinds.split(',')] if kinds else None)
        # Aircraft positions are seconds old; nothing here may sit in an
        # edge cache.
        return serializers.json_response(payload, etag=False)

    @api.route('/<city_slug>/osint/near')
    @twin_access_required()
    def osint_near(city_slug):
        """OSINT for one clicked point, not the whole city.

        Served from the same cached city collection `/osint` builds, with
        every distance re-measured against this point - so opening cell
        drawers costs no extra requests to OpenSky, EMSC, EONET or FIRMS.
        """
        from . import osint

        city, error = get_city_or_404(city_slug)
        if error:
            return error
        lat, lon, bad = _point_args()
        if bad:
            return bad
        radius = _float_arg('radius', twin_config.OSINT_NEAR_RADIUS_KM)
        return serializers.json_response(
            osint.near_point(city, lat, lon, radius_km=radius), etag=False)

    @api.route('/<city_slug>/ground-imagery')
    @twin_access_required()
    def ground_imagery(city_slug):
        """Every location in one city that has a picture, from every source.

        This is the city-scale counterpart to `/cctv/view`, which answers for
        one point. See twin/ground.py for which sources are real, which are
        blocked and why, and which were checked and rejected.

        `?fresh=1` re-pulls the live webcam frames only. The archival
        providers are left on their own 24 h cache - a 60-second refresh loop
        re-querying photographs taken in 2019 would be pure noise upstream.
        """
        from . import ground

        city, error = get_city_or_404(city_slug)
        if error:
            return error
        zones = city.zones.order_by(models.TwinZone.name).all()
        board = ground.build_board(
            city, zones, Report=Report,
            fresh=request.args.get('fresh', '').lower() in ('1', 'true', 'yes'))
        # Never cached at the edge: half of what this returns claims to be live.
        return serializers.json_response(board, etag=False)

    @api.route('/streetview')
    @twin_access_required()
    def streetview():
        lat, lon, bad = _point_args()
        if bad:
            return bad
        result = StreetViewAdapter().run(
            lat=lat, lon=lon,
            radius_m=_float_arg('radius', twin_config.STREETVIEW_RADIUS_M))
        return serializers.json_response(result.data or {'images': []}, etag=False)

    # -- overlays -----------------------------------------------------------
    @api.route('/radar')
    @twin_access_required()
    def radar():
        result = RainViewerAdapter().run()
        if not result.ok:
            return serializers.json_response(
                {'available': False, 'error': result.error}, etag=False)
        payload = dict(result.data)
        payload['available'] = True
        payload['stale'] = result.status != 'ok'
        return serializers.json_response(payload, etag=False)

    @api.route('/gibs')
    @twin_access_required()
    def gibs():
        layer_key = request.args.get('layer', 'viirs')
        layer = GIBS_LAYERS.get(layer_key, GIBS_LAYERS['viirs'])
        date = request.args.get('date')
        if not date:
            # GIBS publishes a day in arrears; asking for today usually returns
            # blank tiles, which reads as a broken layer.
            date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
        return serializers.json_response({
            'available': True,
            'layer': layer,
            'layer_key': layer_key,
            'date': date,
            'tile_template': GIBS_TEMPLATE.format(layer=layer, date=date),
            'native_max_zoom': GIBS_NATIVE_MAX_ZOOM,
            'note': 'Imagery is native to about zoom %d; above that MapLibre over-zooms '
                    'the last valid tile rather than fetching sharper data.' % GIBS_NATIVE_MAX_ZOOM,
            'attribution': 'NASA EOSDIS GIBS',
            'layers': list(GIBS_LAYERS.keys()),
        }, max_age=3600)

    @api.route('/traffic')
    @twin_access_required()
    def traffic():
        key = twin_config.TOMTOM_API_KEY
        if not key:
            return serializers.json_response({
                'available': False,
                'reason': 'TOMTOM_API_KEY is not configured.',
            }, etag=False)
        return serializers.json_response({
            'available': True,
            'tile_template': ('https://api.tomtom.com/traffic/map/4/tile/flow/relative0/'
                              '{z}/{x}/{y}.png?key=%s' % key),
            'attribution': '(c) TomTom',
        }, etag=False)

    # -- health / compare ---------------------------------------------------
    @api.route('/health')
    @twin_access_required()
    def health():
        latest = {}
        rows = (models.TwinDataSnapshot.query
                .order_by(models.TwinDataSnapshot.created_at.desc())
                .limit(200).all())
        for row in rows:
            if row.source_key in latest:
                continue
            latest[row.source_key] = {
                'source': row.source_key,
                'status': row.status,
                'latency_ms': row.latency_ms,
                'records': row.records_ingested,
                'error': row.error_message,
                'at': row.created_at.isoformat() + 'Z' if row.created_at else None,
            }
        sources = sorted(latest.values(), key=lambda s: s['source'])
        failing = [s for s in sources if s['status'] in ('failed', 'degraded')]
        return serializers.json_response({
            'overall': 'degraded' if failing else ('ok' if sources else 'unknown'),
            'sources': sources,
            'failing': [s['source'] for s in failing],
            'sse_subscribers': subscriber_count(),
            'scheduler_enabled': twin_config.TWIN_SCHEDULER_ENABLED,
        }, etag=False)

    @api.route('/compare')
    @twin_access_required()
    def compare():
        horizon = requested_horizon()
        out = []
        for city in models.TwinCity.query.order_by(models.TwinCity.name).all():
            rows = (db.session.query(models.TwinCellState.status,
                                     db.func.count(models.TwinCellState.id),
                                     db.func.avg(models.TwinCellState.risk_score))
                    .join(models.TwinCell, models.TwinCell.id == models.TwinCellState.cell_id)
                    .filter(models.TwinCell.city_id == city.id,
                            models.TwinCellState.horizon_hours == horizon)
                    .group_by(models.TwinCellState.status).all())
            counts = {'normal': 0, 'watch': 0, 'warning': 0, 'critical': 0}
            total, weighted = 0, 0.0
            for status_name, count, avg in rows:
                counts[status_name] = count
                total += count
                weighted += (avg or 0.0) * count
            out.append({
                'city': city.slug, 'name': city.name,
                'status_counts': counts, 'cells': total,
                'avg_risk': round(weighted / total, 2) if total else 0.0,
            })
        return serializers.json_response({'horizon_hours': horizon, 'cities': out}, etag=False)

    # -- realtime -----------------------------------------------------------
    @api.route('/stream')
    @twin_access_required()
    def stream():
        city = request.args.get('city') or None

        def generate():
            sub = subscribe(city)
            try:
                yield 'retry: 5000\n\n'
                yield format_sse({'event': 'hello', 'city': city,
                                  'payload': {'ok': True},
                                  'at': datetime.utcnow().isoformat() + 'Z'})
                while True:
                    try:
                        message = sub.queue.get(timeout=20)
                    except Exception:  # noqa: BLE001 - queue.Empty
                        # A comment frame keeps proxies from closing an idle
                        # connection; the client never sees it as an event.
                        yield ': keep-alive\n\n'
                        continue
                    yield format_sse(message)
            finally:
                unsubscribe(sub)

        return Response(stream_with_context(generate()), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache',
                                 'X-Accel-Buffering': 'no',
                                 'Connection': 'keep-alive'})

    # -- mutations ----------------------------------------------------------
    @api.route('/refresh', methods=['POST'])
    @twin_access_required(admin=True)
    def refresh():
        body = request.get_json(silent=True) or {}
        target = body.get('city') or request.args.get('city') or 'all'
        force = bool(body.get('force'))

        if target == 'all':
            return serializers.json_response(
                {'refreshed': engine.compute_all(db, models, Report, force=force)}, etag=False)

        city, error = get_city_or_404(target)
        if error:
            return error
        return serializers.json_response(
            {'refreshed': {city.slug: engine.compute_city(db, models, city, Report, force=force)}},
            etag=False)

    @api.route('/seed', methods=['POST'])
    @twin_access_required(admin=True)
    def seed_route():
        body = request.get_json(silent=True) or {}
        report = seed.seed_all(db, models,
                               rebuild=bool(body.get('rebuild')),
                               skip_slow=bool(body.get('skip_slow', True)))
        return serializers.json_response({'seeded': report}, etag=False)

    # -- small helpers ------------------------------------------------------
    def _float_arg(name, default):
        try:
            return float(request.args.get(name, default))
        except (TypeError, ValueError):
            return default

    def _point_args():
        try:
            return float(request.args['lat']), float(request.args['lon']), None
        except (KeyError, TypeError, ValueError):
            return None, None, serializers.json_response(
                {'error': 'lat and lon query parameters are required'}, etag=False)

    return pages, api


def _best_view(payload):
    """Pick the single image to lead with, and name what it is.

    A citizen report photo within STREETVIEW_REPORT_RADIUS_M wins outright: it
    is the only imagery here that is recent AND of this exact place. After
    that, a genuine nearby photo of THIS point - found within the normal search
    radius, not the widened fallback (see streetview.py's
    STREETVIEW_FALLBACK_RADIUS_M) - beats the live webcam. The live frame is
    current, but it is shared across every cell in the city (Bengaluru has
    exactly one registered public webcam - see streetview.py's module
    docstring), so leading with it made every cell's drawer show the
    identical image. A real photo actually taken near the clicked point is
    the one thing that differs cell to cell, so it leads whenever one
    exists close enough to mean something. A widened-fallback photo - found
    several km out - is honest borrowed context, same tier as the webcam,
    not "this location" either, so it only leads when nothing closer exists
    at all. The caller renders `best_kind` next to the image so the
    operator is never left guessing which of the three they are looking at.
    """
    # A citizen report photo outranks everything: it is recent AND it is this
    # exact place, which no other source here manages at once.
    reports = payload.get('reports') or []
    if reports:
        return reports[0], 'report'

    close_photo = payload.get('facing') or payload.get('nearest')
    if close_photo and not payload.get('widened'):
        return close_photo, ('facing' if payload.get('facing') else 'nearest')

    # Nothing close exists. Everything still on the table is a picture of
    # somewhere else, except the satellite crop - so the crop leads. A photo
    # found 2 km out by the widened ring and a webcam 4.5 km out are both
    # "not here", and the webcam is worse: it is byte-identical in every cell
    # of the city, which is exactly how eight different locations end up
    # showing the same image.
    if payload.get('aerial'):
        return payload['aerial'], 'aerial'
    if close_photo:
        return close_photo, ('facing' if payload.get('facing') else 'nearest')
    if payload.get('live'):
        return payload['live'][0], 'live'
    return None, 'none'


def _view_caption(payload, direction):
    best, kind = payload.get('best'), payload.get('best_kind')

    if kind == 'live':
        # Distance is not optional here. The only Windy webcam near Bengaluru
        # sits 7.6 km from the centre, and a live frame presented without its
        # distance reads as a picture of the street you are looking at.
        distance = best.get('distance_m')
        where = ('%.1f km away' % (distance / 1000.0)) if distance else 'nearby'
        return ('LIVE webcam frame - %s, %s. Captured %s. This is current city '
                'context, not a view of this exact spot.'
                % (best.get('title') or best.get('provider'), where,
                   best.get('captured_at') or 'recently'))

    if kind == 'report':
        return ('Photo from a citizen report %d m from this point - %s (%s, %s). '
                'Recent and genuinely this place; it is a reporter\'s photo, not a '
                'camera feed.'
                % (round(best.get('distance_m') or 0),
                   best.get('title') or 'untitled report',
                   (best.get('hazard_type') or 'report').replace('_', ' '),
                   best.get('status') or 'unreviewed'))

    if kind == 'facing':
        return ('Open street-level photo looking ~%s, the direction this camera faces '
                '(%s, %s). Archival - not a live feed.'
                % (_compass(direction), best.get('provider'),
                   best.get('captured_at') or 'date unknown'))

    if kind == 'nearest':
        heading = best.get('heading')
        # Say plainly that this is not the camera's view. It is the closest
        # picture of the place, which is useful, but it is a different claim.
        return ('Closest open street-level photo, %d m away%s (%s, %s). It does NOT '
                'look along the camera\'s bearing, and is archival - not a live feed.'
                % (round(best.get('distance_m') or 0),
                   (' looking ~%s' % _compass(heading)) if heading is not None else '',
                   best.get('provider'), best.get('captured_at') or 'date unknown'))

    if kind == 'aerial':
        return ('Satellite view of this exact point (%s, ~%d m across). No ground-level '
                'photograph of this place exists in any open source, so this is the '
                'closest honest answer - it looks straight down, not along a street, '
                'and carries no capture date.'
                % (best.get('provider'), best.get('span_m') or 0))

    return ('No street-level photograph exists for this point in KartaView or '
            'Mapillary, and no citizen report here carries a photo. OpenStreetMap '
            'maps camera locations, not camera feeds, and no webcam publishes this '
            'place.')


def _compass(bearing):
    if bearing is None:
        return 'unknown'
    points = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
              'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    return points[int((bearing % 360) / 22.5 + 0.5) % 16]
