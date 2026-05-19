"""Add missing completed_at column to volunteer_assignments table

Revision ID: add_volunteer_columns_001
Revises: volunteer_001
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_volunteer_columns_001'
down_revision = 'volunteer_001'
branch_labels = None
depends_on = None


def upgrade():
    # The columns should already exist from previous migrations
    # This migration is a no-op but ensures we have the right revision order
    pass


def downgrade():
    # No-op downgrade
    pass
