#!/usr/bin/env python3
#
# Retrieve web packages via NPM and move them to the right locations.
#

import os
import sys
import shutil
import argparse
import subprocess
from glob import glob

import tomllib


class StaticNPMDataConfig:
    def __init__(self, vendor_dir, src_dir):
        self.vendor_dir = os.path.normpath(vendor_dir)
        self.stage_dir = os.path.normpath(os.path.join(self.vendor_dir, 'static'))
        self.src_dir = os.path.normpath(os.path.join(self.vendor_dir, src_dir))
        self.modules = []


def read_config() -> StaticNPMDataConfig:
    thisfile = __file__
    if not os.path.isabs(thisfile):
        thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
    thisdir = os.path.normpath(os.path.join(os.path.dirname(thisfile)))

    config_path = os.path.join(thisdir, 'static-npm-info.toml')
    if not os.path.isfile(config_path):
        print(f"Configuration file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path, 'rb') as f:
        config_data = tomllib.load(f)

    config = StaticNPMDataConfig(thisdir, config_data.get('src_dir', '../../src/'))
    for pkg in config_data.get('packages', []):
        name = pkg.get('name')
        name_short = name if '/' not in name else name.split('/')[-1]
        files = pkg.get('files', [])
        extra_files = pkg.get('extra_files', [])
        copy_to = pkg.get('copy_to', [])
        config.modules.append(
            dict(name=name, name_short=name_short, files=set(files), copy_to=set(copy_to), extra_files=set(extra_files))
        )

    return config


def stage_node_modules(config: StaticNPMDataConfig, node_cmd):
    """Vendor some data from NPM for later installation."""
    try:
        subprocess.run([node_cmd, 'install'], check=True)
    except FileNotFoundError:
        print(f"Node command '{node_cmd}' not found.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Failed to run '{node_cmd} install': {e}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(os.path.join(config.vendor_dir, 'node_modules')):
        print("node_modules directory not found after install.", file=sys.stderr)
        sys.exit(1)

    for info in config.modules:
        mod_dir = os.path.join(config.vendor_dir, 'node_modules', info['name'])
        all_files = list(info['files'])
        all_files.extend(info.get('extra_files', []))
        for pattern in all_files:
            matches = [m for m in glob(os.path.join(mod_dir, pattern))]
            if not matches:
                print(f"Could not find any match for {pattern} in package {info.get('name')}", file=sys.stderr)
                sys.exit(1)
            for fname in matches:
                # Copy all paths that we want a local copy of
                dest_dir_stub = os.path.dirname(os.path.relpath(fname, mod_dir))
                dest_dir = os.path.join(config.stage_dir, info['name_short'], dest_dir_stub)
                dest_fname = os.path.join(dest_dir, os.path.basename(fname))
                os.makedirs(dest_dir, exist_ok=True)
                if os.path.isfile(fname):
                    shutil.copy2(fname, dest_fname)
                else:
                    shutil.copytree(fname, dest_fname, dirs_exist_ok=True)
                info_name = os.path.join(info['name_short'], dest_dir_stub, os.path.basename(fname))
                print(f'Staged: {info_name}')


def _static_data_copy_matches(config: StaticNPMDataConfig):
    for info in config.modules:
        mod_dir = os.path.join(config.stage_dir, info['name_short'])
        # copy_to already contains absolute paths
        install_dests = [os.path.normpath(d) for d in info['copy_to']]
        for pattern in info['files']:
            matches = [m for m in glob(os.path.join(mod_dir, pattern))]
            if not matches:
                print(f"Could not find any match for {pattern} in package {info.get('name_short')}", file=sys.stderr)
                sys.exit(1)
            for fname in matches:
                for dest in install_dests:
                    yield fname, os.path.join(config.src_dir, dest)


def install_static_data(config: StaticNPMDataConfig):
    """Copy static data into the modules that need it."""
    for fname, dest in _static_data_copy_matches(config):
        os.makedirs(dest, exist_ok=True)
        shutil.copy(fname, dest)


def cleanup_static_data(config: StaticNPMDataConfig):
    """Cleanup all vendored data from the source tree."""
    for fname, dest in _static_data_copy_matches(config):
        rm_fname = os.path.join(dest, os.path.basename(fname))
        if os.path.isfile(rm_fname):
            print(f"Removing file: {rm_fname}")
            os.remove(rm_fname)
        if os.path.isdir(dest) and not os.listdir(dest):
            print(f"Removing directory: {dest}")
            os.rmdir(dest)


def run(argv):
    parser = argparse.ArgumentParser(description='Download and/or copy static assets from node packages')
    subparsers = parser.add_subparsers(dest='command')

    p_stage = subparsers.add_parser('stage', help='Fetch NPM packages and stage some data')
    p_stage.add_argument('--npm', help='Node package manager command', nargs='?', default='npm')

    subparsers.add_parser('copy', help='Only copy already staged data')
    subparsers.add_parser('clean', help='Remove all vendored data')

    p_all = subparsers.add_parser('all', help='Fetch NPM packages, stage them, and copy files to destinations')
    p_all.add_argument('--npm', help='Node package manager command', nargs='?', default='npm')

    parser.add_argument('--stamp', help='Write stamp file on success', nargs='?', default=None)

    if not argv:
        parser.print_help()
        return 2

    args = parser.parse_args(argv)

    config = read_config()

    stamp_path = None
    if getattr(args, 'stamp', None):
        stamp_path = os.path.abspath(args.stamp)
    os.chdir(config.vendor_dir)

    if args.command == 'stage':
        stage_node_modules(config, args.npm)
    elif args.command == 'copy':
        install_static_data(config)
    elif args.command == 'clean':
        cleanup_static_data(config)
    elif args.command == 'all':
        stage_node_modules(config, args.npm)
        install_static_data(config)
    else:
        parser.print_help()
        return 2

    # If a stamp path was provided, write it to signal success
    if stamp_path:
        try:
            os.makedirs(os.path.dirname(stamp_path), exist_ok=True)
            # create or truncate the file
            with open(stamp_path, 'w'):
                pass
        except Exception as e:
            print(f'Warning: failed to write stamp file {args.stamp}: {e}', file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
