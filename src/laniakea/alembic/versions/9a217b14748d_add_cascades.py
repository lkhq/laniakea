"""Add cascades

Revision ID: 9a217b14748d
Revises: b3cc3de026da
Create Date: 2019-08-30 19:11:48.347206

"""
# flake8: noqa

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a217b14748d'
down_revision = 'b3cc3de026da'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('archive_binpkg_suite_association_bin_package_uuid_fkey', 'archive_binpkg_suite_association', type_='foreignkey')
    op.drop_constraint('archive_binpkg_suite_association_suite_id_fkey', 'archive_binpkg_suite_association', type_='foreignkey')
    op.create_foreign_key(None, 'archive_binpkg_suite_association', 'archive_bin_packages', ['bin_package_uuid'], ['uuid'], ondelete='cascade')
    op.create_foreign_key(None, 'archive_binpkg_suite_association', 'archive_suites', ['suite_id'], ['id'], ondelete='cascade')
    op.drop_constraint('archive_repo_suite_association_suite_id_fkey', 'archive_repo_suite_association', type_='foreignkey')
    op.drop_constraint('archive_repo_suite_association_repo_id_fkey', 'archive_repo_suite_association', type_='foreignkey')
    op.create_foreign_key(None, 'archive_repo_suite_association', 'archive_suites', ['suite_id'], ['id'], ondelete='cascade')
    op.create_foreign_key(None, 'archive_repo_suite_association', 'archive_repositories', ['repo_id'], ['id'], ondelete='cascade')
    op.drop_constraint('archive_srcpkg_suite_association_src_package_uuid_fkey', 'archive_srcpkg_suite_association', type_='foreignkey')
    op.drop_constraint('archive_srcpkg_suite_association_suite_id_fkey', 'archive_srcpkg_suite_association', type_='foreignkey')
    op.create_foreign_key(None, 'archive_srcpkg_suite_association', 'archive_src_packages', ['src_package_uuid'], ['uuid'], ondelete='cascade')
    op.create_foreign_key(None, 'archive_srcpkg_suite_association', 'archive_suites', ['suite_id'], ['id'], ondelete='cascade')
    op.drop_constraint('archive_suite_architecture_association_suite_id_fkey', 'archive_suite_architecture_association', type_='foreignkey')
    op.drop_constraint('archive_suite_architecture_association_arch_id_fkey', 'archive_suite_architecture_association', type_='foreignkey')
    op.create_foreign_key(None, 'archive_suite_architecture_association', 'archive_suites', ['suite_id'], ['id'], ondelete='cascade')
    op.create_foreign_key(None, 'archive_suite_architecture_association', 'archive_architectures', ['arch_id'], ['id'], ondelete='cascade')
    op.drop_constraint('archive_suite_component_association_component_id_fkey', 'archive_suite_component_association', type_='foreignkey')
    op.drop_constraint('archive_suite_component_association_suite_id_fkey', 'archive_suite_component_association', type_='foreignkey')
    op.create_foreign_key(None, 'archive_suite_component_association', 'archive_components', ['component_id'], ['id'], ondelete='cascade')
    op.create_foreign_key(None, 'archive_suite_component_association', 'archive_suites', ['suite_id'], ['id'], ondelete='cascade')
    op.drop_constraint('archive_swcpt_binpkg_association_sw_cpt_uuid_fkey', 'archive_swcpt_binpkg_association', type_='foreignkey')
    op.drop_constraint('archive_swcpt_binpkg_association_bin_package_uuid_fkey', 'archive_swcpt_binpkg_association', type_='foreignkey')
    op.create_foreign_key(None, 'archive_swcpt_binpkg_association', 'archive_sw_components', ['sw_cpt_uuid'], ['uuid'], ondelete='cascade')
    op.create_foreign_key(None, 'archive_swcpt_binpkg_association', 'archive_bin_packages', ['bin_package_uuid'], ['uuid'], ondelete='cascade')
    op.drop_constraint('debcheck_issues_suite_id_fkey', 'debcheck_issues', type_='foreignkey')
    op.create_foreign_key(None, 'debcheck_issues', 'archive_suites', ['suite_id'], ['id'], ondelete='cascade')


def downgrade():
    op.drop_constraint(None, 'archive_swcpt_binpkg_association', type_='foreignkey')
    op.drop_constraint(None, 'archive_swcpt_binpkg_association', type_='foreignkey')
    op.create_foreign_key('archive_swcpt_binpkg_association_bin_package_uuid_fkey', 'archive_swcpt_binpkg_association', 'archive_bin_packages', ['bin_package_uuid'], ['uuid'])
    op.create_foreign_key('archive_swcpt_binpkg_association_sw_cpt_uuid_fkey', 'archive_swcpt_binpkg_association', 'archive_sw_components', ['sw_cpt_uuid'], ['uuid'])
    op.drop_constraint(None, 'archive_suite_component_association', type_='foreignkey')
    op.drop_constraint(None, 'archive_suite_component_association', type_='foreignkey')
    op.create_foreign_key('archive_suite_component_association_suite_id_fkey', 'archive_suite_component_association', 'archive_suites', ['suite_id'], ['id'])
    op.create_foreign_key('archive_suite_component_association_component_id_fkey', 'archive_suite_component_association', 'archive_components', ['component_id'], ['id'])
    op.drop_constraint(None, 'archive_suite_architecture_association', type_='foreignkey')
    op.drop_constraint(None, 'archive_suite_architecture_association', type_='foreignkey')
    op.create_foreign_key('archive_suite_architecture_association_arch_id_fkey', 'archive_suite_architecture_association', 'archive_architectures', ['arch_id'], ['id'])
    op.create_foreign_key('archive_suite_architecture_association_suite_id_fkey', 'archive_suite_architecture_association', 'archive_suites', ['suite_id'], ['id'])
    op.drop_constraint(None, 'archive_srcpkg_suite_association', type_='foreignkey')
    op.drop_constraint(None, 'archive_srcpkg_suite_association', type_='foreignkey')
    op.create_foreign_key('archive_srcpkg_suite_association_suite_id_fkey', 'archive_srcpkg_suite_association', 'archive_suites', ['suite_id'], ['id'])
    op.create_foreign_key('archive_srcpkg_suite_association_src_package_uuid_fkey', 'archive_srcpkg_suite_association', 'archive_src_packages', ['src_package_uuid'], ['uuid'])
    op.drop_constraint(None, 'archive_repo_suite_association', type_='foreignkey')
    op.drop_constraint(None, 'archive_repo_suite_association', type_='foreignkey')
    op.create_foreign_key('archive_repo_suite_association_repo_id_fkey', 'archive_repo_suite_association', 'archive_repositories', ['repo_id'], ['id'])
    op.create_foreign_key('archive_repo_suite_association_suite_id_fkey', 'archive_repo_suite_association', 'archive_suites', ['suite_id'], ['id'])
    op.drop_constraint(None, 'archive_binpkg_suite_association', type_='foreignkey')
    op.drop_constraint(None, 'archive_binpkg_suite_association', type_='foreignkey')
    op.create_foreign_key('archive_binpkg_suite_association_suite_id_fkey', 'archive_binpkg_suite_association', 'archive_suites', ['suite_id'], ['id'])
    op.create_foreign_key('archive_binpkg_suite_association_bin_package_uuid_fkey', 'archive_binpkg_suite_association', 'archive_bin_packages', ['bin_package_uuid'], ['uuid'])
    op.drop_constraint(None, 'debcheck_issues', type_='foreignkey')
    op.create_foreign_key('debcheck_issues_suite_id_fkey', 'debcheck_issues', 'archive_suites', ['suite_id'], ['id'])
