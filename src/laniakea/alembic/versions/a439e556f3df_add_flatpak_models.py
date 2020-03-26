"""add Flatpak models

Revision ID: a439e556f3df
Revises: c19959e673c1
Create Date: 2020-03-26 20:22:26.670139

"""
# flake8: noqa

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import laniakea

# revision identifiers, used by Alembic.
revision = 'a439e556f3df'
down_revision = 'c19959e673c1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('flatpak_repositories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('collection_id', sa.Text(), nullable=True),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('url_homepage', sa.Text(), nullable=True),
    sa.Column('url_icon', sa.Text(), nullable=True),
    sa.Column('default_branch', sa.String(length=128), nullable=True),
    sa.Column('gpg_key_id', sa.Text(), nullable=True),
    sa.Column('allowed_branches', postgresql.ARRAY(sa.String(length=128)), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('collection_id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('flatpak_refs',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('repo_id', sa.Integer(), nullable=True),
    sa.Column('kind', sa.Enum('UNKNOWN', 'APP', 'RUNTIME', name='flatpakrefkind'), nullable=True),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('version', laniakea.db.base.DebVersion(), nullable=True),
    sa.Column('branch', sa.String(length=128), nullable=True),
    sa.Column('commit', postgresql.BYTEA(), nullable=True),
    sa.Column('architecture_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['architecture_id'], ['archive_architectures.id'], ),
    sa.ForeignKeyConstraint(['repo_id'], ['flatpak_repositories.id'], ),
    sa.PrimaryKeyConstraint('uuid')
    )
    op.add_column('archive_sw_components', sa.Column('flatpakref_uuid', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('archive_sw_components', sa.Column('supports_touch', sa.Boolean(), nullable=True))
    op.create_foreign_key(None, 'archive_sw_components', 'flatpak_refs', ['flatpakref_uuid'], ['uuid'])


def downgrade():
    op.drop_constraint(None, 'archive_sw_components', type_='foreignkey')
    op.drop_column('archive_sw_components', 'supports_touch')
    op.drop_column('archive_sw_components', 'flatpakref_uuid')
    op.drop_table('flatpak_refs')
    op.drop_table('flatpak_repositories')
