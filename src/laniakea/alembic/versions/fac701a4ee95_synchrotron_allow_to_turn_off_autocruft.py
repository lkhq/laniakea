"""synchrotron: Allow to turn off autocruft

Revision ID: fac701a4ee95
Revises: a439e556f3df
Create Date: 2020-06-10 21:36:21.493537

"""
# flake8: noqa

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fac701a4ee95'
down_revision = 'a439e556f3df'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('synchrotron_config', sa.Column('auto_cruft_remove', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('synchrotron_config', 'auto_cruft_remove')
