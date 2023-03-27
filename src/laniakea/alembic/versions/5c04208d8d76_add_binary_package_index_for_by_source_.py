"""Add binary package index for by source search

Revision ID: 5c04208d8d76
Revises: 2568fcba6520
Create Date: 2023-03-27 23:56:40.472374

"""
# flake8: noqa

from alembic import op

# revision identifiers, used by Alembic.
revision = '5c04208d8d76'
down_revision = '2568fcba6520'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'idx_pkgs_binary_repo_source_arch',
        'archive_pkgs_binary',
        ['repo_id', 'source_id', 'architecture_id'],
        unique=False,
    )


def downgrade():
    op.drop_index('idx_pkgs_binary_repo_source_arch', table_name='archive_pkgs_binary')
