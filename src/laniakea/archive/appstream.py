# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+


import os

import gi

gi.require_version('AppStream', '1.0')
import gzip
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
from laniakea.logging import log


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

    arch_all = session.query(ArchiveArchitecture).filter(ArchiveArchitecture.name == 'all').one()

    mdata_read = AppStream.Metadata()
    mdata_read.set_locale('ALL')
    mdata_read.set_format_style(AppStream.FormatStyle.COLLECTION)
    mdata_read.set_parse_flags(AppStream.ParseFlags.IGNORE_MEDIABASEURL)

    mdata_write = AppStream.Metadata()
    mdata_write.set_locale('ALL')
    mdata_write.set_format_style(AppStream.FormatStyle.COLLECTION)
    mdata_write.set_parse_flags(AppStream.ParseFlags.IGNORE_MEDIABASEURL)
    mdata_write.set_write_header(False)

    suite = rss.suite
    if not repo_dists_dir:
        repo_dists_dir = os.path.join(rss.repo.get_root_dir(), 'dists')

    dep11_dists_dir = os.path.join(repo_dists_dir, suite.name, component.name, 'dep11')
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
    mdata_read.parse(yaml_catalog_data, AppStream.FormatKind.YAML)
    cpts = mdata_read.get_components()
    if len(cpts) == 0:
        return

    log.debug('Found {} software components in {}/{}'.format(len(cpts), suite.name, component.name))
    for cpt in cpts:
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
            .filter(BinaryPackage.name == pkgname)
            .filter(BinaryPackage.repo_id == rss.repo.id)
            .filter(BinaryPackage.architecture_id.in_((arch.id, arch_all.id)))
            .filter(BinaryPackage.component_id == component.id)
            .filter(BinaryPackage.suites.any(ArchiveSuite.id == suite.id))
            .order_by(BinaryPackage.version.desc())
            .first()
        )

        if not bin_pkg:
            log.info('Found orphaned DEP-11 component in {}/{}: {}'.format(suite.name, component.name, cpt.get_id()))
            continue

        dcpt = SoftwareComponent()
        dcpt.kind = int(cpt.get_kind())
        dcpt.cid = cpt.get_id()

        dcpt.gcid = cid_map.get(dcpt.cid)
        if not dcpt.gcid:
            log.warning(
                'Found DEP-11 component without GCID in {}:{}/{}: {}'.format(
                    rss.repo.name, suite.name, component.name, cpt.get_id()
                )
            )
            continue

        # Generate JSON representation for this component
        # We want the whole component data in the database for quick reference,
        # but dumping the raw XML into the db, while convenient, is rather inefficient.
        # So storing JSON is a compromise.
        mdata_write.clear_components()
        mdata_write.add_component(cpt)
        y_data = yaml.safe_load(mdata_write.components_to_collection(AppStream.FormatKind.YAML))
        dcpt.data = json.dumps(y_data)

        # create UUID for this component (based on GCID or XML data)
        dcpt.update_uuid()

        existing_dcpt = session.query(SoftwareComponent).filter(SoftwareComponent.uuid == dcpt.uuid).one_or_none()
        if existing_dcpt:
            if bin_pkg in existing_dcpt.pkgs_binary:
                continue  # the binary package is already registered with this component
            existing_dcpt.pkgs_binary.append(bin_pkg)
            continue  # we already have this component, no need to add it again

        # add new software component to database
        dcpt.name = cpt.get_name()
        dcpt.summary = cpt.get_summary()
        dcpt.description = cpt.get_description()

        for icon in cpt.get_icons():
            if icon.get_kind() == AppStream.IconKind.CACHED:
                dcpt.icon_name = icon.get_name()
                break

        dcpt.project_license = cpt.get_project_license()
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

        dcpt.pkgs_binary = [bin_pkg]

        session.add(dcpt)
        log.info('Added new software component \'{}\' to database'.format(dcpt.cid))
        session.commit()
