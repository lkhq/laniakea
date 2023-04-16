"""Rename software components table

Revision ID: 334556f6c022
Revises: 8e8e17bcda40
Create Date: 2023-04-16 20:12:41.165419

"""
# flake8: noqa

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '334556f6c022'
down_revision = '8e8e17bcda40'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'software_components',
        sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kind', sa.Integer(), nullable=True),
        sa.Column('cid', sa.Text(), nullable=False),
        sa.Column('gcid', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon_name', sa.String(length=200), nullable=True),
        sa.Column('is_free', sa.Boolean(), nullable=True),
        sa.Column('project_license', sa.Text(), nullable=True),
        sa.Column('developer_name', sa.Text(), nullable=True),
        sa.Column('supports_touch', sa.Boolean(), nullable=True),
        sa.Column('categories', postgresql.ARRAY(sa.String(length=100)), nullable=True),
        sa.Column('flatpakref_uuid', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ['flatpakref_uuid'],
            ['flatpak_refs.uuid'],
        ),
        sa.PrimaryKeyConstraint('uuid'),
    )
    op.drop_constraint(
        'archive_swcpt_binpkg_association_sw_cpt_uuid_fkey', 'archive_swcpt_binpkg_association', type_='foreignkey'
    )
    op.create_foreign_key(
        None, 'archive_swcpt_binpkg_association', 'software_components', ['sw_cpt_uuid'], ['uuid'], ondelete='cascade'
    )
    op.drop_table('archive_sw_components')


def downgrade():
    op.drop_constraint(None, 'archive_swcpt_binpkg_association', type_='foreignkey')
    op.create_foreign_key(
        'archive_swcpt_binpkg_association_sw_cpt_uuid_fkey',
        'archive_swcpt_binpkg_association',
        'archive_sw_components',
        ['sw_cpt_uuid'],
        ['uuid'],
        ondelete='CASCADE',
    )
    op.create_table(
        'archive_sw_components',
        sa.Column('uuid', postgresql.UUID(), autoincrement=False, nullable=False),
        sa.Column('kind', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('cid', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('gcid', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('name', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('summary', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('icon_name', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
        sa.Column('is_free', sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column('project_license', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('developer_name', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('supports_touch', sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column('categories', postgresql.ARRAY(sa.VARCHAR(length=100)), autoincrement=False, nullable=True),
        sa.Column('flatpakref_uuid', postgresql.UUID(), autoincrement=False, nullable=True),
        sa.Column('data', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(
            ['flatpakref_uuid'], ['flatpak_refs.uuid'], name='archive_sw_components_flatpakref_uuid_fkey'
        ),
        sa.PrimaryKeyConstraint('uuid', name='archive_sw_components_pkey'),
    )
    op.drop_table('software_components')
