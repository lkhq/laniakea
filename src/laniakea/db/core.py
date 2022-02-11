# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSON

from .base import Base


class LkModule:
    '''
    String identifiers of Laniakea modules.
    '''

    UNKNOWN = ''
    BASE = 'core'  # The Laniakea base platform
    TESTSUITE = 'test'  # The Laniakea testsuite
    LIGHTHOUSE = 'lighthouse'  # Message relay station
    SYNCHROTRON = 'synchrotron'  # Syncs packages from a source distribution
    SPEARS = 'spears'  # Automatic package migration
    PLANTER = 'planter'  # Interface to Germinate, a metapackage / default-package-selection generator
    ADMINCLI = 'admin-cli'  # CLI interface to Laniakea settings and the database, useful debug tool
    KEYTOOL = 'keytool'  # Small CLI tool to handle encryption keys and certificates
    WEB = 'web'  # Laniakea web view
    WEBSWVIEW = 'webswview'  # Packages / software web view
    DEBCHECK = 'debcheck'  # Package installability and dependency tests
    ISOTOPE = 'isotope'  # ISO image build scheduling and data import
    # Accepts job result artifacts (logfiles, built files, ...), verifies them and moves them to the right place
    RUBICON = 'rubicon'
    ARCHIVE = 'archive'  # Lists packages in the database
    DATAIMPORT = 'dataimport'  # Import various data from other sources into the database
    ARIADNE = 'ariadne'  # Package autobuild scheduler
    ARCHIVE = 'archive'  # Package archive related things


class ConfigEntry(Base):
    '''
    A generic, multi-purpose configuration entry.
    '''

    __tablename__ = 'config'

    id = Column(String, primary_key=True)
    value = Column(JSON)

    def __init__(self, mod, identifier, value: dict = None):
        if not value:
            value = {}

        self.id = '{}.{}'.format(mod, identifier)
        self.value = value

    def set_value(self, mod, key, value):
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
