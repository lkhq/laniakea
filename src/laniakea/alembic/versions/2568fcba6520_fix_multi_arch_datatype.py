"""Fix multi-arch datatype

Revision ID: 2568fcba6520
Revises: 4c4d4f6fd252
Create Date: 2023-03-09 00:44:29.965875

"""
# flake8: noqa

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2568fcba6520'
down_revision = '4c4d4f6fd252'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('archive_pkgs_binary', 'multi_arch', type_=sa.String(32))
    op.alter_column('archive_pkg_overrides', 'pkg_name', existing_type=sa.VARCHAR(length=200), nullable=True)
    op.alter_column('archive_queue_new', 'package_uuid', existing_type=postgresql.UUID(), nullable=False)


def downgrade():
    op.alter_column('archive_queue_new', 'package_uuid', existing_type=postgresql.UUID(), nullable=True)
    op.alter_column('archive_pkg_overrides', 'pkg_name', existing_type=sa.VARCHAR(length=200), nullable=False)
