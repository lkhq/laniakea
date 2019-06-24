# Copyright (C) 2018-2019 Matthias Klumpp <matthias@tenstral.net>
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

# import all of lknative and expose its API intentionally here
from lknative import *  # noqa
from lknative import BaseConfig, SuiteInfo

from laniakea.db import config_get_project_name, config_get_distro_tag, session_factory, \
    ArchiveSuite


def create_native_baseconfig():
    from laniakea import LocalConfig

    session = session_factory()
    bconf = BaseConfig()

    bconf.projectName = config_get_project_name()
    bconf.archive.distroTag = config_get_distro_tag()

    dev_suite = session.query(ArchiveSuite) \
        .filter(ArchiveSuite.devel_target == True).one()  # noqa: E712

    bconf.archive.develSuite = dev_suite.name

    lconf = LocalConfig()
    bconf.cacheDir = lconf.cache_dir
    bconf.workspace = lconf.workspace
    bconf.archive.rootPath = lconf.archive_root_dir

    return bconf


def get_suiteinfo_for_suite(suite):
    '''
    get native SuiteInfo() description for an ArchiveSuite from the database.
    '''
    si = SuiteInfo()
    si.name = suite.name
    si.architectures = [a.name for a in suite.architectures]
    si.components = [c.name for c in suite.components]
    si.primaryArchitecture = suite.primary_architecture

    if suite.parent:
        si.parent.name = suite.parent.name
        si.parent.architectures = [a.name for a in suite.parent.architectures]
        si.parent.components = [c.name for c in suite.parent.components]

    return si


def get_suiteinfo_all_suites():
    session = session_factory()

    suite_infos = []
    suites = session.query(ArchiveSuite).all()
    for suite in suites:
        suite_infos.append(get_suiteinfo_for_suite(suite))

    return suite_infos
