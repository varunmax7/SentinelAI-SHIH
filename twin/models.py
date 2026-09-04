"""Twin ORM models, built by a factory bound to the host application's `db`.

The twin never creates its own SQLAlchemy instance. It is registered *into* an
existing app (principle C6 — additive only), so its tables have to live on the
host's metadata or `db.create_all()` would not build them and relationships
across to `Report`/`User` would not resolve.

`build_twin_models(db)` is idempotent: calling it twice returns the same classes
rather than raising `Table 'twin_cell' is already defined`.
"""

import json
from datetime import datetime

_CACHE = {}


class TwinModels(object):
    """Plain namespace holding the generated model classes."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def all_models(self):
        return [v for v in self.__dict__.values() if hasattr(v, '__tablename__')]


def build_twin_models(db):
    cached = _CACHE.get(id(db))
    if cached is not None:
        return cached

    class TwinCity(db.Model):
        __tablename__ = 'twin_city'

        id = db.Column(db.Integer, primary_key=True)
        slug = db.Column(db.String(40), unique=True, nullable=False, index=True)
        name = db.Column(db.String(80), nullable=False)
        state = db.Column(db.String(80), nullable=True)

        center_latitude = db.Column(db.Float, nullable=False)
        center_longitude = db.Column(db.Float, nullable=False)
        bbox_min_lon = db.Column(db.Float, nullable=True)
        bbox_min_lat = db.Column(db.Float, nullable=True)
        bbox_max_lon = db.Column(db.Float, nullable=True)
        bbox_max_lat = db.Column(db.Float, nullable=True)

        default_zoom = db.Column(db.Float, default=10.6)
        default_pitch = db.Column(db.Float, default=45.0)
        default_bearing = db.Column(db.Float, default=-12.5)
        h3_resolution = db.Column(db.Integer, default=8)

        last_computed_at = db.Column(db.DateTime, nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

        zones = db.relationship('TwinZone', backref='city', lazy='dynamic',
                                cascade='all, delete-orphan')
        cells = db.relationship('TwinCell', backref='city', lazy='dynamic',
                                cascade='all, delete-orphan')

        @property
        def bbox(self):
            return (self.bbox_min_lon, self.bbox_min_lat,
                    self.bbox_max_lon, self.bbox_max_lat)

        def camera_config(self):
            return {
                'center': [self.center_longitude, self.center_latitude],
                'zoom': self.default_zoom,
                'pitch': self.default_pitch,
                'bearing': self.default_bearing,
            }

        def __repr__(self):
            return "<TwinCity %s>" % self.slug

    class TwinZone(db.Model):
        __tablename__ = 'twin_zone'
        __table_args__ = (db.UniqueConstraint('city_id', 'slug', name='uq_twin_zone_city_slug'),)

        id = db.Column(db.Integer, primary_key=True)
        city_id = db.Column(db.Integer, db.ForeignKey('twin_city.id'), nullable=False, index=True)
        slug = db.Column(db.String(60), nullable=False)
        name = db.Column(db.String(120), nullable=False)
        center_latitude = db.Column(db.Float, nullable=False)
        center_longitude = db.Column(db.Float, nullable=False)
        boundary_geojson = db.Column(db.Text, nullable=True)
        # 'approximate' means a synthesised hull, not a surveyed boundary. The
        # UI is required to say so - honesty over polish.
        boundary_source = db.Column(db.String(30), default='approximate')

        def boundary(self):
            if not self.boundary_geojson:
                return None
            try:
                return json.loads(self.boundary_geojson)
            except (TypeError, ValueError):
                return None

        def __repr__(self):
            return "<TwinZone %s>" % self.slug

    class TwinCell(db.Model):
        __tablename__ = 'twin_cell'

        id = db.Column(db.Integer, primary_key=True)
        h3_index = db.Column(db.String(20), unique=True, nullable=False, index=True)
        city_id = db.Column(db.Integer, db.ForeignKey('twin_city.id'), nullable=False, index=True)
        zone_id = db.Column(db.Integer, db.ForeignKey('twin_zone.id'), nullable=True, index=True)

        center_latitude = db.Column(db.Float, nullable=False)
        center_longitude = db.Column(db.Float, nullable=False)
        boundary_geojson = db.Column(db.Text, nullable=True)
        area_km2 = db.Column(db.Float, nullable=True)

        # Static terrain/vulnerability inputs, filled at seed time and refreshed
        # by the Overpass ingest.
        elevation_m = db.Column(db.Float, nullable=True)
        dist_to_water_m = db.Column(db.Float, nullable=True)
        drain_length_m = db.Column(db.Float, default=0.0)
        camera_count = db.Column(db.Integer, default=0)

        zone = db.relationship('TwinZone', backref=db.backref('cells', lazy='dynamic'))
        states = db.relationship('TwinCellState', backref='cell', lazy='dynamic',
                                 cascade='all, delete-orphan')

        def boundary_ring(self):
            if not self.boundary_geojson:
                return None
            try:
                return json.loads(self.boundary_geojson)
            except (TypeError, ValueError):
                return None

        def __repr__(self):
            return "<TwinCell %s>" % self.h3_index

    class TwinCellState(db.Model):
        """Risk for one cell at one horizon. Overwritten in place each compute."""

        __tablename__ = 'twin_cell_state'
        __table_args__ = (
            db.UniqueConstraint('cell_id', 'horizon_hours', name='uq_twin_state_cell_horizon'),
        )

        id = db.Column(db.Integer, primary_key=True)
        cell_id = db.Column(db.Integer, db.ForeignKey('twin_cell.id'), nullable=False, index=True)
        horizon_hours = db.Column(db.Integer, nullable=False, default=0, index=True)

        risk_score = db.Column(db.Float, default=0.0)
        status = db.Column(db.String(20), default='normal', index=True)

        hydro_score = db.Column(db.Float, default=0.0)
        incident_score = db.Column(db.Float, default=0.0)
        env_score = db.Column(db.Float, default=0.0)
        terrain_score = db.Column(db.Float, default=0.0)
        infra_score = db.Column(db.Float, default=0.0)

        # C3 - show your working. Every score carries the inputs that made it.
        raw_inputs = db.Column(db.Text, nullable=True)
        # True when any contributing source was degraded. Drawn as a dashed
        # amber outline: officials must be able to see when the twin is guessing.
        degraded_inputs = db.Column(db.Boolean, default=False)

        computed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

        def inputs(self):
            if not self.raw_inputs:
                return {}
            try:
                return json.loads(self.raw_inputs)
            except (TypeError, ValueError):
                return {}

    class TwinCellHistory(db.Model):
        """Append-only risk time series, for the timeline chart and back-testing."""

        __tablename__ = 'twin_cell_history'

        id = db.Column(db.Integer, primary_key=True)
        cell_id = db.Column(db.Integer, db.ForeignKey('twin_cell.id'), nullable=False, index=True)
        horizon_hours = db.Column(db.Integer, nullable=False, default=0)
        risk_score = db.Column(db.Float, default=0.0)
        status = db.Column(db.String(20), default='normal')
        recorded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    class TwinInfrastructure(db.Model):
        __tablename__ = 'twin_infrastructure'

        id = db.Column(db.Integer, primary_key=True)
        city_id = db.Column(db.Integer, db.ForeignKey('twin_city.id'), nullable=False, index=True)
        cell_id = db.Column(db.Integer, db.ForeignKey('twin_cell.id'), nullable=True, index=True)
        osm_id = db.Column(db.String(40), nullable=True, index=True)
        asset_type = db.Column(db.String(40), nullable=False)
        name = db.Column(db.String(160), nullable=True)
        criticality = db.Column(db.Integer, default=1)
        latitude = db.Column(db.Float, nullable=False)
        longitude = db.Column(db.Float, nullable=False)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    class TwinDataSnapshot(db.Model):
        """One row per ingest attempt. C7 - audit everything."""

        __tablename__ = 'twin_data_snapshot'

        id = db.Column(db.Integer, primary_key=True)
        city_id = db.Column(db.Integer, db.ForeignKey('twin_city.id'), nullable=True, index=True)
        source_key = db.Column(db.String(60), nullable=False, index=True)
        status = db.Column(db.String(20), default='ok')  # ok | degraded | failed | cached
        latency_ms = db.Column(db.Integer, default=0)
        records_ingested = db.Column(db.Integer, default=0)
        error_message = db.Column(db.Text, nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    models = TwinModels(
        TwinCity=TwinCity,
        TwinZone=TwinZone,
        TwinCell=TwinCell,
        TwinCellState=TwinCellState,
        TwinCellHistory=TwinCellHistory,
        TwinInfrastructure=TwinInfrastructure,
        TwinDataSnapshot=TwinDataSnapshot,
    )
    _CACHE[id(db)] = models
    return models
