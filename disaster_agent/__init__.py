"""AI Disaster Prediction Agent.

Watches live wind, cloud and fire-danger signal across a curated grid of
Indian regions - the same class of data the analyst dashboard's three Windy
panels visualise - and predicts which regions are downwind of an elevated
hazard signal, for the next 1/3/6/24 hours. See IMPLEMENTATION.md for the
full three-step design (ingest -> project -> narrate).

Registered into an existing Flask application with one call:

    from disaster_agent import create_disaster_agent_blueprint
    create_disaster_agent_blueprint(app, db, login_required=login_required,
                                    scheduler=scheduler)

Additive only: one blueprint, one table (`disaster_prediction`), one
scheduled job. It touches no existing route, model or template - removing the
call removes the feature.
"""

from . import config as agent_config
from .models import build_prediction_models
from .routes import build_blueprint
from .security import adopt_login_required

__all__ = ['create_disaster_agent_blueprint', 'agent_config']

_STATE = {}


def create_disaster_agent_blueprint(app, db, login_required=None, scheduler=None,
                                    register_jobs=True):
    if not agent_config.AGENT_ENABLED:
        app.logger.info('Disaster Prediction Agent disabled (DISASTER_AGENT_ENABLED=0)')
        return {'enabled': False}

    if _STATE.get('registered'):
        return _STATE

    models = build_prediction_models(db)

    if login_required is not None:
        adopt_login_required(login_required)

    api = build_blueprint(db, models)
    app.register_blueprint(api)

    jobs = []
    if register_jobs and scheduler is not None:
        from .jobs import register_jobs as _register
        jobs = _register(app, scheduler, db, models)

    _STATE.update({
        'enabled': True,
        'registered': True,
        'models': models,
        'blueprint': api.name,
        'jobs': jobs,
    })
    return _STATE


def prediction_models():
    return _STATE.get('models')
