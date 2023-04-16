"""Add suite relation to Job

Revision ID: 8e8e17bcda40
Revises: 5c04208d8d76
Create Date: 2023-04-16 16:34:30.335913

"""
# flake8: noqa

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '8e8e17bcda40'
down_revision = '5c04208d8d76'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'idx_pkgs_source_source_id_version', 'archive_pkgs_source', ['source_uuid', 'version'], unique=False
    )
    op.create_index('idx_debcheck_issues_repo', 'debcheck_issues', ['repo_id'], unique=False)
    op.create_index(
        'idx_debcheck_issues_repo_suite_type', 'debcheck_issues', ['package_type', 'repo_id', 'suite_id'], unique=False
    )
    op.add_column('jobs', sa.Column('suite_id', sa.Integer(), nullable=True))
    op.create_index('idx_jobs_status', 'jobs', ['status'], unique=False)
    op.create_index(
        'idx_jobs_status_result_trigger_ver_arch',
        'jobs',
        ['status', 'result', 'trigger', 'version', 'architecture'],
        unique=False,
    )
    op.create_foreign_key(None, 'jobs', 'archive_suites', ['suite_id'], ['id'])


def downgrade():
    op.drop_constraint(None, 'jobs', type_='foreignkey')
    op.drop_index('idx_jobs_status_result_trigger_ver_arch', table_name='jobs')
    op.drop_index('idx_jobs_status', table_name='jobs')
    op.drop_column('jobs', 'suite_id')
    op.drop_index('idx_debcheck_issues_repo_suite_type', table_name='debcheck_issues')
    op.drop_index('idx_debcheck_issues_repo', table_name='debcheck_issues')
    op.drop_index('idx_pkgs_source_source_id_version', table_name='archive_pkgs_source')
