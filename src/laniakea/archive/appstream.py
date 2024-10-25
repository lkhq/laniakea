# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+


import os

import gi

gi.require_version('AppStream', '1.0')
import json
import lzma

import yaml
from gi.repository import AppStream

import laniakea.typing as T
from laniakea.db import (
    ArchiveSuite,
    BinaryPackage,
    ArchiveComponent,
    SoftwareComponent,
    ArchiveArchitecture,
    ArchiveRepoSuiteSettings,
)
from laniakea.utils import process_file_lock
from laniakea.logging import log


def _update_appstream_components_internal(
    session, rss: ArchiveRepoSuiteSettings, component: ArchiveComponent, arch: ArchiveArchitecture, cpts, cid_map
):
    if len(cpts) == 0:
        return

    suite = rss.suite
    arch_all = session.query(ArchiveArchitecture).filter(ArchiveArchitecture.name == 'all').one()

    mdata_write = AppStream.Metadata()
    mdata_write.set_locale('ALL')
    mdata_write.set_format_style(AppStream.FormatStyle.CATALOG)
    mdata_write.set_parse_flags(AppStream.ParseFlags.IGNORE_MEDIABASEURL)
    mdata_write.set_write_header(False)

    for cpt in cpts:
        try:
            cpt.set_context_locale('C')
        except AttributeError:
            # compatibility with AppStream < 1.0
            cpt.set_active_locale('C')

        pkgname = cpt.get_pkgname()
        if not pkgname:
            # we skip these for now, web-apps have no package assigned - we might need a better way to map
            # those to their packages, likely with an improved appstream-generator integration
            log.debug(
                'Found DEP-11 component without package name in {}/{}: {}'.format(
                    suite.name, component.name, cpt.get_id()
                )
            )
            continue

        # fetch package this component belongs to
        bin_pkg = (
            session.query(BinaryPackage)
            .filter(
                BinaryPackage.name == pkgname,
                BinaryPackage.repo_id == rss.repo.id,
                BinaryPackage.architecture_id.in_((arch.id, arch_all.id)),
                BinaryPackage.component_id == component.id,
                BinaryPackage.suites.any(ArchiveSuite.id == suite.id),
            )
            .order_by(BinaryPackage.version.desc())
            .first()
        )

        is_orphaned = False
        if not bin_pkg:
            log.info('Found orphaned DEP-11 component in {}/{}: {}'.format(suite.name, component.name, cpt.get_id()))
            is_orphaned = True

        # determine the global component ID (GCID)
        cid = cpt.get_id()
        gcid = cid_map.get(cid)
        if not gcid:
            log.warning(
                'Found DEP-11 component without GCID in {}:{}/{}: {}'.format(
                    rss.repo.name, suite.name, component.name, cpt.get_id()
                )
            )
            continue

        # see if a component already exists in the database
        cpt_uuid = SoftwareComponent.uuid_for_gcid(gcid)
        existing_dcpt: SoftwareComponent | None = (
            session.query(SoftwareComponent).filter(SoftwareComponent.uuid == cpt_uuid).one_or_none()
        )
        if existing_dcpt:
            if is_orphaned:
                # remove our orphaned component, if necessary
                if not existing_dcpt.pkgs_binary:
                    log.info('Deleted component: %s', existing_dcpt.gcid)
                    session.delete(existing_dcpt)
                continue
            elif bin_pkg in existing_dcpt.pkgs_binary:
                # The binary package is already registered with this component, or the component is
                # orphaned. We have nothing left to do.
                continue

            log.debug('Component "%s" is now also available in package "%s"', cid, str(bin_pkg))
            existing_dcpt.pkgs_binary.append(bin_pkg)
            continue  # we already have this component, no need to add it again

        if is_orphaned:
            # if the component is orphaned, we need to stop processing here and shouldn't add
            # it to the database
            continue

        dcpt = SoftwareComponent()
        dcpt.gcid = gcid
        dcpt.uuid = cpt_uuid
        dcpt.kind = int(cpt.get_kind())
        dcpt.cid = cid

        # Generate JSON representation for this component
        # We want the whole component data in the database for quick reference,
        # but dumping the raw XML into the db, while convenient, is rather inefficient.
        # So storing JSON is a compromise.
        mdata_write.clear_components()
        mdata_write.add_component(cpt)
        try:
            y_data = yaml.safe_load(mdata_write.components_to_catalog(AppStream.FormatKind.YAML))
        except AttributeError:
            # backwards compatibility with AppStream versions prior to 1.0
            y_data = yaml.safe_load(
                mdata_write.components_to_collection(AppStream.FormatKind.YAML)  # pylint: disable=no-member
            )

        dcpt.data = json.dumps(y_data)  # type: ignore[assignment]

        # add new software component to database
        dcpt.name = cpt.get_name()
        dcpt.summary = cpt.get_summary()
        dcpt.description = cpt.get_description()

        for icon in cpt.get_icons():
            if icon.get_kind() == AppStream.IconKind.CACHED:
                dcpt.icon_name = icon.get_name()
                break

        dcpt.project_license = cpt.get_project_license()
        try:
            developer = cpt.get_developer()
            if developer:
                dcpt.developer_name = developer.get_name()
        except AttributeError:
            # compatibility with AppStream < 1.0
            dcpt.developer_name = cpt.get_developer_name()

        # test for free software
        dcpt.is_free = False
        if not dcpt.project_license:
            # We have no license set.
            # If we are in the 'main' component, we
            # assume we have free software
            if bin_pkg.component.name == 'main':
                dcpt.is_free = True
        else:
            # have AppStream test the SPDX license expression for free software
            dcpt.is_free = AppStream.license_is_free_license(dcpt.project_license)

        dcpt.categories = []
        for cat in cpt.get_categories():
            dcpt.categories.append(cat)

        dcpt.pkgs_binary.append(bin_pkg)

        session.add(dcpt)
        log.info('Added new software component \'{}\' to database'.format(dcpt.cid))


def import_appstream_data(
    session,
    rss: ArchiveRepoSuiteSettings,
    component: ArchiveComponent,
    arch: ArchiveArchitecture,
    *,
    repo_dists_dir: T.Optional[T.PathUnion] = None,
):
    """
    Import AppStream metadata about software components and associate it with the
    binary packages the data belongs to.

    :param session: SQLAlchemy session
    :param rss: Repo/suite configuration to act on (must match the local repository)
    :param component: Component to import data for
    :param arch: Architecture to act on
    """

    if arch.name == 'all':
        # arch:all has no AppStream components, those are always associated with an architecture
        # and are included in arch-specific files (even if the package they belong to is arch:all)
        return

    mdata_read = AppStream.Metadata()
    mdata_read.set_locale('ALL')
    mdata_read.set_format_style(AppStream.FormatStyle.CATALOG)
    mdata_read.set_parse_flags(AppStream.ParseFlags.IGNORE_MEDIABASEURL)

    if not repo_dists_dir:
        repo_dists_dir = os.path.join(rss.repo.get_root_dir(), 'dists')

    dep11_dists_dir = os.path.join(repo_dists_dir, rss.suite.name, component.name, 'dep11')
    yaml_fname = os.path.join(dep11_dists_dir, 'Components-{}.yml.xz'.format(arch.name))
    if not os.path.isfile(yaml_fname):
        return

    cidmap_fname = os.path.join(dep11_dists_dir, 'CID-Index-{}.json.xz'.format(arch.name))
    if not os.path.isfile(cidmap_fname):
        return

    with lzma.open(cidmap_fname, 'rb') as f:
        cid_map = json.loads(f.read())
    with lzma.open(yaml_fname, 'r') as f:
        yaml_catalog_data = str(f.read(), 'utf-8')

    mdata_read.clear_components()
    try:
        try:
            mdata_read.parse_data(yaml_catalog_data, AppStream.FormatKind.YAML)
        except TypeError:
            mdata_read.parse_data(yaml_catalog_data, -1, AppStream.FormatKind.YAML)
        cpts = mdata_read.get_components().as_array()
    except AttributeError:
        # backwards compatibility with AppStream versions prior to 1.0
        mdata_read.parse(yaml_catalog_data, AppStream.FormatKind.YAML)  # pylint: disable=no-member
        cpts = mdata_read.get_components()

    log.debug('Found {} software components in {}/{}'.format(len(cpts), rss.suite.name, component.name))
    if len(cpts) == 0:
        return

    with process_file_lock('import_dep11', wait=True, noisy=False):
        _update_appstream_components_internal(session, rss, component, arch, cpts, cid_map)
        session.commit()
