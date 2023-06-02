"""Add statistics

Revision ID: e50fdc2c5c80
Revises: 6fc763140941
Create Date: 2023-06-03 00:47:32.752604

"""
# flake8: noqa

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e50fdc2c5c80'
down_revision = '6fc763140941'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'statistics',
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('time', sa.DateTime(), nullable=False),
        sa.Column('value', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('key', 'time'),
    )


def downgrade():
    op.drop_table('statistics')
