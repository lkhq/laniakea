"""Make binary packages not reference their overrides

Revision ID: 4c4d4f6fd252
Revises: a5281c40b748
Create Date: 2023-03-07 21:06:51.270191

"""
import pickle
import os.path
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Enum, Column, String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import joinedload, relationship, sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

from laniakea.db import BinaryPackage, PackageOverride, PackagePriority, session_scope

# flake8: noqa


# revision identifiers, used by Alembic.
revision = '4c4d4f6fd252'
down_revision = 'a5281c40b748'
branch_labels = None
depends_on = None

Base: Any = declarative_base()


class StubArchiveRepoSuiteSettings(Base):
    __tablename__ = 'archive_repo_suite_settings'

    id = Column(Integer, primary_key=True)

    repo_id = Column(Integer)
    suite_id = Column(Integer)


class OldPackageOverride(Base):
    """
    Overridable "archive organization" data of a binary package.
    """

    __tablename__ = 'archive_pkg_overrides'

    id = Column(Integer, primary_key=True)

    pkgname = Column(String(200))  # Name of the binary package

    repo_suite_id = Column(Integer, ForeignKey('archive_repo_suite_settings.id'))
    repo_suite = relationship('StubArchiveRepoSuiteSettings')

    essential = Column(Boolean(), default=False)  # Whether this package is marked as essential
    priority = Column(Enum(PackagePriority))  # Priority of the package

    component_id = Column(Integer)
    section_id = Column(Integer)

    def __init__(self, pkgname: str):
        self.pkgname = pkgname


def upgrade():
    # save & convert the old overrides
    print('Collecting old data...')
    old_overrides = {}
    with session_scope() as session:
        for o in session.query(OldPackageOverride).all():
            ov = PackageOverride(o.pkgname)
            ov.repo_id = o.repo_suite.repo_id
            ov.suite_id = o.repo_suite.suite_id
            ov.essential = o.essential
            ov.priority = o.priority
            ov.component_id = o.component_id
            ov.section_id = o.section_id

            old_overrides['{}:{}/{}'.format(ov.repo_id, ov.suite_id, ov.pkg_name)] = ov

    backup_fname = '/tmp/old-overrides-backup.pkl'
    if old_overrides:
        with open(backup_fname, 'wb') as f:
            pickle.dump(old_overrides, f)
    elif os.path.isfile(backup_fname):
        with open(backup_fname, 'rb') as f:
            old_overrides = pickle.load(f)

    print('Adjusting database schema...')
    op.alter_column('archive_pkgs_binary', 'repo_id', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('archive_pkgs_binary', 'architecture_id', existing_type=sa.INTEGER(), nullable=False)
    op.drop_constraint('archive_pkgs_binary_override_id_fkey', 'archive_pkgs_binary', type_='foreignkey')
    op.drop_column('archive_pkgs_binary', 'override_id')

    op.execute('TRUNCATE TABLE archive_pkg_overrides')

    op.alter_column('archive_pkg_overrides', 'pkgname', nullable=False, new_column_name='pkg_name')
    op.add_column('archive_pkg_overrides', sa.Column('repo_id', sa.Integer(), nullable=False))
    op.add_column('archive_pkg_overrides', sa.Column('suite_id', sa.Integer(), nullable=False))
    op.create_unique_constraint('_repo_suite_pkgname_uc', 'archive_pkg_overrides', ['repo_id', 'suite_id', 'pkg_name'])
    op.create_index(
        'idx_overrides_repo_suite_pkgname', 'archive_pkg_overrides', ['repo_id', 'suite_id', 'pkg_name'], unique=False
    )
    op.drop_constraint('archive_pkg_overrides_repo_suite_id_fkey', 'archive_pkg_overrides', type_='foreignkey')
    op.create_foreign_key(None, 'archive_pkg_overrides', 'archive_suites', ['suite_id'], ['id'])
    op.create_foreign_key(None, 'archive_pkg_overrides', 'archive_repositories', ['repo_id'], ['id'])
    op.drop_column('archive_pkg_overrides', 'repo_suite_id')

    op.alter_column('archive_queue_new', 'destination_id', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('archive_repo_suite_settings', 'repo_id', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('archive_repo_suite_settings', 'suite_id', existing_type=sa.INTEGER(), nullable=False)

    # fix up database and ensure every package actually has an override set
    print('Migrating data...')
    engine = op.get_bind()
    session_factory = sessionmaker(bind=engine)

    Session = scoped_session(session_factory)
    with Session() as session:
        all_bpkgs = session.query(BinaryPackage).options(joinedload(BinaryPackage.suites)).all()
        for bpkg in all_bpkgs:
            orig_override = None
            for suite in bpkg.suites:
                orig_override = old_overrides.get('{}:{}/{}'.format(bpkg.repo.id, suite.id, bpkg.name), None)
                if orig_override:
                    break

            if not orig_override:
                print('WARNING: Found binary package without override:', bpkg, '(invented one to fill the blank)')
                orig_override = PackageOverride(bpkg.name)
                orig_override.repo = bpkg.repo
                orig_override.pkg_name = bpkg.name
                orig_override.essential = False
                orig_override.component = bpkg.component
                orig_override.section = bpkg.source.section

            for suite in bpkg.suites:
                override = old_overrides.get('{}:{}/{}'.format(bpkg.repo.id, suite.id, bpkg.name), None)
                if override:
                    if (
                        not session.query(PackageOverride)
                        .filter(
                            PackageOverride.repo_id == bpkg.repo_id,
                            PackageOverride.suite_id == suite.id,
                            PackageOverride.pkg_name == bpkg.name,
                        )
                        .all()
                    ):
                        session.add(override)
                else:
                    ov = PackageOverride(bpkg.name)
                    ov.repo = bpkg.repo
                    ov.suite = suite
                    ov.pkg_name = bpkg.name
                    ov.essential = orig_override.essential
                    ov.priority = orig_override.priority
                    ov.component = orig_override.component
                    ov.section = orig_override.section
                    session.add(ov)
        session.commit()


def downgrade():
    op.alter_column('archive_repo_suite_settings', 'suite_id', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('archive_repo_suite_settings', 'repo_id', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('archive_queue_new', 'destination_id', existing_type=sa.INTEGER(), nullable=True)
    op.add_column('archive_pkgs_binary', sa.Column('override_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(
        'archive_pkgs_binary_override_id_fkey', 'archive_pkgs_binary', 'archive_pkg_overrides', ['override_id'], ['id']
    )
    op.alter_column('archive_pkgs_binary', 'architecture_id', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('archive_pkgs_binary', 'repo_id', existing_type=sa.INTEGER(), nullable=True)
    op.add_column('archive_pkg_overrides', sa.Column('repo_suite_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column(
        'archive_pkg_overrides', sa.Column('pkgname', sa.VARCHAR(length=200), autoincrement=False, nullable=True)
    )
    op.drop_constraint(None, 'archive_pkg_overrides', type_='foreignkey')
    op.drop_constraint(None, 'archive_pkg_overrides', type_='foreignkey')
    op.create_foreign_key(
        'archive_pkg_overrides_repo_suite_id_fkey',
        'archive_pkg_overrides',
        'archive_repo_suite_settings',
        ['repo_suite_id'],
        ['id'],
    )
    op.drop_index('idx_overrides_repo_suite_pkgname', table_name='archive_pkg_overrides')
    op.drop_constraint('_repo_suite_pkgname_uc', 'archive_pkg_overrides', type_='unique')
    op.drop_column('archive_pkg_overrides', 'pkg_name')
    op.drop_column('archive_pkg_overrides', 'suite_id')
    op.drop_column('archive_pkg_overrides', 'repo_id')
