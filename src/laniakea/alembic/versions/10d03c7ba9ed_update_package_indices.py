"""Update package indices

Revision ID: 10d03c7ba9ed
Revises: 28166771d128
Create Date: 2023-02-28 00:38:36.563586

"""
# flake8: noqa

from alembic import op

# revision identifiers, used by Alembic.
revision = '10d03c7ba9ed'
down_revision = '28166771d128'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index('idx_pkgs_binary_repo_arch', table_name='archive_pkgs_binary')
    op.create_index(
        'idx_pkgs_binary_repo_component_arch',
        'archive_pkgs_binary',
        ['repo_id', 'component_id', 'architecture_id', 'time_deleted'],
        unique=False,
    )
    op.create_index(
        'idx_pkgs_source_repo_component',
        'archive_pkgs_source',
        ['repo_id', 'component_id', 'time_deleted'],
        unique=False,
    )
    op.create_index(
        'idx_pkgs_binary_repo_name_version', 'archive_pkgs_binary', ['repo_id', 'name', 'version'], unique=False
    )
    op.create_index(
        'idx_pkgs_source_repo_name_version', 'archive_pkgs_source', ['repo_id', 'name', 'version'], unique=False
    )


def downgrade():
    op.drop_index('idx_pkgs_source_repo_component', table_name='archive_pkgs_source')
    op.drop_index('idx_pkgs_binary_repo_component_arch', table_name='archive_pkgs_binary')
    op.drop_index('idx_pkgs_source_repo_name_version', table_name='archive_pkgs_source')
    op.drop_index('idx_pkgs_binary_repo_name_version', table_name='archive_pkgs_binary')
    op.create_index('idx_pkgs_binary_repo_arch', 'archive_pkgs_binary', ['repo_id', 'architecture_id'], unique=False)
