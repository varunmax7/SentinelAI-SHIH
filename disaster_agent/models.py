"""One table, built by a factory bound to the host application's `db`.

Same reasoning as twin/models.py: this package never creates its own
SQLAlchemy instance, so its table lives on the host's metadata and
`db.create_all()` builds it alongside everything else. `build_prediction_models`
is idempotent - calling it twice returns the same class rather than raising
`Table 'disaster_prediction' is already defined`.
"""

from datetime import datetime

_CACHE = {}


class PredictionModels(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def build_prediction_models(db):
    cached = _CACHE.get(id(db))
    if cached is not None:
        return cached

    class DisasterPrediction(db.Model):
        """One row per (region, hazard_type) currently projected as a hotspot.

        Re-run of the cycle updates the row in place (`status='active'`) rather
        than inserting a new one, so the dashboard always shows the latest
        number for a given place-and-hazard rather than an ever-growing list.
        A row the next cycle does not refresh is marked 'expired', not
        deleted, so there is an audit trail of what the agent used to think.
        """

        __tablename__ = 'disaster_prediction'
        __table_args__ = (
            db.Index('ix_disaster_prediction_region_hazard', 'region_slug', 'hazard_type'),
        )

        id = db.Column(db.Integer, primary_key=True)

        region_slug = db.Column(db.String(60), nullable=False)
        region_name = db.Column(db.String(120), nullable=False)
        state = db.Column(db.String(120), nullable=True)
        latitude = db.Column(db.Float, nullable=True)
        longitude = db.Column(db.Float, nullable=True)

        hazard_type = db.Column(db.String(40), nullable=False)
        horizon_hours = db.Column(db.Integer, nullable=False)
        predicted_for = db.Column(db.DateTime, nullable=True)

        risk_score = db.Column(db.Float, default=0.0)
        severity = db.Column(db.String(20), default='low')
        confidence_label = db.Column(db.String(20), default='low')

        headline = db.Column(db.String(240), nullable=True)
        narrative = db.Column(db.Text, nullable=True)
        recommended_action = db.Column(db.Text, nullable=True)
        # JSON list of the contributing source regions and their raw
        # wind/cloud/fire readings - what the drill-down panel renders and
        # what the narrative above is supposed to be traceable to.
        contributing_json = db.Column(db.Text, nullable=True)
        # True when written by the deterministic template because no LLM key
        # was configured or the call failed - the UI must say so, never imply
        # a model wrote a brief it did not.
        generated_offline = db.Column(db.Boolean, default=False)

        status = db.Column(db.String(20), default='active', index=True)  # active | expired | dismissed
        dismissed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
        dismissed_at = db.Column(db.DateTime, nullable=True)

        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

        def contributing_sources(self):
            import json
            if not self.contributing_json:
                return []
            try:
                return json.loads(self.contributing_json)
            except (TypeError, ValueError):
                return []

        def to_dict(self):
            return {
                'id': self.id,
                'region_slug': self.region_slug,
                'region_name': self.region_name,
                'state': self.state,
                'latitude': self.latitude,
                'longitude': self.longitude,
                'hazard_type': self.hazard_type,
                'horizon_hours': self.horizon_hours,
                'predicted_for': self.predicted_for.isoformat() if self.predicted_for else None,
                'risk_score': round(self.risk_score or 0.0, 1),
                'severity': self.severity,
                'confidence_label': self.confidence_label,
                'headline': self.headline,
                'narrative': self.narrative,
                'recommended_action': self.recommended_action,
                'contributing_sources': self.contributing_sources(),
                'generated_offline': self.generated_offline,
                'status': self.status,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            }

    models = PredictionModels(DisasterPrediction=DisasterPrediction)
    _CACHE[id(db)] = models
    return models
