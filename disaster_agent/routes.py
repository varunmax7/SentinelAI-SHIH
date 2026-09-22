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
