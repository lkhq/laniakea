#!/usr/bin/env python3
#
# Copyright (C) 2016-2019 Matthias Klumpp <matthias@tenstral.net>
#
# Licensed under the GNU Lesser General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the license, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..')))

import json
import gzip
import lzma
from argparse import ArgumentParser
from laniakea import LocalConfig
from laniakea.logging import log
from laniakea.db import session_factory, session_scope, ArchiveSuite, ArchiveRepository, ArchiveArchitecture, \
    SourcePackage, BinaryPackage, ArchiveFile, PackageInfo, SoftwareComponent
from sqlalchemy.orm import joinedload
from laniakea.native import Repository
import gi
gi.require_version('AppStream', '1.0')
from gi.repository import AppStream


def _register_binary_packages(session, repo, suite, component, arch, existing_bpkgs, bpkgs):

    for bpi in bpkgs:
        bpkg = BinaryPackage()
        bpkg.name = bpi.name
        bpkg.version = bpi.ver
        bpkg.repo = repo
        bpkg.architecture = arch
        bpkg.update_uuid()  # we can generate the uuid from name/version/repo-name/arch now

        db_bpkg = existing_bpkgs.pop(bpkg.uuid, None)
        if db_bpkg:
            if suite in db_bpkg.suites:
                continue  # the binary package is already registered with this suite
            db_bpkg.suites.append(suite)
            continue

        # if we are here, the package is completely new and is only in one suite
        bpkg.suites = [suite]
        bpkg.component = component

        bpkg.deb_type = bpi.debType

        bpkg.size_installed = bpi.installedSize
        bpkg.description = bpi.description
        bpkg.description_md5 = bpi.descriptionMd5

        bpkg.source_name = bpi.sourceName
        bpkg.source_version = bpi.sourceVersion

        bpkg.priority = bpi.priority
        bpkg.section = bpi.section

        bpkg.depends = bpi.depends
        bpkg.pre_depends = bpi.preDepends

        bpkg.maintainer = bpi.maintainer
        bpkg.homepage = bpi.homepage

        f = ArchiveFile()
        f.fname = bpi.file.fname
        f.size = bpi.file.size
        f.sha256sum = bpi.file.sha256sum
        bpkg.pkg_file = f

        session.add(bpkg)

    return existing_bpkgs


def import_appstream_data(session, local_repo, repo, suite, component, arch):
    '''
    Import AppStream metadata about software components and associate it with the
    binary packages the data belongs to.
    '''

    if arch.name == 'all':
        # arch:all has no AppStream components, those are always associated with an architecture
        # and are included in arch-specific files (even if the package they belong to is arch:all)
        return

    arch_all = session.query(ArchiveArchitecture) \
                      .filter(ArchiveArchitecture.name == 'all').one()

    yaml_fname = local_repo.getIndexFile(suite.name, os.path.join(component.name, 'dep11', 'Components-{}.yml.xz'.format(arch.name)))
    if not yaml_fname:
        return

    cidmap_fname = local_repo.getIndexFile(suite.name, os.path.join(component.name, 'dep11', 'CID-Index-{}.json.gz'.format(arch.name)))
    if not cidmap_fname:
        return

    with gzip.open(cidmap_fname, 'rb') as f:
        cid_map = json.loads(f.read())
    with lzma.open(yaml_fname, 'r') as f:
        yaml_data = str(f.read(), 'utf-8')

    mdata = AppStream.Metadata()
    mdata.set_locale('ALL')
    mdata.set_format_style(AppStream.FormatStyle.COLLECTION)
    mdata.set_parse_flags(AppStream.ParseFlags.IGNORE_MEDIABASEURL)

    mdata.parse(yaml_data, AppStream.FormatKind.YAML)
    cpts = mdata.get_components()
    if len(cpts) == 0:
        return

    log.debug('Found {} software components in {}/{}'.format(len(cpts), suite.name, component.name))

    tmp_mdata = AppStream.Metadata()
    tmp_mdata.set_locale('ALL')
    tmp_mdata.set_format_style(AppStream.FormatStyle.COLLECTION)

    for cpt in cpts:
        cpt.set_active_locale('C')

        pkgname = cpt.get_pkgname()
        if not pkgname:
            # we skip these for now, web-apps have no package assigned - we might need a better way to map
            # those to their packages, likely with an improved appstream-generator integration
            log.debug('Found DEP-11 component without package name in {}/{}: {}'.format(suite.name, component.name, cpt.get_id()))
            continue

        # fetch package this component belongs to
        bin_pkg = session.query(BinaryPackage) \
            .filter(BinaryPackage.name == pkgname) \
            .filter(BinaryPackage.repo_id == repo.id) \
            .filter(BinaryPackage.architecture_id.in_((arch.id, arch_all.id))) \
            .filter(BinaryPackage.component_id == component.id) \
            .filter(BinaryPackage.suites.any(ArchiveSuite.id == suite.id)) \
            .order_by(BinaryPackage.version.desc()).first()

        if not bin_pkg:
            log.info('Found orphaned DEP-11 component in {}/{}: {}'.format(suite.name, component.name, cpt.get_id()))
            continue

        dcpt = SoftwareComponent()
        dcpt.kind = int(cpt.get_kind())
        dcpt.cid = cpt.get_id()

        tmp_mdata.clear_components()
        tmp_mdata.add_component(cpt)
        dcpt.xml = tmp_mdata.components_to_collection(AppStream.FormatKind.XML)

        dcpt.gcid = cid_map.get(dcpt.cid)
        if not dcpt.gcid:
            log.info('Found DEP-11 component without GCID in {}/{}: {}'.format(suite.name, component.name, cpt.get_id()))

        # create UUID for this component (based on GCID or XML data)
        dcpt.update_uuid()

        existing_dcpt = session.query(SoftwareComponent) \
            .filter(SoftwareComponent.uuid == dcpt.uuid).one_or_none()
        if existing_dcpt:
            if bin_pkg in existing_dcpt.bin_packages:
                continue  # the binary package is already registered with this component
            existing_dcpt.bin_packages.append(bin_pkg)
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

        dcpt.categories = []
        for cat in cpt.get_categories():
            dcpt.categories.append(cat)

        dcpt.bin_packages = [bin_pkg]

        session.add(dcpt)
        log.debug('Added new software component \'{}\' to database'.format(dcpt.cid))
    session.commit()


def import_suite_packages(suite_name):
    # FIXME: Don't hardcode the "master" repository here, fully implement
    # the "multiple repositories" feature
    repo_name = 'master'

    session = session_factory()
    suite = session.query(ArchiveSuite) \
        .filter(ArchiveSuite.name == suite_name).one()
    repo = session.query(ArchiveRepository) \
        .filter(ArchiveRepository.name == repo_name).one()

    lconf = LocalConfig()
    local_repo = Repository(lconf.archive_root_dir, lconf.cache_dir, repo_name, [])

    for component in suite.components:

        # fetch all source packages for the given repository
        # FIXME: Urgh... We need to do this better, this is not efficient.
        existing_spkgs = dict()
        all_existing_src_packages = session.query(SourcePackage) \
            .options(joinedload(SourcePackage.suites)) \
            .filter(SourcePackage.repo_id == repo.id) \
            .filter(SourcePackage.component_id == component.id).all()
        for e_spkg in all_existing_src_packages:
            existing_spkgs[e_spkg.uuid] = e_spkg

        srcPkgInfos = local_repo.getSourcePackages(suite.name, component.name)
        for spi in srcPkgInfos:
            spkg = SourcePackage()
            spkg.name = spi.name
            spkg.version = spi.ver
            spkg.repo = repo
            spkg.update_uuid()  # we can generate the uuid from name/version/repo-name now

            db_spkg = existing_spkgs.pop(spkg.uuid, None)
            if db_spkg:
                if suite in db_spkg.suites:
                    continue  # the source package is already registered with this suite
                db_spkg.suites.append(suite)
                continue

            # if we are here, the source package is completely new and is only in one suite
            spkg.suites = [suite]
            spkg.component = component
            spkg.architectures = spi.architectures
            spkg.standards_version = spi.standardsVersion
            spkg.format_version = spi.format
            spkg.homepage = spi.homepage
            spkg.vcs_browser = spi.vcsBrowser
            spkg.maintainer = spi.maintainer
            spkg.uploaders = spi.uploaders
            spkg.build_depends = spi.buildDepends
            spkg.directory = spi.directory

            binaries = []
            for b in spi.binaries:
                binfo = PackageInfo()
                binfo.deb_type = b.debType
                binfo.name = b.name
                binfo.version = b.ver
                binaries.append(binfo)
            spkg.binaries = binfo

            for fi in spi.files:
                f = ArchiveFile()
                f.fname = fi.fname
                f.size = fi.size
                f.sha256sum = fi.sha256sum
                spkg.files.append(f)

            session.add(spkg)

        for old_spkg in existing_spkgs.values():
            if suite in old_spkg.suites:
                old_spkg.suites.remove(suite)
            if len(old_spkg.suites) <= 0:
                for f in old_spkg.files:
                    session.delete(f)
                session.delete(old_spkg)

        # commit the source package changes already
        session.commit()

        for arch in suite.architectures:

            # Get all binary packages for the given architecture
            # FIXME: Urgh... We need to do this better, this is not efficient.
            existing_bpkgs = dict()
            for e_bpkg in session.query(BinaryPackage) \
                    .options(joinedload(BinaryPackage.suites)) \
                    .filter(BinaryPackage.repo_id == repo.id) \
                    .filter(BinaryPackage.component_id == component.id) \
                    .filter(BinaryPackage.architecture_id == arch.id).all():
                existing_bpkgs[e_bpkg.uuid] = e_bpkg

            # add information about regular binary packages
            existing_bpkgs = _register_binary_packages(session,
                                                       repo,
                                                       suite,
                                                       component,
                                                       arch,
                                                       existing_bpkgs,
                                                       local_repo.getBinaryPackages(suite.name,
                                                                                    component.name,
                                                                                    arch.name))
            session.commit()

            # add information about debian-installer packages
            existing_bpkgs = _register_binary_packages(session,
                                                       repo,
                                                       suite,
                                                       component,
                                                       arch,
                                                       existing_bpkgs,
                                                       local_repo.getInstallerPackages(suite.name,
                                                                                       component.name,
                                                                                       arch.name))
            session.commit()

            for old_bpkg in existing_bpkgs.values():
                if suite in old_bpkg.suites:
                    old_bpkg.suites.remove(suite)
                if len(old_bpkg.suites) <= 0:
                    session.delete(old_bpkg.pkg_file)
                    session.delete(old_bpkg)
            session.commit()

            # import new AppStream component metadata
            import_appstream_data(session, local_repo, repo, suite, component, arch)

    # delete orphaned AppStream metadata
    for cpt in session.query(SoftwareComponent).filter(~SoftwareComponent.bin_packages.any()).all():
        session.delete(cpt)
    session.commit()


def command_repo(options):
    ''' Import repository data '''

    suite_names = []
    if options.suite:
        suite_names.append(options.suite)
    else:
        log.debug('Importing data from all mutable suites.')
        with session_scope() as session:
            suite_names = [r[0] for r in session.query(ArchiveSuite.name)
                           .filter(ArchiveSuite.frozen == False).all()]  # noqa

    # TODO: Optimize this so we can run it in parallel, as well as skip
    # imports if they are not needed
    for suite_name in suite_names:
        log.debug('Importing data for suite "{}".'.format(suite_name))
        import_suite_packages(suite_name)


def create_parser(formatter_class=None):
    ''' Create DataImport CLI argument parser '''

    parser = ArgumentParser(description='Import existing static data into the Laniakea database')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')
    parser.add_argument('--config', action='store', dest='config_fname', default=None,
                        help='Location of the base configuration file to use.')

    sp = subparsers.add_parser('repo', help='Import repository data for a specific suite.')
    sp.add_argument('suite', type=str, help='The suite to import data for.', nargs='?')
    sp.set_defaults(func=command_repo)

    return parser


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__
        print(__version__)
        sys.exit(0)


def check_verbose(options):
    if options.verbose:
        from laniakea.logging import set_verbose
        set_verbose(True)


def run(args):
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    parser = create_parser()
    args = parser.parse_args(args)
    check_print_version(args)
    check_verbose(args)
    if args.config_fname:
        LocalConfig(args.config_fname)

    args.func(args)


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
