# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2026 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from click.testing import CliRunner

from laniakea.db import (
    ArchiveSuite,
    BinaryPackage,
    SourcePackage,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveArchitecture,
    session_scope,
)
from archivecli.manage_pkg import cmd_list


def _add_source_package(
    session, repo: ArchiveRepository, name: str, version: str, suites: list[ArchiveSuite]
) -> SourcePackage:
    """Register a bare-bones source package with the database, without any files."""

    spkg = SourcePackage(name, version, repo)
    spkg.component = session.query(ArchiveComponent).filter(ArchiveComponent.name == 'main').one()
    spkg.architectures = ['any']
    spkg.format_version = '3.0 (quilt)'
    spkg.maintainer = 'A Maintainer <maint@example.com>'
    spkg.directory = 'pool/main/{}/{}'.format(name[0], name)
    spkg.expected_binaries = []
    spkg.suites = suites
    session.add(spkg)

    return spkg


def _add_binary_package(
    session, spkg: SourcePackage, name: str, version: str, arch_name: str, suites: list[ArchiveSuite]
) -> BinaryPackage:
    """Register a bare-bones binary package built from :spkg with the database, without any files."""

    arch = session.query(ArchiveArchitecture).filter(ArchiveArchitecture.name == arch_name).one()

    bpkg = BinaryPackage(name, version, spkg.repo)
    bpkg.source = spkg
    bpkg.component = spkg.component
    bpkg.architecture = arch
    bpkg.update_uuid()
    bpkg.size_installed = 1
    bpkg.summary = 'Test package'
    bpkg.description = 'Test package'
    bpkg.description_md5 = '0' * 32
    bpkg.maintainer = spkg.maintainer
    bpkg.suites = suites
    session.add(bpkg)

    return bpkg


def _list_packages(term: str) -> list[list[str]]:
    """Run `lk-archive ls` and return the rows of the table it prints."""

    # make the table wide enough that rich doesn't need to wrap any cells
    result = CliRunner().invoke(cmd_list, [term], env={'COLUMNS': '200'}, catch_exceptions=False)
    assert result.exit_code == 0, result.output

    table_lines = [line for line in result.output.splitlines() if '│' in line]
    rows = [[cell.strip() for cell in line.split('│')] for line in table_lines]

    # the first line holds the column names
    assert rows[0] == ['Package', 'Version', 'Repository', 'Suites', 'Component', 'Architectures']
    return rows[1:]


def test_list_packages_sorted(database):
    """`lk-archive ls` has to sort packages by their version, not alphabetically (#35)."""

    with session_scope() as session:
        master = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'master').one()
        extra = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'extra').one()
        unstable = session.query(ArchiveSuite).filter(ArchiveSuite.name == 'unstable').one()
        stable = session.query(ArchiveSuite).filter(ArchiveSuite.name == 'stable').one()

        # an alphabetical sort would put 2.06-3 after 2.06-13
        spkg_new = _add_source_package(session, master, 'grub2', '2.06-13+deb12u1', [unstable])
        _add_source_package(session, master, 'grub2', '2.02+dfsg1-4', [stable])
        spkg_old = _add_source_package(session, master, 'grub2', '2.06-3~deb11u5', [stable])
        _add_source_package(session, extra, 'grub2', '2.06-13+deb12u1', [unstable])

        _add_binary_package(session, spkg_new, 'grub-pc', '2.06-13+deb12u1+b1', 'amd64', [unstable])
        _add_binary_package(session, spkg_new, 'grub-common', '2.06-13+deb12u1', 'arm64', [unstable])
        _add_binary_package(session, spkg_new, 'grub-common', '2.06-13+deb12u1', 'amd64', [unstable])
        _add_binary_package(session, spkg_old, 'grub-pc', '2.06-3~deb11u5', 'amd64', [stable])
        _add_binary_package(session, spkg_old, 'grub-common', '2.06-3~deb11u5', 'amd64', [stable])

    # binaries follow their source, even if their own version is different (like for binNMUs)
    assert _list_packages('grub*') == [
        ['grub2', '2.02+dfsg1-4', 'master', 'stable', 'main', 'source'],
        ['grub2', '2.06-3~deb11u5', 'master', 'stable', 'main', 'source'],
        ['grub-common', '2.06-3~deb11u5', 'master', 'stable', 'main', 'amd64'],
        ['grub-pc', '2.06-3~deb11u5', 'master', 'stable', 'main', 'amd64'],
        ['grub2', '2.06-13+deb12u1', 'extra', 'unstable', 'main', 'source'],
        ['grub2', '2.06-13+deb12u1', 'master', 'unstable', 'main', 'source'],
        ['grub-common', '2.06-13+deb12u1', 'master', 'unstable', 'main', 'amd64 arm64'],
        ['grub-pc', '2.06-13+deb12u1+b1', 'master', 'unstable', 'main', 'amd64'],
    ]
