"""Add the hazard-window columns to disaster_prediction.

The watch list could say how strong a signal is but not how long it lasts, so
`disaster_agent/window.py` now re-scores the hourly forecast to derive when a
hazard starts, peaks and is expected to ease. These columns store that result
alongside the prediction it belongs to.

`window_ends_at` is nullable on purpose and NULL carries meaning: together
with `window_open_ended = 1` it says the signal is still above threshold at
the end of the available forecast, so no end time exists. Rendering that as
"no end time" rather than as an all-clear is the point.

Revision ID: a7c41d9b3e20
Revises: ec15d6b69125
"""

import sqlalchemy as sa
from alembic import op

revision = 'a7c41d9b3e20'
down_revision = 'ec15d6b69125'
branch_labels = None
depends_on = None

_COLUMNS = (
    ('window_state', sa.String(length=20)),
    ('window_starts_at', sa.DateTime()),
    ('window_ends_at', sa.DateTime()),
    ('window_peak_at', sa.DateTime()),
    ('window_peak_strength', sa.Float()),
    ('window_open_ended', sa.Boolean()),
    ('window_text', sa.Text()),
)


def _existing():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'disaster_prediction' not in inspector.get_table_names():
        return None
    return {c['name'] for c in inspector.get_columns('disaster_prediction')}


def upgrade():
    # The table is created by `db.create_all()` from a model factory rather
    # than by a migration, so on a fresh database it may already carry these
    # columns. Adding one that exists is an error on every backend, so each is
    # checked first - this migration has to be safe on both an old database
    # and a brand-new one.
    existing = _existing()
    if existing is None:
        return
    with op.batch_alter_table('disaster_prediction') as batch:
        for name, column_type in _COLUMNS:
            if name not in existing:
                batch.add_column(sa.Column(name, column_type, nullable=True))


def downgrade():
    existing = _existing()
    if existing is None:
        return
    with op.batch_alter_table('disaster_prediction') as batch:
        for name, _type in _COLUMNS:
            if name in existing:
                batch.drop_column(name)
