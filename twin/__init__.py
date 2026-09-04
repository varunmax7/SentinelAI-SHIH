"""Urban Digital Twin - a live, queryable spatial model of a city.

Registered into an existing Flask application with one call:

    from twin import create_twin_blueprint
    create_twin_blueprint(app, db, Report, login_required=login_required,
                          scheduler=scheduler)

It adds two blueprints, its own `twin_*` tables and a few jobs on the scheduler
the host already runs. It changes no existing route, model or template
(principle C6 - additive only), so removing the call removes the feature.
"""

from . import config as twin_config
from .models import build_twin_models
from .routes import build_blueprints
from .security import adopt_login_required

__all__ = ['create_twin_blueprint', 'build_twin_models', 'twin_config',
           'twin_models', 'notify_report']

_STATE = {}


def create_twin_blueprint(app, db, Report, login_required=None, scheduler=None,
                          register_jobs=True):
    """Attach the twin to `app`. Returns a dict describing what was registered."""
    if not twin_config.TWIN_ENABLED:
        app.logger.info('Digital Twin disabled (TWIN_ENABLED=0)')
        return {'enabled': False}

    if _STATE.get('registered'):
        return _STATE

    models = build_twin_models(db)

    if login_required is not None:
        adopt_login_required(login_required)

    pages, api = build_blueprints(db, models, Report)
    app.register_blueprint(pages)
    app.register_blueprint(api)

    jobs = []
    if register_jobs and scheduler is not None:
        from .jobs import register_jobs as _register
        jobs = _register(app, scheduler, db, models, Report)

    _STATE.update({
        'enabled': True,
        'registered': True,
        'models': models,
        'blueprints': [pages.name, api.name],
        'jobs': jobs,
    })
    return _STATE


def twin_models():
    """The generated model classes, once the twin has been registered."""
    return _STATE.get('models')


def notify_report(report):
    """Tell every open console that a report just landed.

    The compute pass runs every five minutes, and a *pending* report moves no
    risk score at all, so neither the scheduler nor the risk grid would surface
    a new submission promptly. This pushes an event the moment one is saved, so
    a report filed from a phone shows up on an operator's map in seconds.

    Never raises: a failure to notify must not fail the submission that
    triggered it.
    """
    if not _STATE.get('registered'):
        return
    try:
        if report is None or report.latitude is None or report.longitude is None:
            return
        models = _STATE.get('models')
        for city in models.TwinCity.query.all():
            if city.bbox_min_lon is None:
                continue
            min_lon, min_lat, max_lon, max_lat = city.bbox
            if min_lon <= report.longitude <= max_lon and min_lat <= report.latitude <= max_lat:
                from .stream import publish
                publish(city.slug, 'state', {
                    'city': city.slug,
                    'reason': 'report_submitted',
                    'report_id': report.id,
                    'hazard_type': report.hazard_type,
                    'verification_status': report.verification_status,
                })
                return
    except Exception:  # noqa: BLE001 - C1: never take the app down
        pass
