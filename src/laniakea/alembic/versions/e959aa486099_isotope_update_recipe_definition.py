"""isotope: Update recipe definition

Revision ID: e959aa486099
Revises: fac701a4ee95
Create Date: 2021-04-12 02:25:55.549332

"""
# flake8: noqa

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e959aa486099'
down_revision = 'fac701a4ee95'
branch_labels = None
depends_on = None


def upgrade():
    postgresql.ENUM('UNKNOWN', 'ISO', 'IMG', name='imageformat', create_type=True).create(op.get_bind())

    op.add_column('image_build_recipes', sa.Column('create_latest_symlink', sa.Boolean(), nullable=True))
    op.add_column('image_build_recipes', sa.Column('environment', sa.Text(), nullable=False))
    op.add_column('image_build_recipes', sa.Column('format', sa.Enum('UNKNOWN', 'ISO', 'IMG', name='imageformat'), nullable=True))
    op.add_column('image_build_recipes', sa.Column('host_architecture', sa.String(length=128), nullable=False))
    op.add_column('image_build_recipes', sa.Column('retain_images_n', sa.Integer(), nullable=True))
    op.add_column('image_build_recipes', sa.Column('style', sa.Text(), nullable=True))
    op.alter_column('image_build_recipes', 'distribution',
               existing_type=sa.TEXT(),
               nullable=False)
    op.alter_column('image_build_recipes', 'git_url',
               existing_type=sa.TEXT(),
               nullable=False)
    op.alter_column('image_build_recipes', 'suite',
               existing_type=sa.TEXT(),
               nullable=False)
    op.drop_column('image_build_recipes', 'kind')
    op.drop_column('image_build_recipes', 'flavor')


def downgrade():
    op.add_column('image_build_recipes', sa.Column('flavor', sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column('image_build_recipes', sa.Column('kind', postgresql.ENUM('UNKNOWN', 'ISO', 'IMG', name='imagekind'), autoincrement=False, nullable=True))
    op.alter_column('image_build_recipes', 'suite',
               existing_type=sa.TEXT(),
               nullable=True)
    op.alter_column('image_build_recipes', 'git_url',
               existing_type=sa.TEXT(),
               nullable=True)
    op.alter_column('image_build_recipes', 'distribution',
               existing_type=sa.TEXT(),
               nullable=True)
    op.drop_column('image_build_recipes', 'style')
    op.drop_column('image_build_recipes', 'retain_images_n')
    op.drop_column('image_build_recipes', 'host_architecture')
    op.drop_column('image_build_recipes', 'format')
    op.drop_column('image_build_recipes', 'environment')
    op.drop_column('image_build_recipes', 'create_latest_symlink')
