#!/usr/bin/env python3
#
# Check whether all required Python modules are found on the system.
#

import os
import re
import sys
import argparse
import subprocess

if sys.version_info[0] < 3 or sys.version_info[1] < 9:
    print('Laniakea requires at least Python 3.9 to run!', file=sys.stderr)
    sys.exit(2)

try:
    from packaging import version
    from packaging.requirements import Requirement
except ModuleNotFoundError:
    print(
        (
            'Unable to find "packaging" Python module. Please install it via '
            '`apt install python3-packaging` or `pip install packaging`'
        ),
        file=sys.stderr,
    )
    sys.exit(2)

try:
    import tomllib as toml
except ModuleNotFoundError:
    try:
        import tomlkit as toml
    except ModuleNotFoundError:
        print(
            (
                'Unable to find "tomlkit" Python module. Please install it via '
                '`apt install python3-tomlkit` or `pip install tomlkit`'
            ),
            file=sys.stderr,
        )
        sys.exit(2)
    if version.parse(toml.__version__) < version.parse('0.8'):
        print(
            'Your version of tomlkit is too old. We require at least tomlkit>=0.8',
            file=sys.stderr,
        )
        sys.exit(2)

thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
os.chdir(os.path.normpath(os.path.join(os.path.dirname(thisfile))))


def get_installed_modules():
    pip_freeze = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'])
    installed_modules = {}
    for e in pip_freeze.split():
        parts = e.decode().split('==')
        installed_modules[parts[0]] = [parts[1]] if len(parts) > 1 else [None]
    return installed_modules


def ensure_gir(req_str):
    try:
        import gi
    except ModuleNotFoundError:
        print(
            ('Unable to GObject Introspection for Python. Please install it via ' '`apt install python3-gi`'),
            file=sys.stderr,
        )
        sys.exit(2)

    if not req_str.startswith('gir:'):
        raise Exception('GIR dependency definition "{}" is invalid.'.format(req_str))
    req_str = req_str[4:]

    req = Requirement(req_str)
    try:
        gi.require_version(req.name, list(req.specifier)[0].version)
        exec('from gi.repository import {}'.format(req.name))
    except ValueError:
        print(
            'Laniakea requires "{}" GObject introspection data. Please install it to continue.'.format(req.name),
            file=sys.stderr,
        )
        sys.exit(2)


def ensure_dependencies(dependencies, installed_mods=None):
    '''Ensure all dependencies in the list are available in the current environment'''

    if dependencies is None:
        print('No module to check for was defined in this set!', file=sys.stderr)
        sys.exit(2)

    if not installed_mods:
        installed_mods = get_installed_modules()
    for req_str in dependencies:

        # handle GIR dependencies
        if req_str.startswith('gir:'):
            ensure_gir(req_str)
            continue

        req = Requirement(req_str)
        versions = installed_mods.get(req.name)
        if not versions:
            print('Python module "{}" was not found (need: {})'.format(req.name, req_str), file=sys.stderr)
            sys.exit(2)
        if len(versions) == 1 and versions[0] is None:
            continue

        # HACK: workaround for a malformed version string that appeared in python-apt once
        if versions[0].startswith('='):
            versions[0] = re.sub(r'[a-zA-Z]', '', versions[0][1:].replace('-', ''))

        candidates = list(req.specifier.filter(versions))
        if not candidates:
            print(
                'Python module "{}" found, but version "{}" is not sufficient (need: {}).'.format(
                    req.name, versions[0], req_str
                ),
                file=sys.stderr,
            )
            sys.exit(2)


def write_requirements(all_dependencies):
    '''Write requirements.txt file(s) for all groups, based on the current environment'''

    installed_mods = get_installed_modules()
    for group, req_list in all_dependencies.items():
        is_tests = group == 'tests'
        is_docs = group == 'docs'
        ensure_dependencies(req_list, installed_mods)
        req_fname = 'requirements.{}.txt'.format(group)
        if is_docs:
            req_fname = os.path.join('docs', 'requirements.txt')
        with open(req_fname, 'w') as f:
            if is_docs:
                f.write('-r ../requirements.txt\n')
            for req_str in sorted(req_list):
                if req_str.startswith('gir:'):
                    continue  # GIR dependencies don't go into requirements files
                req = Requirement(req_str)
                versions = installed_mods.get(req.name)
                version = versions[0]
                if version:
                    # sanitize versions to work with pip
                    # and the compatible release operator
                    if '.' not in version:
                        version += '.0'
                    if version == '0.0.0':
                        version = None
                if version and not is_tests:
                    if req.name in ('PyGObject', 'systemd-python', 'python-apt'):
                        f.write('{}\n'.format(req.name))
                    elif req.specifier:
                        f.write('{}{}\n'.format(req.name, str(req.specifier)))
                    else:
                        f.write('{}~={}\n'.format(req.name, version))
                else:
                    f.write('{}\n'.format(req.name))

    with open('requirements.txt', 'w') as f:
        for group in all_dependencies.keys():
            if group == 'tests' or group == 'docs':
                continue  # we don't want test and doc dependencies installed by default
            f.write('-r requirements.{}.txt\n'.format(group))


def write_requirements_readthedocs(all_dependencies):
    '''Write requirements.txt file, just for Readthedocs'''

    ignore_reqs = set(['systemd-python', 'python-apt', 'PyGObject'])
    with open(os.path.join('docs', 'readthedocs-reqs.txt'), 'w') as f:
        for group, req_list in all_dependencies.items():
            if group == 'tests':
                continue
            for req_str in sorted(req_list):
                if req_str.startswith('gir:'):
                    continue  # GIR dependencies don't go into requirements files
                req = Requirement(req_str)
                if req.name in ignore_reqs:
                    continue
                f.write('{}\n'.format(req.name))


def run(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-group', type=str, help='Test if dependencies in the given group are satisfied.')
    parser.add_argument(
        '--write-requirements', action='store_true', help='Write requirements file based on the current environment.'
    )
    args = parser.parse_args()

    if not args.check_group and not args.write_requirements:
        print('No group name set to check modules for!', file=sys.stderr)
        sys.exit(1)

    with open('pyproject.toml', 'rb') as f:
        pyproject = toml.load(f)

    if args.check_group:
        ensure_dependencies(pyproject['tool']['laniakea']['dependencies'].get(args.check_group))
    if args.write_requirements:
        write_requirements(pyproject['tool']['laniakea']['dependencies'])
        write_requirements_readthedocs(pyproject['tool']['laniakea']['dependencies'])

    return 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
