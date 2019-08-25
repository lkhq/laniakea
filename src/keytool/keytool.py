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
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..', 'lib', 'laniakea')))
if not thisfile.startswith(('/usr', '/bin')):
    sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..')))

import datetime
import zmq.auth
from argparse import ArgumentParser
from laniakea import LocalConfig
from laniakea.utils import stringify
from laniakea.msgstream.signing import generate_signing_key, get_verify_key, \
    encode_signing_key_base64, encode_verify_key_base64, keyfile_read_verify_key, keyfile_read_signing_key
from laniakea.logging import log


def _create_metadata_section(metadata):
    ''' Create metadata string for use in Laniakea keyfiles '''

    s = 'metadata\n'
    for key, value in metadata.items():
        s += '    {} = "{}"\n'.format(key.replace(' ', '_'), value)
    return s


def _write_key_file(fname, metadata, curve_public_key, curve_secret_key, ed_public_key, ed_secret_key):
    ''' Create a Laniakea keyfile for the given set of keys '''

    secret_keyfile = True
    with open(fname, 'w') as f:
        if curve_secret_key or ed_secret_key:
            f.write(('#\n# Laniakea Messaging **Secret** Certificate\n'
                     '# DO NOT PROVIDE THIS FILE TO OTHER USERS nor change its permissions.\n#\n'))
            secret_keyfile = True
        else:
            f.write(('#\n# Laniakea Messaging Public Certificate\n'
                     '# Exchange securely, or use a secure mechanism to verify the contents\n'
                     '# of this file after exchange.\n#\n'))
            secret_keyfile = False
        f.write('\n')
        f.write(_create_metadata_section(metadata))

        # Curve25519 section
        f.write('curve\n')
        if curve_public_key:
            f.write('    public-key = "{}"\n'.format(stringify(curve_public_key)))
        if curve_secret_key and secret_keyfile:
            f.write('    secret-key = "{}"\n'.format(stringify(curve_secret_key)))

        # NOTE: We can't name the Ed25519 keys 'public-key' and 'secret-key' as well,
        # because CurveZMQ will not actually read the section these keys are in and
        # simply take the last entry with the respective names.
        # That's why we use 'verify-key' and 'signing-key' here, so the generated
        # file can still be read by CurveZMQ without modifications.
        # Lighthouse is still able to filter out the Ed25519 signing keys that way

        # Ed25519 section
        f.write('ed\n')
        if ed_public_key:
            f.write('    verify-key = "{}"\n'.format(stringify(ed_public_key)))
        if ed_secret_key and secret_keyfile:
            f.write('    signing-key = "{}"\n'.format(stringify(ed_secret_key)))


def command_keyfile_new(options):
    ''' Create new certificate '''

    base_path = options.path
    if not base_path:
        print('No directory to store they key files in was specified.')
        sys.exit(1)

    metadata = {}
    metadata['id'] = options.id
    metadata['name'] = options.name
    metadata['email'] = options.email
    if options.organization:
        metadata['organization'] = options.organization
    metadata['created-by'] = 'Laniakea Keytool'
    metadata['date-created'] = str(datetime.datetime.now())

    secret_fname = os.path.join(base_path, '{}.key_secret'.format(options.id))
    public_fname = os.path.join(base_path, '{}.key'.format(options.id))

    # create Curve25519 keys for ZCurve
    if options.sign_only:
        curve_public_key = None
        curve_secret_key = None
    else:
        curve_public_key, curve_secret_key = zmq.curve_keypair()

    # create Ed25519 for our message signing
    ed_key = generate_signing_key(0)
    ed_verify_key = get_verify_key(ed_key)
    ed_secret_key = encode_signing_key_base64(ed_key)
    ed_public_key = encode_verify_key_base64(ed_verify_key)

    # write secret keyfile
    _write_key_file(secret_fname,
                    metadata,
                    curve_public_key,
                    curve_secret_key,
                    ed_public_key,
                    ed_secret_key)

    # write public keyfile
    _write_key_file(public_fname,
                    metadata,
                    curve_public_key,
                    None,
                    ed_public_key,
                    None)


def install_service_keyfile(options):
    ''' Install a private key for a specific service '''
    from shutil import copyfile

    service = '' if not options.service else options.service.lower()
    if not service:
        print('The "service" option must not be empty')
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
    target_keyfile = lconf.secret_curve_keyfile_for_module(service)
    if os.path.isfile(target_keyfile) and not options.force:
        print('We already have a secret key for this service on the current machine. You can override the existing one by specifying "--force".')
        sys.exit(2)

    try:
        copyfile(source_keyfile, target_keyfile)
    except Exception as e:
        print('Failed to install new secret key as {}: {}'.format(target_keyfile, str(e)))
        sys.exit(3)
    print('Installed private key as {}'.format(target_keyfile))


def install_trusted_keyfile(options):
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

    pub_key = None
    sec_key = None
    try:
        pub_key, sec_key = zmq.auth.load_certificate(source_keyfile)
    except ValueError:
        pass
    if not pub_key:
        log.info('The given keyfile does not contain a public ZCurve key!')
    if sec_key:
        print('')
        print('/!\\ The current file contains a secret ZCurve key. This file should never leave the client machine it is installed on.')
        print('')

    _, verify_key = keyfile_read_verify_key(source_keyfile)
    if not verify_key:
        log.info('The given keyfile does not contain a verification key!')
    if not verify_key and not pub_key:
        log.error('The keyfile does not contain either a public encryption, nor a verification key. Can not continue.')
        sys.exit(4)

    _, sign_key = keyfile_read_signing_key(source_keyfile)
    if sign_key:
        print('')
        print('/!\\ The current file contains a secret signing key. This file should never leave the client machine it is installed on.')
        print('')

    lconf = LocalConfig()
    target_keyfile = os.path.join(lconf.trusted_curve_keys_dir, '{}.pub.key'.format(options.name))
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

    parser = ArgumentParser(description='Manage key-files used for secure messaging between modules')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')

    sp = subparsers.add_parser('key-new', help='Create new keyfile for use with Laniakea\'s messaging.')
    sp.add_argument('--id', help='Service/signer ID used with this key. Is used as part of the key filenames.', required=True)
    sp.add_argument('--name', help='Name of the certificate issuer.', required=True)
    sp.add_argument('--email', help='E-Mail address of the certificate issuer.', required=True)
    sp.add_argument('--organization', help='Organization of the certificate issuer.')
    sp.add_argument('--sign-only', action='store_true', help='Only generate Ed25519 keys to sign data, but none to encrypt data streams.')
    sp.add_argument('path', type=str, help='Directory to store the generated keyfiles in.', nargs='?')
    sp.set_defaults(func=command_keyfile_new)

    sp = subparsers.add_parser('install-service-key', help='Install a private key for a specific service on this machine.')
    sp.add_argument('--force', action='store_true', help='Enforce installation of the key file, overriding any existing one.')
    sp.add_argument('service', type=str, help='Name of the Laniakea service.', nargs='?')
    sp.add_argument('keyfile', type=str, help='The private key filename.', nargs='?')
    sp.set_defaults(func=install_service_keyfile)

    sp = subparsers.add_parser('install-trusted-key', help='Install a public key from a client node to trust it.')
    sp.add_argument('--force', action='store_true', help='Enforce installation of the key file, overriding any existing one.')
    sp.add_argument('name', type=str, help='Name of the client this public key file belongs to.', nargs='?')
    sp.add_argument('keyfile', type=str, help='The public key filename.', nargs='?')
    sp.set_defaults(func=install_trusted_keyfile)

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
