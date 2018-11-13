# Copyright (C) 2018 Matthias Klumpp <matthias@tenstral.net>
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

from sqlalchemy import Column, String, Integer
from sqlalchemy.dialects.postgresql import JSON
from .base import Base


class LkModule:
    '''
    String identifiers of Laniakea modules.
    '''
    UNKNOWN     = ''
    BASE        = 'core'        # The Laniakea base platform
    TESTSUITE   = 'test'        # The Laniakea testsuite
    LIGHTHOUSE  = 'lighthouse'  # Message relay station
    SYNCHROTRON = 'synchrotron' # Syncs packages from a source distribution
    SPEARS      = 'spears'      # Automatic package migration
    PLANTER     = 'planter'     # Interface to Germinate, a metapackage / default-package-selection generator
    ADMINCLI    = 'admin-cli'   # CLI interface to Laniakea settings and the database, useful debug tool
    KEYTOOL     = 'keytool'     # Small CLI tool to handle encryption keys and certificates
    WEB         = 'web'         # Laniakea web view
    WEBSWVIEW   = 'webswview'   # Packages / software web view
    DEBCHECK    = 'debcheck'    # Package installability and dependency tests
    ISOTOPE     = 'isotope'     # ISO image build scheduling and data import
    RUBICON     = 'rubicon'     # Accepts job result artifacts (logfiles, built files, ...), verifies them and moves them to the right place
    ARCHIVE     = 'archive'     # Lists packages in the database
    DATAIMPORT  = 'dataimport'  # Import various data from other sources into the database
    ARIADNE     = 'ariadne'     # Package autobuild scheduler


class ConfigEntry(Base):
    '''
    A generic, multi-purpose configuration entry.
    '''
    __tablename__ = 'config'

    id = Column(String, primary_key=True)
    value = Column(JSON)

    def __init__(self, mod, identifier, value={}):
        self.id = '{}.{}'.format(mod, identifier)
        self.value = value

    def set_value(mod, key, value):
        self.id = '{}.{}'.format(mod, key)
        self.value = value


def config_get_value(mod, key):
    '''
    Get a value from the configuration store.
    '''
    from laniakea.db import session_factory

    session = session_factory()
    entry = session.query(ConfigEntry).filter_by(id='{}.{}'.format(mod, key)).one_or_none()
    if not entry:
        return None
    return entry.value


def config_set_value(mod, key, value):
    '''
    Set a value in the configuration store
    '''
    from laniakea.db import session_factory

    session = session_factory()
    entry = session.query(ConfigEntry).filter_by(id='{}.{}'.format(mod, key)).one_or_none()
    if entry:
        entry.value = value
    else:
        entry = ConfigEntry(mod, key, value)
        session.add(entry)
    session.commit()


def config_get_distro_tag():
    '''
    Retrieve version tag for this distribution ("pureos", "tanglu", ...)
    - will usually be part of a package version, e.g. "1.0-0tanglu1"
    '''
    r = config_get_value(LkModule.BASE, 'distro_tag')
    return r if r is not None else None


def config_set_distro_tag(value):
    '''
    Set version tag for this distribution ("pureos", "tanglu", ...)
    - will usually be part of a package version, e.g. "1.0-0tanglu1"
    '''
    config_set_value(LkModule.BASE, 'distro_tag', value)


def config_get_project_name():
    '''
    Get the name of the distribution or project ("Tanglu", "PureOS", ...)
    '''
    r = config_get_value(LkModule.BASE, 'project_name')
    return r if r is not None else None


def config_set_project_name(value):
    '''
    Set the name of the distribution or project ("Tanglu", "PureOS", ...)
    '''
    config_set_value(LkModule.BASE, 'project_name', value)
