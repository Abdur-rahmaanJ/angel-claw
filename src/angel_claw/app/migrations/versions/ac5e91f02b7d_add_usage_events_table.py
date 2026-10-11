"""Add usage_events table

Revision ID: ac5e91f02b7d
Revises: 9cce5396954e
Create Date: 2026-10-11 17:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ac5e91f02b7d'
down_revision = '9cce5396954e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'usage_events',
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('app', sa.String(length=100), nullable=False),
        sa.Column('event', sa.String(length=100), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('reported_by', sa.String(length=100), nullable=True),
        sa.Column('meta_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_usage_events_user_id'), 'usage_events', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_usage_events_user_id'), table_name='usage_events')
    op.drop_table('usage_events')
