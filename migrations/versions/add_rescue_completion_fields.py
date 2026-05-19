"""Add rescue completion tracking fields

Revision ID: add_rescue_completion_fields
Revises: add_volunteer_columns_001
Create Date: 2026-01-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_rescue_completion_fields'
down_revision = 'add_volunteer_columns_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to volunteers table
    op.add_column('volunteers', sa.Column('points', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('volunteers', sa.Column('total_rescues', sa.Integer(), nullable=False, server_default='0'))
    
    # Add new columns to volunteer_assignments table
    op.add_column('volunteer_assignments', sa.Column('completion_photo', sa.String(500), nullable=True))
    op.add_column('volunteer_assignments', sa.Column('completion_notes', sa.Text(), nullable=True))
    op.add_column('volunteer_assignments', sa.Column('points_earned', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    # Remove columns from volunteer_assignments table
    op.drop_column('volunteer_assignments', 'points_earned')
    op.drop_column('volunteer_assignments', 'completion_notes')
    op.drop_column('volunteer_assignments', 'completion_photo')
    
    # Remove columns from volunteers table
    op.drop_column('volunteers', 'total_rescues')
    op.drop_column('volunteers', 'points')
