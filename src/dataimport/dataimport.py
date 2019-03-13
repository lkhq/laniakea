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

from argparse import ArgumentParser
from laniakea import LocalConfig, LkModule
from laniakea.db import session_factory, ArchiveSuite, ArchiveRepository, SourcePackage, BinaryPackage, \
    ArchiveFile
from lknative import Repository


def _register_binary_packages(session, repo, suite, component, arch, existing_bpkgs, bpkgs):
    import lknative

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
            session.update(db_bpkg)
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


def command_repo(options):
    ''' Import repository data '''

    suite_name = options.suite
    if not suite_name:
        print('Suite parameter is missing!')
        sys.exit(1)

    # FIXME: Don't hardcode the "master" repository here, fully implement
    # the "multiple repositories" feature
    repo_name = 'master'

    session = session_factory()
    suite = session.query(ArchiveSuite) \
        .filter(ArchiveSuite.name==suite_name).one()
    repo = session.query(ArchiveRepository) \
        .filter(ArchiveRepository.name==repo_name).one()

    lconf = LocalConfig()
    local_repo = Repository(lconf.archive_root_dir, lconf.cache_dir, repo_name, [])

    for component in suite.components:

        # fetch all source packages for the given suite
        existing_spkgs = dict()
        for e_spkg in session.query(SourcePackage).filter(SourcePackage.suites.any(ArchiveSuite.id==suite.id)) \
            .filter(SourcePackage.repo_id==repo.id).all():
                existing_spkgs[e_spkg.uuid] = e_spkg

        for spi in local_repo.getSourcePackages (suite.name, component.name):
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
                session.update(db_spkg)
                continue

            # if we are here, the source package is completely new and is only in one suite
            spkg.suites = [suite]
            spkg.component = component
            spkg.architectures = spi.architectures
            spkg.standards_version = spi.standardsVersion
            #spkg.pkgformat = spi.pkgformat
            spkg.homepage = spi.homepage
            spkg.vcs_browser = spi.vcsBrowser
            spkg.maintainer = spi.maintainer
            spkg.uploaders = spi.uploaders
            spkg.build_depends = spi.buildDepends
            spkg.directory = spi.directory

            for fi in spi.files:
                f = ArchiveFile()
                f.fname = fi.fname
                f.size = fi.size
                f.sha256sum = fi.sha256sum
                spkg.files.append(f)

            session.add(spkg)

        for old_spkg in existing_spkgs.keys():
            old_spkg.suites.remove(suite)
            if len(old_spkg.suites) > 0:
                session.update(old_spkg)
            else:
                for f in old_spkg.files:
                    session.delete(f)
                session.delete(old_spkg)

        # commit the source package changes already
        session.commit()

        for arch in suite.architectures:

            existing_bpkgs = dict()
            for e_bpkg in session.query(BinaryPackage).filter(BinaryPackage.suites.any(ArchiveSuite.id==suite.id)) \
                    .filter(BinaryPackage.repo_id==repo.id) \
                    .filter(BinaryPackage.architecture_id==arch.id).all():
                existing_bpkgs[e_bpkg.uuid] = e_bpkg

            # add information about regular binary packages
            existing_bpkgs = _register_binary_packages(session,
                                                       repo,
                                                       suite,
                                                       component,
                                                       arch,
                                                       existing_bpkgs,
                                                       local_repo.getBinaryPackages (suite.name,
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
                                                       local_repo.getInstallerPackages (suite.name,
                                                                                     component.name,
                                                                                     arch.name))
            session.commit()

            for old_bpkg in existing_bpkgs.keys():
                old_bpkg.suites.remove(suite)
                if len(old_bpkg.suites) > 0:
                    session.update(old_bpkg)
                else:
                    session.delete(old_bpkg.pkg_file)
                    session.delete(old_bpkg)
            session.commit()

            # TODO: Add AppStream information as well


def create_parser(formatter_class=None):
    ''' Create DataImport CLI argument parser '''

    parser = ArgumentParser(description='Import existing static data into the Laniakea database')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of debspawn itself.')

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
    args.func(args)

if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
