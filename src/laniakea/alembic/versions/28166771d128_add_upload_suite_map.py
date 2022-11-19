"""Add upload suite map

Revision ID: 28166771d128
Revises: 34ccc7e6f9b8
Create Date: 2022-11-19 14:39:48.897814

"""
# flake8: noqa

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '28166771d128'
down_revision = '34ccc7e6f9b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'archive_repositories', sa.Column('upload_suite_map', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade():
    op.drop_column('archive_repositories', 'upload_suite_map')
