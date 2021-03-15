"""synchrotron: Multiple sync configurations

Revision ID: b3cc3de026da
Revises: b71d5948f5b7
Create Date: 2019-08-25 02:11:10.030312

"""
# flake8: noqa
# pylint: disable=W,R,C

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from laniakea.db import session_scope, SynchrotronIssue

# revision identifiers, used by Alembic.
revision = 'b3cc3de026da'
down_revision = 'b71d5948f5b7'
branch_labels = None
depends_on = None


def upgrade():
    try:
        with session_scope() as session:
            session.query(SynchrotronIssue).delete()
    except Exception as e:
        pass

    op.create_table('synchrotron_sources',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('os_name', sa.Text(), nullable=False),
    sa.Column('suite_name', sa.String(length=256), nullable=False),
    sa.Column('architectures', postgresql.ARRAY(sa.String(length=64)), nullable=True),
    sa.Column('components', postgresql.ARRAY(sa.String(length=128)), nullable=True),
    sa.Column('repo_url', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('suite_name')
    )
    op.create_table('synchrotron_config',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=True),
    sa.Column('destination_suite_id', sa.Integer(), nullable=True),
    sa.Column('sync_enabled', sa.Boolean(), nullable=True),
    sa.Column('sync_auto_enabled', sa.Boolean(), nullable=True),
    sa.Column('sync_binaries', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['destination_suite_id'], ['archive_suites.id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['synchrotron_sources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('synchrotron_blacklist', sa.Column('config_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'synchrotron_blacklist', 'synchrotron_config', ['config_id'], ['id'])
    op.add_column('synchrotron_issues', sa.Column('config_id', sa.Integer(), nullable=False))
    op.create_foreign_key(None, 'synchrotron_issues', 'synchrotron_config', ['config_id'], ['id'])

    op.execute('DELETE FROM config WHERE id=\'synchrotron.source_name\'')
    op.execute('DELETE FROM config WHERE id=\'synchrotron.source_repo_url\'')
    op.execute('DELETE FROM config WHERE id=\'synchrotron.source_suites\'')
    op.execute('DELETE FROM config WHERE id=\'synchrotron.source_default_suite\'')
    op.execute('DELETE FROM config WHERE id=\'synchrotron.sync_binaries\'')
    op.execute('DELETE FROM config WHERE id=\'synchrotron.sync_enabled\'')


def downgrade():
    op.drop_column('synchrotron_issues', 'config_id')
    op.drop_column('synchrotron_blacklist', 'config_id')
    op.drop_table('synchrotron_config')
    op.drop_table('synchrotron_sources')
