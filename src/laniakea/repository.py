# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

from apt_pkg import (TagFile, TagSection,  # type: ignore[attr-defined]
                     sha256sum, version_compare)

from laniakea.db import (ArchiveArchitecture, ArchiveComponent, ArchiveFile,
                         ArchiveRepository, ArchiveSuite, BinaryPackage,
                         DebType, PackageInfo, SourcePackage,
                         debtype_from_string, packagepriority_from_string)
from laniakea.localconfig import LocalConfig
from laniakea.logging import log
from laniakea.utils import download_file, is_remote_url, split_strip
from laniakea.utils.gpg import SignedFile


def parse_checksums_list(data, base_dir=None):
    files = []
    if not data:
        return files
    for line in data.split('\n'):
        parts = split_strip(line, ' ')  # f43923ace1c558ad9f9fa88eb3f1764a8c0379013aafbc682a35769449fe8955 2455 0ad_0.0.20-1.dsc
        if len(parts) != 3:
            continue

        af = ArchiveFile()
        af.sha256sum = parts[0]
        af.size = int(parts[1])
        if not base_dir:
            af.fname = parts[2]
        else:
            af.fname = os.path.join(base_dir, parts[2])

        files.append(af)

    return files


def parse_package_list_str(pkg_list_raw, default_version=None):
    '''
    Parse a "Package-List" field and return its information in
    PackageInfo data structures.
    See https://www.debian.org/doc/debian-policy/ch-controlfields.html#package-list
    '''

    res = []

    for line in pkg_list_raw.split('\n'):
        parts = split_strip(line, ' ')
        if len(parts) < 4:
            continue

        pi = PackageInfo()
        pi.name = parts[0]
        pi.version = default_version
        pi.deb_type = debtype_from_string(parts[1])
        pi.section = parts[2]
        pi.priority = packagepriority_from_string(parts[3])

        if len(parts) > 4:
            # we have additional data
            raw_vals = split_strip(parts[4], ' ')
            for v in raw_vals:
                if v.startswith('arch='):
                    # handle architectures
                    pi.architectures = v[5:].split(',')

        res.append(pi)
    return res


def version_revision(version: str, full_for_native: bool = True) -> str:
    '''
    Get the Debian revision string from a version number.
    :param full_for_native: Return the full version if we have a native package.
    '''
    idx = version.rfind('-')
    if idx < 0:
        return version if full_for_native else ''
    return version[idx + 1:]


class Repository:
    '''
    Allows reading data from a Debian repository.
    '''

    class InReleaseData:
        files: list[ArchiveFile] = []

    def __init__(self, location, repo_name=None, trusted_keyrings: list[str] = None, entity=None):

        if not trusted_keyrings:
            trusted_keyrings = []

        lconf = LocalConfig()
        if not repo_name:
            repo_name = 'unknown'
        if is_remote_url(location):
            self._root_dir = os.path.join(lconf.cache_dir, 'repo_cache', repo_name)
            os.makedirs(self._root_dir, exist_ok=True)
            self._repo_url = location
        else:
            self._root_dir = location
            self._repo_url = None

        self._keyrings = trusted_keyrings
        self._trusted = False
        self._name = repo_name

        if entity:
            self._repo_entity = entity
        else:
            self._repo_entity = ArchiveRepository(self._name)

        self._inrelease: dict[str, Repository.InReleaseData] = {}

    @property
    def base_dir(self) -> str:
        '''
        The on-disk location of this repository.
        '''
        return self._root_dir

    @property
    def location(self) -> str:
        '''
        A location string identifier of where this repository resides.
        '''
        if not self._repo_url:
            return self._root_dir
        return self._repo_url

    def set_trusted(self, trusted):
        self._trusted = trusted
        if self._trusted:
            log.debug('Explicitly marked repository "{}" as trusted.'.format(self.location))

    def _fetch_repo_file_internal(self, location, check=False):
        '''
        Download a file and retrieve a filename.

        This function does not validate the result, this step
        has to be done by the caller.
        '''
        if self._repo_url:
            source_url = os.path.join(self._repo_url, location)
            target_fname = os.path.join(self._root_dir, location)
            os.makedirs(os.path.dirname(target_fname), exist_ok=True)

            download_file(source_url, target_fname, check=check)
            return target_fname
        else:
            fname = os.path.join(self._root_dir, location)
            if os.path.isfile(fname):
                return fname

        # There was an error, we couldn't find or download the file
        log.error('Could not find repository file "{}"'.format(location))
        return None

    def get_file(self, afile, check=True) -> str:
        '''
        Get a file from the repository.
        Returns: An absolute path to the repository file.
        '''
        assert type(afile) is ArchiveFile

        fname = self._fetch_repo_file_internal(afile.fname, check=True)
        if check:
            with open(fname, 'rb') as f:
                sha256h = sha256sum(f)
                if sha256h != afile.sha256sum:
                    raise Exception('Checksum validation of "{}" failed ({} != {}).'.format(fname, sha256h, afile.sha256sum))

        return fname

    def _read_repo_information(self, suite_name, check=True):
        if suite_name in self._inrelease:
            return self._inrelease[suite_name]

        irfname = self._fetch_repo_file_internal(os.path.join('dists', suite_name, 'InRelease'))
        if not irfname:
            if check:
                raise Exception('Unable to find InRelease data for repository "{}"'.format(self.location))
            return Repository.InReleaseData()

        with open(irfname, 'rb') as irf:
            contents = irf.read()

        require_signature = True
        if self._trusted and not self._keyrings:
            # no keyrings, but the repository was explicitly trusted - no need to validate
            # the stuff.
            # TODO: Maybe we should change the code to simply *always* validate everything?
            require_signature = False

        sf = SignedFile(contents, self._keyrings, require_signature=require_signature)
        contents = sf.contents

        section = TagSection(contents)
        ird = Repository.InReleaseData()

        files_raw = section['SHA256']
        ird.files = parse_checksums_list(files_raw)

        self._inrelease[suite_name] = ird
        return ird

    def index_file(self, suite, fname, check=True):
        '''
        Retrieve a package list (index) file from the repository.
        The file will be downloaded if necessary:

        Returns: A file path to the index file.
        '''
        if type(suite) is ArchiveSuite:
            suite_name = suite.name
        else:
            suite_name = suite

        ird = self._read_repo_information(suite_name)
        index_fname = self._fetch_repo_file_internal(os.path.join('dists', suite_name, fname))
        if not index_fname:
            return None

        # validate the file
        with open(index_fname, 'rb') as f:
            index_sha256sum = sha256sum(f)

        valid = False
        for af in ird.files:
            if af.fname == fname:
                if index_sha256sum != af.sha256sum:
                    raise Exception('Checksum validation of "{}" failed ({} != {})'.format(fname, index_sha256sum, af.sha256sum))
                valid = True

        if not valid and check:
            raise Exception('Unable to validate "{}": File not mentioned in InRelease.'.format(fname))

        return index_fname

    def source_packages(self, suite, component):
        ''' Return a list of all source packages in the given suite and component. '''
        assert type(suite) is ArchiveSuite
        assert type(component) is ArchiveComponent

        index_fname = self.index_file(suite.name, os.path.join(component.name, 'source', 'Sources.xz'))
        if not index_fname:
            return []

        pkgs = []
        with TagFile(index_fname) as tf:
            for e in tf:
                pkgname = e['Package']
                pkgversion = e['Version']
                if not pkgname or not pkgversion:
                    raise Exception('Found invalid block (no Package and Version fields) in Sources file "{}".'.format(index_fname))

                pkg = SourcePackage()
                pkg.repo = self._repo_entity
                pkg.name = pkgname
                pkg.component = component
                if suite not in pkg.suites:
                    pkg.suites.append(suite)

                pkg.version = pkgversion
                pkg.architectures = split_strip(e['Architecture'], ' ')
                pkg.standards_version = e.get('Standards-Version', '0~notset')
                pkg.format_version = e['Format']

                pkg.vcs_browser = e.get('Vcs-Browser')
                pkg.homepage = e.get('Homepage')
                pkg.maintainer = e['Maintainer']
                pkg.uploaders = split_strip(e.get('Uploaders', ''), ',')  # FIXME: Careful! Splitting just by comma isn't enough! We need to parse this properly.

                pkg.build_depends = split_strip(e.get('Build-Depends', ''), ',')
                pkg.directory = e['Directory']

                pkg.files = parse_checksums_list(e.get('Checksums-Sha256'), pkg.directory)

                binaries = []
                raw_pkg_list = e.get('Package-List', None)
                if not raw_pkg_list:
                    for bpname in e.get('Binary', '').split(','):
                        if not bpname:
                            continue
                        bpname = bpname.strip()
                        pi = PackageInfo()
                        pi.deb_type = DebType.DEB
                        pi.name = bpname
                        pi.ver = pkg.version
                        binaries.append(pi)
                else:
                    binaries = parse_package_list_str(raw_pkg_list, pkg.version)
                pkg.binaries = binaries

                # do some issue-reporting
                if not pkg.files and pkg.format_version != '1.0':
                    log.warning('Source package {}/{} seems to have no files (in {}).'.format(pkg.name, pkg.version, self.location))

                # add package to results set
                pkg.update_uuid()
                pkgs.append(pkg)

        return pkgs

    def _read_binary_packages_from_tf(self, tf, tf_fname, suite, component, arch, deb_type):
        requested_arch_is_all = arch.name == 'all'

        pkgs = []
        for e in tf:
            pkgname = e['Package']
            pkgversion = e['Version']
            if not pkgname or not pkgversion:
                raise Exception('Found invalid block (no Package and Version fields) in Packages file "{}".'.format(tf_fname))

            arch_name = e['Architecture']

            # we deal with arch:all packages separately
            if not requested_arch_is_all and arch_name == 'all':
                continue

            # sanity check
            if arch_name != arch.name:
                log.warning('Found package "{}::{}/{}" with unexpeced architecture "{}" (expected "{}")'.format(self._name, pkgname, pkgversion, arch_name, arch.name))

            pkg = BinaryPackage()
            pkg.repo = self._repo_entity
            pkg.name = pkgname
            pkg.component = component
            pkg.version = pkgversion
            if suite not in pkg.suites:
                pkg.suites.append(suite)

            pkg.architecture = arch
            pkg.maintainer = e['Maintainer']

            source_id = e.get('Source')
            if not source_id:
                pkg.source_name = pkg.name
                pkg.source_version = pkg.version
            elif '(' in source_id:
                pkg.source_name = source_id[0:source_id.index('(') - 1].strip()
                pkg.source_version = source_id[source_id.index('(') + 1:source_id.index(')')].strip()
            else:
                pkg.source_name = source_id
                pkg.source_version = pkg.version

            pkg.size_installed = int(e.get('Installed-Size', '0'))

            pkg.depends = split_strip(e.get('Depends', ''), ',')
            pkg.pre_depends = split_strip(e.get('Pre-Depends', ''), ',')

            pkg.homepage = e.get('Homepage')
            pkg.section = e['Section']

            pkg.description = e['Description']
            pkg.description_md5 = e.get('Description-md5')

            pkg.priority = packagepriority_from_string(e['Priority'])

            pkg.bin_file = ArchiveFile()
            pkg.bin_file.fname = e['Filename']
            pkg.bin_file.size = int(e.get('Size', '0'))
            pkg.bin_file.sha256sum = e['SHA256']

            pkg.deb_type = DebType.DEB
            if pkg.bin_file.fname.endswith('.udeb'):
                pkg.deb_type = DebType.UDEB

            # do some issue-reporting
            if not pkg.bin_file.fname:
                log.warning('Binary package "{}/{}/{}" seems to have no files.'.format(pkg.name, pkg.version, arch.name))

            # update UUID and add package to results set
            pkg.update_uuid()
            pkgs.append(pkg)

        return pkgs

    def binary_packages(self, suite, component, arch):
        '''
        Get a list of binary package information for the given repository suite,
        component and architecture.
        '''

        assert type(suite) is ArchiveSuite
        assert type(component) is ArchiveComponent
        assert type(arch) is ArchiveArchitecture

        index_fname = self.index_file(suite.name, os.path.join(component.name, 'binary-{}'.format(arch.name), 'Packages.xz'))
        if not index_fname:
            return []

        with TagFile(index_fname) as tf:
            return self._read_binary_packages_from_tf(tf,
                                                      index_fname,
                                                      suite,
                                                      component,
                                                      arch,
                                                      DebType.DEB)

    def installer_packages(self, suite, component, arch):
        '''
        Get a list of binary installer packages for the given repository suite, component
        and architecture.
        These binary packages are typically udebs used by the debian-installer, and should not
        be installed on an user's system.
        '''

        assert type(suite) is ArchiveSuite
        assert type(component) is ArchiveComponent
        assert type(arch) is ArchiveArchitecture

        index_fname = self.index_file(suite.name, os.path.join(component.name, 'debian-installer', 'binary-{}'.format(arch.name), 'Packages.xz'))
        if not index_fname:
            return []

        with TagFile(index_fname) as tf:
            return self._read_binary_packages_from_tf(tf,
                                                      index_fname,
                                                      suite,
                                                      component,
                                                      arch,
                                                      DebType.UDEB)


def make_newest_packages_dict(pkgs):
    '''
    Create a dictionary of name->pkg containing only
    the packages with the highest version number from :pkgs
    '''

    res = {}
    for pkg in pkgs:
        epkg = res.get(pkg.name)
        if epkg:
            if version_compare(pkg.version, epkg.version) > 0:
                res[pkg.name] = pkg
        else:
            res[pkg.name] = pkg

    return res
