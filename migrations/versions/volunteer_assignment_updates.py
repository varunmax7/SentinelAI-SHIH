"""Add volunteer assignment status and acceptance tracking

Revision ID: volunteer_001
Revises: 8b8777ac801a
Create Date: 2026-01-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'volunteer_001'
down_revision = '8b8777ac801a'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to volunteer_assignments table
    op.add_column('volunteer_assignments', sa.Column('accepted_at', sa.DateTime(), nullable=True))
    op.add_column('volunteer_assignments', sa.Column('distance_km', sa.Float(), nullable=True))
    
    # Modify the status column to allow new values
    # SQLite doesn't support ALTER COLUMN, so we'll just document the change
    # The status column should now accept: pending, accepted, deployed, completed, declined, cancelled


def downgrade():
    # Remove the new columns
    op.drop_column('volunteer_assignments', 'distance_km')
    op.drop_column('volunteer_assignments', 'accepted_at')
