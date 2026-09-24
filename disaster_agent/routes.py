"""JSON API for the analyst dashboard's AI Disaster Prediction panel.

One blueprint, four endpoints. No HTML page of its own - this is consumed by
a panel embedded in the host app's existing `analyst_dashboard.html`.
"""

from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user

from . import config as agent_config
from .security import agent_access_required


def build_blueprint(db, models):
    api = Blueprint('disaster_agent_api', __name__, url_prefix='/api/disaster-agent')

    @api.route('/predictions')
    @agent_access_required()
    def predictions():
        query = (models.DisasterPrediction.query
                 .filter_by(status='active')
                 .order_by(models.DisasterPrediction.risk_score.desc()))

        min_risk = request.args.get('min_risk', type=float)
        if min_risk is not None:
            query = query.filter(models.DisasterPrediction.risk_score >= min_risk)

        hazard_type = request.args.get('hazard_type')
        if hazard_type:
            query = query.filter_by(hazard_type=hazard_type)

        limit = min(request.args.get('limit', 50, type=int) or 50, 200)
        rows = query.limit(limit).all()
        return jsonify({'predictions': [r.to_dict() for r in rows], 'count': len(rows)})

    @api.route('/status')
    @agent_access_required()
    def status():
        latest = (models.DisasterPrediction.query
                  .order_by(models.DisasterPrediction.updated_at.desc())
                  .first())
        active_count = models.DisasterPrediction.query.filter_by(status='active').count()
        return jsonify({
            'enabled': agent_config.AGENT_ENABLED,
            'scheduler_enabled': agent_config.SCHEDULER_ENABLED,
            'cycle_interval_min': agent_config.CYCLE_INTERVAL_MIN,
            'llm_available': agent_config.llm_available(),
            'last_run_at': latest.updated_at.isoformat() if latest and latest.updated_at else None,
            'active_predictions': active_count,
            'horizons_hours': list(agent_config.HORIZONS),
        })

    @api.route('/localities')
    @agent_access_required()
    def localities():
        """Neighbourhood-level alert targets within each watched region.

        Static reference data (see localities.py), fetched once by the
        dashboard and used to populate the "which area exactly" dropdown on
        every hotspot / watch-list card - deliberately not duplicated into
        every prediction/signal payload.
        """
        from .localities import as_json_map
        return jsonify({'localities': as_json_map()})

    @api.route('/signals')
    @agent_access_required()
    def signals():
        """Live per-region hazard strength, regardless of the alert threshold.

        `predictions` only ever shows a hotspot once it clears
        `HOTSPOT_THRESHOLD` - correctly so, an "alert" that fires on every
        cloudy afternoon teaches analysts to ignore it. But that means a quiet
        day renders as a blank panel with no way to tell "nothing is happening"
        from "this is broken". This is the honest middle ground: the raw
        numbers the projection step is working from, always visible, clearly
        separated from an actual hotspot.
        """
        from . import advect, ingest, window as hazard_window

        raw_signals = ingest.fetch_region_signals()
        now = datetime.utcnow()
        by_slug = {s['slug']: s for s in raw_signals}
        ranked = []
        for signal in raw_signals:
            for hazard_type, strength in advect.source_strengths(signal).items():
                targets = advect.downwind_candidates(signal, hazard_type, strength, by_slug)
                # When this signal starts, peaks and is expected to ease -
                # read off the same forecast, scored with the same function
                # that produced `strength`. See window.py.
                span = hazard_window.hazard_window(signal, hazard_type, now=now)
                ranked.append({
                    'window': hazard_window.as_json(span),
                    'window_text': hazard_window.describe(span, hazard_type),
                    'region_slug': signal['slug'],
                    'region_name': signal['name'],
                    'state': signal['state'],
                    'latitude': signal['lat'],
                    'longitude': signal['lon'],
                    'hazard_type': hazard_type,
                    'strength': round(strength, 1),
                    'wind_speed_kmh': signal.get('wind_speed_kmh'),
                    'wind_dir_deg': signal.get('wind_dir_deg'),
                    'cloud_cover_pct': signal.get('cloud_cover_pct'),
                    'fire_weather_index': (
                        round(signal['fire_weather_index'], 1)
                        if signal.get('fire_weather_index') is not None else None),
                    'temperature_c': signal.get('temperature_c'),
                    'possible_targets': [
                        {'slug': t['slug'], 'name': t['name'], 'state': t['state'],
                         'latitude': t['lat'], 'longitude': t['lon'],
                         'horizon_hours': t['horizon_hours']}
                        for t in targets
                    ],
                })
        ranked.sort(key=lambda r: r['strength'], reverse=True)

        limit = min(request.args.get('limit', 8, type=int) or 8, 26)
        return jsonify({
            'signals': ranked[:limit],
            'regions_monitored': len(raw_signals),
            'source_threshold': agent_config.SOURCE_SIGNAL_MIN,
            'hotspot_threshold': agent_config.HOTSPOT_THRESHOLD,
        })

    @api.route('/run', methods=['POST'])
    @agent_access_required()
    def run_now():
        from .agent import run_prediction_cycle
        result = run_prediction_cycle(db, models, now=datetime.utcnow())
        status_code = 200 if result.get('ok') else 502
        return jsonify(result), status_code

    @api.route('/predictions/<int:prediction_id>/dismiss', methods=['POST'])
    @agent_access_required()
    def dismiss(prediction_id):
        row = models.DisasterPrediction.query.get_or_404(prediction_id)
        row.status = 'dismissed'
        row.dismissed_at = datetime.utcnow()
        try:
            row.dismissed_by = current_user.id
        except Exception:  # noqa: BLE001
            pass
        db.session.commit()
        return jsonify({'ok': True, 'id': prediction_id})

    return api
