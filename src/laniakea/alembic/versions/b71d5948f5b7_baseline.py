"""baseline

Revision ID: b71d5948f5b7
Revises: -
Create Date: 2019-08-24 17:23:22.604954

"""
# flake8: noqa

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import laniakea

# revision identifiers, used by Alembic.
revision = 'b71d5948f5b7'
down_revision = '34ccc7e6f9b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('archive_architectures',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('summary', sa.String(length=256), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('archive_components',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('parent_component_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['parent_component_id'], ['archive_components.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('archive_repositories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('archive_suites',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('accept_uploads', sa.Boolean(), nullable=True),
    sa.Column('devel_target', sa.Boolean(), nullable=True),
    sa.Column('frozen', sa.Boolean(), nullable=True),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['archive_suites.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('archive_sw_components',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('kind', sa.Integer(), nullable=True),
    sa.Column('cid', sa.Text(), nullable=True),
    sa.Column('gcid', sa.Text(), nullable=True),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icon_name', sa.String(length=256), nullable=True),
    sa.Column('project_license', sa.Text(), nullable=True),
    sa.Column('developer_name', sa.Text(), nullable=True),
    sa.Column('categories', postgresql.ARRAY(sa.String(length=256)), nullable=True),
    sa.Column('xml', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('uuid')
    )
    op.create_table('config',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('value', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('image_build_recipes',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('kind', sa.Enum('UNKNOWN', 'ISO', 'IMG', name='imagekind'), nullable=True),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('distribution', sa.Text(), nullable=True),
    sa.Column('suite', sa.Text(), nullable=True),
    sa.Column('flavor', sa.Text(), nullable=True),
    sa.Column('architectures', postgresql.ARRAY(sa.String(length=128)), nullable=True),
    sa.Column('git_url', sa.Text(), nullable=True),
    sa.Column('result_move_to', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('uuid'),
    sa.UniqueConstraint('name')
    )
    op.create_table('jobs',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('status', sa.Enum('UNKNOWN', 'WAITING', 'DEPWAIT', 'SCHEDULED', 'RUNNING', 'DONE', 'TERMINATED', 'STARVING', name='jobstatus'), nullable=True),
    sa.Column('module', sa.String(length=256), nullable=False),
    sa.Column('kind', sa.String(length=256), nullable=False),
    sa.Column('trigger', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('version', laniakea.db.base.DebVersion(), nullable=True),
    sa.Column('architecture', sa.Text(), nullable=True),
    sa.Column('time_created', sa.DateTime(), nullable=True),
    sa.Column('time_assigned', sa.DateTime(), nullable=True),
    sa.Column('time_finished', sa.DateTime(), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('worker', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('result', sa.Enum('UNKNOWN', 'SUCCESS_PENDING', 'SUCCESS', 'FAILURE_DEPENDENCY', 'FAILURE_PENDING', 'FAILURE', name='jobresult'), nullable=True),
    sa.Column('data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('latest_log_excerpt', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('uuid')
    )
    op.create_table('spark_workers',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('owner', sa.Text(), nullable=True),
    sa.Column('time_created', sa.DateTime(), nullable=True),
    sa.Column('accepts', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('status', sa.Enum('UNKNOWN', 'ACTIVE', 'IDLE', 'MISSING', 'DEAD', name='workerstatus'), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=True),
    sa.Column('last_ping', sa.DateTime(), nullable=True),
    sa.Column('last_job', postgresql.UUID(as_uuid=True), nullable=True),
    sa.PrimaryKeyConstraint('uuid')
    )
    op.create_table('spears_excuses',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('source_suites', postgresql.ARRAY(sa.String(length=128)), nullable=True),
    sa.Column('time', sa.DateTime(), nullable=True),
    sa.Column('migration_id', sa.Text(), nullable=False),
    sa.Column('suite_target', sa.String(length=128), nullable=True),
    sa.Column('suite_source', sa.String(length=128), nullable=True),
    sa.Column('is_candidate', sa.Boolean(), nullable=True),
    sa.Column('source_package', sa.Text(), nullable=True),
    sa.Column('maintainer', sa.Text(), nullable=True),
    sa.Column('age_current', sa.Integer(), nullable=True),
    sa.Column('age_required', sa.Integer(), nullable=True),
    sa.Column('version_new', laniakea.db.base.DebVersion(), nullable=True),
    sa.Column('version_old', laniakea.db.base.DebVersion(), nullable=True),
    sa.Column('missing_archs_primary', postgresql.ARRAY(sa.String(length=128)), nullable=True),
    sa.Column('missing_archs_secondary', postgresql.ARRAY(sa.String(length=128)), nullable=True),
    sa.Column('old_binaries', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('blocked_by', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('migrate_after', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('manual_block', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('other', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('log_excerpt', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('uuid')
    )
    op.create_table('spears_hints',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('migration_id', sa.String(length=256), nullable=True),
    sa.Column('time', sa.DateTime(), nullable=True),
    sa.Column('hint', sa.Text(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('user', sa.String(length=256), nullable=True),
    sa.PrimaryKeyConstraint('uuid')
    )
    op.create_table('spears_migrations',
    sa.Column('idname', sa.Text(), nullable=False),
    sa.Column('source_suites', postgresql.ARRAY(sa.String(length=128)), nullable=True),
    sa.Column('target_suite', sa.String(length=128), nullable=True),
    sa.Column('delays', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.PrimaryKeyConstraint('idname')
    )
    op.create_table('synchrotron_blacklist',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('pkgname', sa.String(length=256), nullable=True),
    sa.Column('time_created', sa.DateTime(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('user', sa.String(length=256), nullable=True),
    sa.PrimaryKeyConstraint('uuid')
    )
    op.create_table('synchrotron_issues',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('time_created', sa.DateTime(), nullable=True),
    sa.Column('kind', sa.Enum('UNKNOWN', 'NONE', 'MERGE_REQUIRED', 'MAYBE_CRUFT', 'SYNC_FAILED', 'REMOVAL_FAILED', name='synchrotronissuekind'), nullable=True),
    sa.Column('package_name', sa.String(length=256), nullable=True),
    sa.Column('source_suite', sa.String(length=256), nullable=True),
    sa.Column('target_suite', sa.String(length=256), nullable=True),
    sa.Column('source_version', laniakea.db.base.DebVersion(), nullable=True),
    sa.Column('target_version', laniakea.db.base.DebVersion(), nullable=True),
    sa.Column('details', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('uuid')
    )
    op.create_table('archive_bin_packages',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('deb_type', sa.Enum('UNKNOWN', 'DEB', 'UDEB', name='debtype'), nullable=True),
    sa.Column('name', sa.String(length=256), nullable=True),
    sa.Column('version', laniakea.db.base.DebVersion(), nullable=True),
    sa.Column('repo_id', sa.Integer(), nullable=True),
    sa.Column('component_id', sa.Integer(), nullable=True),
    sa.Column('architecture_id', sa.Integer(), nullable=True),
    sa.Column('size_installed', sa.Integer(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('description_md5', sa.CHAR(length=32), nullable=True),
    sa.Column('source_name', sa.String(length=256), nullable=True),
    sa.Column('source_version', laniakea.db.base.DebVersion(), nullable=True),
    sa.Column('priority', sa.Enum('UNKNOWN', 'REQUIRED', 'IMPORTANT', 'STANDARD', 'OPTIONAL', 'EXTRA', name='packagepriority'), nullable=True),
    sa.Column('section', sa.String(length=64), nullable=True),
    sa.Column('depends', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('pre_depends', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('maintainer', sa.Text(), nullable=True),
    sa.Column('homepage', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['architecture_id'], ['archive_architectures.id'], ),
    sa.ForeignKeyConstraint(['component_id'], ['archive_components.id'], ),
    sa.ForeignKeyConstraint(['repo_id'], ['archive_repositories.id'], ),
    sa.PrimaryKeyConstraint('uuid')
    )
    op.create_index('idx_bin_package_repo_arch', 'archive_bin_packages', ['repo_id', 'architecture_id'], unique=False)
    op.create_table('archive_repo_suite_association',
    sa.Column('repo_id', sa.Integer(), nullable=True),
    sa.Column('suite_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['repo_id'], ['archive_repositories.id'], ),
    sa.ForeignKeyConstraint(['suite_id'], ['archive_suites.id'], )
    )
    op.create_table('archive_src_packages',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('source_uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=True),
    sa.Column('version', laniakea.db.base.DebVersion(), nullable=True),
    sa.Column('repo_id', sa.Integer(), nullable=True),
    sa.Column('component_id', sa.Integer(), nullable=True),
    sa.Column('architectures', postgresql.ARRAY(sa.String(length=64)), nullable=True),
    sa.Column('binaries', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('standards_version', sa.String(length=256), nullable=True),
    sa.Column('format_version', sa.String(length=64), nullable=True),
    sa.Column('homepage', sa.Text(), nullable=True),
    sa.Column('vcs_browser', sa.Text(), nullable=True),
    sa.Column('maintainer', sa.Text(), nullable=True),
    sa.Column('uploaders', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('build_depends', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('directory', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['component_id'], ['archive_components.id'], ),
    sa.ForeignKeyConstraint(['repo_id'], ['archive_repositories.id'], ),
    sa.PrimaryKeyConstraint('uuid')
    )
    op.create_table('archive_suite_architecture_association',
    sa.Column('suite_id', sa.Integer(), nullable=True),
    sa.Column('arch_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['arch_id'], ['archive_architectures.id'], ),
    sa.ForeignKeyConstraint(['suite_id'], ['archive_suites.id'], )
    )
    op.create_table('archive_suite_component_association',
    sa.Column('suite_id', sa.Integer(), nullable=True),
    sa.Column('component_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['component_id'], ['archive_components.id'], ),
    sa.ForeignKeyConstraint(['suite_id'], ['archive_suites.id'], )
    )
    op.create_table('debcheck_issues',
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('time', sa.DateTime(), nullable=True),
    sa.Column('package_type', sa.Enum('UNKNOWN', 'SOURCE', 'BINARY', name='packagetype'), nullable=True),
    sa.Column('repo_id', sa.Integer(), nullable=True),
    sa.Column('suite_id', sa.Integer(), nullable=True),
    sa.Column('architectures', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('package_name', sa.String(length=256), nullable=True),
    sa.Column('package_version', laniakea.db.base.DebVersion(), nullable=True),
    sa.Column('missing', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('conflicts', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['repo_id'], ['archive_repositories.id'], ),
    sa.ForeignKeyConstraint(['suite_id'], ['archive_suites.id'], ),
    sa.PrimaryKeyConstraint('uuid')
    )
    op.create_table('archive_binpkg_suite_association',
    sa.Column('bin_package_uuid', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('suite_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['bin_package_uuid'], ['archive_bin_packages.uuid'], ),
    sa.ForeignKeyConstraint(['suite_id'], ['archive_suites.id'], )
    )
    op.create_table('archive_files',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('fname', sa.Text(), nullable=True),
    sa.Column('size', sa.Integer(), nullable=True),
    sa.Column('sha256sum', sa.CHAR(length=64), nullable=True),
    sa.Column('srcpkg_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('binpkg_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.ForeignKeyConstraint(['binpkg_id'], ['archive_bin_packages.uuid'], ),
    sa.ForeignKeyConstraint(['srcpkg_id'], ['archive_src_packages.uuid'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('binpkg_id')
    )
    op.create_table('archive_srcpkg_suite_association',
    sa.Column('src_package_uuid', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('suite_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['src_package_uuid'], ['archive_src_packages.uuid'], ),
    sa.ForeignKeyConstraint(['suite_id'], ['archive_suites.id'], )
    )
    op.create_table('archive_swcpt_binpkg_association',
    sa.Column('sw_cpt_uuid', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('bin_package_uuid', postgresql.UUID(as_uuid=True), nullable=True),
    sa.ForeignKeyConstraint(['bin_package_uuid'], ['archive_bin_packages.uuid'], ),
    sa.ForeignKeyConstraint(['sw_cpt_uuid'], ['archive_sw_components.uuid'], )
    )


def downgrade():
    op.drop_table('archive_swcpt_binpkg_association')
    op.drop_table('archive_srcpkg_suite_association')
    op.drop_table('archive_files')
    op.drop_table('archive_binpkg_suite_association')
    op.drop_table('debcheck_issues')
    op.drop_table('archive_suite_component_association')
    op.drop_table('archive_suite_architecture_association')
    op.drop_table('archive_src_packages')
    op.drop_table('archive_repo_suite_association')
    op.drop_index('idx_bin_package_repo_arch', table_name='archive_bin_packages')
    op.drop_table('archive_bin_packages')
    op.drop_table('synchrotron_issues')
    op.drop_table('synchrotron_blacklist')
    op.drop_table('spears_migrations')
    op.drop_table('spears_hints')
    op.drop_table('spears_excuses')
    op.drop_table('spark_workers')
    op.drop_table('jobs')
    op.drop_table('image_build_recipes')
    op.drop_table('config')
    op.drop_table('archive_sw_components')
    op.drop_table('archive_suites')
    op.drop_table('archive_repositories')
    op.drop_table('archive_components')
    op.drop_table('archive_architectures')

    sa.Enum(name='imagekind').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='jobstatus').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='jobresult').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='workerstatus').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='synchrotronissuekind').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='debtype').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='packagepriority').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='packagetype').drop(op.get_bind(), checkfirst=False)

