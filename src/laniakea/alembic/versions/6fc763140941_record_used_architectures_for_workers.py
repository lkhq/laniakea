"""Record used architectures for workers

Revision ID: 6fc763140941
Revises: 34ccc7e6f9b8
Create Date: 2023-05-21 21:42:55.220551

"""
# flake8: noqa

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6fc763140941'
down_revision = '34ccc7e6f9b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('spark_workers', sa.Column('architectures', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('spark_workers', sa.Column('data', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.drop_column('spark_workers', 'last_job')


def downgrade():
    op.add_column('spark_workers', sa.Column('last_job', postgresql.UUID(), autoincrement=False, nullable=True))
    op.drop_column('spark_workers', 'data')
    op.drop_column('spark_workers', 'architectures')
