"""add last_password_change to user

Revision ID: 9b921f46113f
Revises: 03d92055e5c6
Create Date: 2026-04-04 12:18:32.666856

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b921f46113f'
down_revision = '03d92055e5c6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('last_password_change', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'last_password_change')
