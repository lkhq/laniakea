"""Add arch awareness to VersionMemory

Revision ID: a5281c40b748
Revises: ec0445328615
Create Date: 2023-03-06 11:48:10.655201

"""
# flake8: noqa

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a5281c40b748'
down_revision = 'ec0445328615'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('archive_pkg_version_memory', sa.Column('arch_name', sa.String(length=80), nullable=False))
    op.alter_column('archive_pkg_version_memory', 'pkg_name', existing_type=sa.VARCHAR(length=200), nullable=False)
    op.drop_constraint('_rss_pkg_uc', 'archive_pkg_version_memory', type_='unique')
    op.create_unique_constraint('_rss_pkg_uc', 'archive_pkg_version_memory', ['repo_suite_id', 'pkg_name', 'arch_name'])
    op.drop_column('archive_pkg_version_memory', 'pkg_type')


def downgrade():
    op.add_column(
        'archive_pkg_version_memory',
        sa.Column(
            'pkg_type',
            postgresql.ENUM('UNKNOWN', 'SOURCE', 'BINARY', name='packagetype'),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.drop_constraint('_rss_pkg_uc', 'archive_pkg_version_memory', type_='unique')
    op.create_unique_constraint('_rss_pkg_uc', 'archive_pkg_version_memory', ['repo_suite_id', 'pkg_type', 'pkg_name'])
    op.alter_column('archive_pkg_version_memory', 'pkg_name', existing_type=sa.VARCHAR(length=200), nullable=True)
    op.drop_column('archive_pkg_version_memory', 'arch_name')
