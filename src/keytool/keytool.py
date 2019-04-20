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

import datetime
import zmq.auth
from argparse import ArgumentParser
from laniakea import LocalConfig


def command_cert_new(options):
    ''' Create new certificate '''

    base_path = options.basepath
    if not base_path:
        print('The base filename of the certificate is missing.')
        sys.exit(1)

    metadata = {}
    metadata['name'] = options.name
    metadata['email'] = options.email
    if options.organization:
        metadata['organization'] = options.organization
    metadata['created-by'] = 'Laniakea Keytool'
    metadata['date-created'] = str(datetime.datetime.now())

    zmq.auth.create_certificates(os.path.dirname(base_path),
                                 os.path.basename(base_path),
                                 metadata)


def install_service_cert(options):
    ''' Install a private key for a specific service '''
    from shutil import copyfile

    service = '' if not options.service else options.service.lower()
    if service != 'lighthouse':
        print('The "service" option is not "lighthouse". Currently, keys can only be installed for the Lighthouse module.')
        sys.exit(1)

    source_keyfile = options.keyfile
    if not source_keyfile:
        print('No private key file given!')
        sys.exit(1)

    if not os.path.isfile(source_keyfile):
        print('Private key file "{}" was not found.'.format(source_keyfile))
        sys.exit(1)

    pub_key, sec_key = zmq.auth.load_certificate(source_keyfile)
    if not sec_key:
        print('The given keyfile does not contain a secret key!')

    lconf = LocalConfig()
    target_keyfile = lconf.zcurve_secret_keyfile_for_module(service)
    if os.path.isfile(target_keyfile) and not options.force:
        print('We already have a secret key for this service on the current machine. You can override the existing one by specifying "--force".')
        sys.exit(2)

    try:
        copyfile(source_keyfile, target_keyfile)
    except Exception as e:
        print('Failed to install new secret key as {}: {}'.format(target_keyfile, str(e)))
        sys.exit(3)
    print('Installed private key as {}'.format(target_keyfile))


def install_trusted_cert(options):
    ''' Install a public key to trust a client node. '''
    from shutil import copyfile

    if not options.name:
        print('No name for this public key / client given!')
        sys.exit(1)

    source_keyfile = options.keyfile
    if not source_keyfile:
        print('No public key file given!')
        sys.exit(1)

    if not os.path.isfile(source_keyfile):
        print('Public key file "{}" was not found.'.format(source_keyfile))
        sys.exit(1)

    pub_key, sec_key = zmq.auth.load_certificate(source_keyfile)
    if not pub_key:
        print('The given keyfile does not contain a public key!')
        sys.exit(1)
    if sec_key:
        print('')
        print('/!\\ The current file contains a secret key. This file should never leave the client machine it is installed on.')
        print('')

    lconf = LocalConfig()
    target_keyfile = os.path.join(lconf.zcurve_trusted_certs_dir, '{}.pub.key'.format(options.name))
    if os.path.isfile(target_keyfile) and not options.force:
        print('We already trust a key for "{}" on this machine. You can override the existing one by specifying "--force".'.format(options.name))
        sys.exit(2)

    try:
        copyfile(source_keyfile, target_keyfile)
    except Exception as e:
        print('Failed to install new public key as {}: {}'.format(target_keyfile, str(e)))
        sys.exit(3)
    print('Installed as {}'.format(target_keyfile))


def create_parser(formatter_class=None):
    ''' Create KeyTool CLI argument parser '''

    parser = ArgumentParser(description='Manage keys and certificates')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')

    sp = subparsers.add_parser('cert-new', help='Create new ZCurve certificate.')
    sp.add_argument('--name', help='Name of the certificate issuer.', required=True)
    sp.add_argument('--email', help='E-Mail address of the certificate issuer.', required=True)
    sp.add_argument('--organization', help='Organization of the certificate issuer.')
    sp.add_argument('basepath', type=str, help='The base filename of the new certificate.', nargs='?')
    sp.set_defaults(func=command_cert_new)

    sp = subparsers.add_parser('install-service-cert', help='Install a private certificate for a specific service on this machine.')
    sp.add_argument('--force', action='store_true', help='Enforce installation of the key file, overriding any existing one.')
    sp.add_argument('service', type=str, help='Name of the Laniakea service.', nargs='?')
    sp.add_argument('keyfile', type=str, help='The private key filename.', nargs='?')
    sp.set_defaults(func=install_service_cert)

    sp = subparsers.add_parser('install-trusted-cert', help='Install a public certificate from a client node to trust it.')
    sp.add_argument('--force', action='store_true', help='Enforce installation of the key file, overriding any existing one.')
    sp.add_argument('name', type=str, help='Name of the client this public key file belongs to.', nargs='?')
    sp.add_argument('keyfile', type=str, help='The public key filename.', nargs='?')
    sp.set_defaults(func=install_trusted_cert)

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
