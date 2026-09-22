"""Background job, registered on the host application's existing scheduler.

Same rule as twin/jobs.py: this package never starts a scheduler of its own,
it only adds one job, with a stable id, to the one the host already runs.
"""

from datetime import datetime, timedelta

from . import config as agent_config

CYCLE_JOB_ID = 'disaster_agent_cycle'
FIRST_RUN_DELAY_S = 60


def register_jobs(app, scheduler, db, models):
    if scheduler is None or not agent_config.SCHEDULER_ENABLED or not agent_config.AGENT_ENABLED:
        return []

    def run_cycle():
        with app.app_context():
            try:
                from .agent import run_prediction_cycle
                result = run_prediction_cycle(db, models)
                if not result.get('ok'):
                    app.logger.warning('disaster agent cycle failed at %s: %s',
                                       result.get('stage'), result.get('error'))
            except Exception as exc:  # noqa: BLE001 - a job must never kill the scheduler
                app.logger.warning('disaster agent cycle failed: %s', exc)
                db.session.rollback()

    try:
        scheduler.add_job(
            func=run_cycle,
            trigger='interval',
            minutes=agent_config.CYCLE_INTERVAL_MIN,
            id=CYCLE_JOB_ID,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            next_run_time=datetime.now() + timedelta(seconds=FIRST_RUN_DELAY_S),
        )
        return [CYCLE_JOB_ID]
    except Exception as exc:  # noqa: BLE001
        app.logger.warning('could not register disaster agent job: %s', exc)
        return []
