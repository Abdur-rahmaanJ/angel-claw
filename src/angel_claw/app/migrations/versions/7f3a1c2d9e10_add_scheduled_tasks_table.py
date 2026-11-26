"""Add scheduled_tasks table

Revision ID: 7f3a1c2d9e10
Revises: ac5e91f02b7d
Create Date: 2026-11-26 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7f3a1c2d9e10'
down_revision = 'ac5e91f02b7d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scheduled_tasks',
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=False),
        sa.Column('run_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('job_name', sa.String(length=120), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_name'),
    )
    op.create_index(
        op.f('ix_scheduled_tasks_user_id'),
        'scheduled_tasks',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_scheduled_tasks_status'),
        'scheduled_tasks',
        ['status'],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f('ix_scheduled_tasks_status'), table_name='scheduled_tasks')
    op.drop_index(op.f('ix_scheduled_tasks_user_id'), table_name='scheduled_tasks')
    op.drop_table('scheduled_tasks')
