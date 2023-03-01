"""Make VersionMemory aware of suites

Revision ID: ec0445328615
Revises: 10d03c7ba9ed
Create Date: 2023-03-01 15:55:25.773046

"""
# flake8: noqa

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'ec0445328615'
down_revision = '10d03c7ba9ed'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('archive_pkg_version_memory', sa.Column('repo_suite_id', sa.Integer(), nullable=False))
    op.add_column(
        'archive_pkg_version_memory',
        sa.Column('pkg_type', sa.Enum('UNKNOWN', 'SOURCE', 'BINARY', name='packagetype'), nullable=True),
    )
    op.add_column('archive_pkg_version_memory', sa.Column('pkg_name', sa.String(length=200), nullable=True))
    op.drop_constraint('_pkgname_repo_uc', 'archive_pkg_version_memory', type_='unique')
    op.create_unique_constraint('_rss_pkg_uc', 'archive_pkg_version_memory', ['repo_suite_id', 'pkg_type', 'pkg_name'])
    op.drop_constraint('archive_pkg_version_memory_repo_id_fkey', 'archive_pkg_version_memory', type_='foreignkey')
    op.create_foreign_key(None, 'archive_pkg_version_memory', 'archive_repo_suite_settings', ['repo_suite_id'], ['id'])
    op.drop_column('archive_pkg_version_memory', 'repo_id')
    op.drop_column('archive_pkg_version_memory', 'pkgname')


def downgrade():
    op.add_column(
        'archive_pkg_version_memory', sa.Column('pkgname', sa.VARCHAR(length=200), autoincrement=False, nullable=True)
    )
    op.add_column('archive_pkg_version_memory', sa.Column('repo_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'archive_pkg_version_memory', type_='foreignkey')
    op.create_foreign_key(
        'archive_pkg_version_memory_repo_id_fkey',
        'archive_pkg_version_memory',
        'archive_repositories',
        ['repo_id'],
        ['id'],
    )
    op.drop_constraint('_rss_pkg_uc', 'archive_pkg_version_memory', type_='unique')
    op.create_unique_constraint('_pkgname_repo_uc', 'archive_pkg_version_memory', ['pkgname', 'repo_id'])
    op.drop_column('archive_pkg_version_memory', 'pkg_name')
    op.drop_column('archive_pkg_version_memory', 'pkg_type')
    op.drop_column('archive_pkg_version_memory', 'repo_suite_id')
