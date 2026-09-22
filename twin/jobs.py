"""Background jobs, registered on the host application's existing scheduler.

The twin never starts a scheduler of its own (principle C6). It is handed the
one the app already runs and adds jobs to it, each with a stable `id` so a
Flask reloader double-import replaces the job rather than stacking a second copy.
"""

from datetime import datetime, timedelta

from . import config as twin_config
from . import engine, seed

COMPUTE_JOB_ID = 'twin_compute'
ALERT_JOB_ID = 'twin_poll_alerts'
AGENT_JOB_ID = 'twin_triage'
WARM_JOB_ID = 'twin_warm_osm'
PRUNE_JOB_ID = 'twin_prune_history'

# History rows older than this are dropped by the weekly prune.
HISTORY_RETENTION_DAYS = 30
# Ingest audit rows are high-volume and only useful recently.
SNAPSHOT_RETENTION_DAYS = 7


def _first_delay(job_id):
    """Stagger first fires so app start is not competing with a full compute
    pass over both cities, an Overpass warm and an LLM run at once."""
    return {
        COMPUTE_JOB_ID: 45,
        ALERT_JOB_ID: 90,
        AGENT_JOB_ID: 150,
    }.get(job_id, 300)


def register_jobs(app, scheduler, db, models, Report):
    if scheduler is None or not twin_config.TWIN_SCHEDULER_ENABLED:
        return []

    def compute():
        with app.app_context():
            try:
                engine.compute_all(db, models, Report)
            except Exception as exc:  # noqa: BLE001 - a job must never kill the scheduler
                app.logger.warning('twin compute failed: %s', exc)
                db.session.rollback()

    def warm_osm():
        """Refresh the slow Overpass-backed layers out of band.

        `/water` and `/cameras` are served cache-only on the request path, so
        this job is the only thing that ever populates them. Without it those
        layers stay honestly empty rather than hanging a dashboard.
        """
        with app.app_context():
            for city in models.TwinCity.query.all():
                try:
                    seed.seed_water(db, models, city)
                    seed.seed_assets(db, models, city)
                    seed.seed_cameras(db, models, city)
                except Exception as exc:  # noqa: BLE001
                    app.logger.warning('twin OSM warm failed for %s: %s', city.slug, exc)
                    db.session.rollback()

    def poll_alerts():
        """Pull the official alert feeds. Runs whether or not the agent is on -
        putting real IMD warnings on the map needs no LLM at all."""
        with app.app_context():
            try:
                from . import alerts as alert_service
                alert_service.poll_alerts(db, models)
            except Exception as exc:  # noqa: BLE001
                app.logger.warning('twin alert poll failed: %s', exc)
                db.session.rollback()

    def run_triage():
        with app.app_context():
            try:
                from .agent import run_triage as _run
                _run(db, models)
            except Exception as exc:  # noqa: BLE001
                app.logger.warning('twin triage failed: %s', exc)
                db.session.rollback()

    def prune():
        with app.app_context():
            try:
                now = datetime.utcnow()
                (models.TwinCellHistory.query
                 .filter(models.TwinCellHistory.recorded_at
                         < now - timedelta(days=HISTORY_RETENTION_DAYS))
                 .delete(synchronize_session=False))
                (models.TwinDataSnapshot.query
                 .filter(models.TwinDataSnapshot.created_at
                         < now - timedelta(days=SNAPSHOT_RETENTION_DAYS))
                 .delete(synchronize_session=False))
                db.session.commit()
            except Exception as exc:  # noqa: BLE001
                app.logger.warning('twin prune failed: %s', exc)
                db.session.rollback()

    registered = []
    schedule = [
        (COMPUTE_JOB_ID, compute, twin_config.COMPUTE_INTERVAL_MIN),
        (ALERT_JOB_ID, poll_alerts, twin_config.ALERT_POLL_MIN),
        (WARM_JOB_ID, warm_osm, 24 * 60),
        (PRUNE_JOB_ID, prune, 7 * 24 * 60),
    ]
    # Only scheduled when the agent is switched on. With TWIN_AGENT_ENABLED=0
    # the job does not exist at all - not a job that wakes up and returns early.
    if twin_config.AGENT_ENABLED:
        schedule.append((AGENT_JOB_ID, run_triage, twin_config.ALERT_POLL_MIN * 2))

    for job_id, func, minutes in schedule:
        try:
            scheduler.add_job(
                func=func,
                trigger='interval',
                minutes=minutes,
                id=job_id,
                replace_existing=True,
                # Skip a run entirely rather than queueing catch-ups: a compute
                # pass that overran is never worth running twice back to back.
                coalesce=True,
                max_instances=1,
                # Stagger the first fire so app start is not competing with a
                # full compute pass over both cities.
                next_run_time=datetime.now() + timedelta(seconds=_first_delay(job_id)),
            )
            registered.append(job_id)
        except Exception as exc:  # noqa: BLE001
            app.logger.warning('could not register twin job %s: %s', job_id, exc)
    return registered
