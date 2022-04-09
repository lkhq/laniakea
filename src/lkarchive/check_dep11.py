# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2022 Matthias Klumpp <mak@debian.org>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys
import gzip
import lzma
import multiprocessing as mp
from optparse import OptionParser

import yaml
from voluptuous import All, Url, Match, Length, Schema, Required

import laniakea.typing as T

__all__ = ['check_dep11_path']

schema_header = Schema(
    {
        Required('File'): All(str, 'DEP-11', msg='Must be "DEP-11"'),
        Required('Origin'): All(str, Length(min=1)),
        Required('Version'): All(str, Match(r'(\d+\.?)+$'), msg='Must be a valid version number'),
        Required('MediaBaseUrl'): All(str, Url()),
        'Time': All(str),
        'Priority': All(int),
    }
)

schema_translated = Schema(
    {
        Required('C'): All(str, Length(min=1), msg='Must have an unlocalized \'C\' key'),
        dict: All(str, Length(min=1)),
    },
    extra=True,
)

schema_component = Schema(
    {
        Required('Type'): All(str, Length(min=1)),
        Required('ID'): All(str, Length(min=1)),
        Required('Name'): All(dict, Length(min=1), schema_translated),
        Required('Summary'): All(dict, Length(min=1)),
    },
    extra=True,
)


class DEP11Validator:
    """Validate DEP-11 YAML files."""

    def __init__(self):
        self.issues = []

    def add_issue(self, msg):
        self.issues.append(msg)

    def reset(self):
        self.issues = []

    def _test_custom_objects(self, lines):
        ret = True
        for i in range(0, len(lines)):
            if '!!python/' in lines[i]:
                self.add_issue('Python object encoded in line %i.' % (i))
                ret = False
        return ret

    def _test_localized_dict(self, doc, ldict, id_string):
        ret = True
        for lang, value in ldict.items():
            if lang == 'x-test':
                self.add_issue('[%s][%s]: %s' % (doc['ID'], id_string, 'Found cruft locale: x-test'))
            if lang == 'xx':
                self.add_issue('[%s][%s]: %s' % (doc['ID'], id_string, 'Found cruft locale: xx'))
            if lang.endswith('.UTF-8'):
                self.add_issue(
                    '[%s][%s]: %s'
                    % (doc['ID'], id_string, 'AppStream locale names should not specify encoding (ends with .UTF-8)')
                )
            if ' ' in lang:
                self.add_issue('[%s][%s]: %s' % (doc['ID'], id_string, 'Locale name contains space: "%s"' % (lang)))
                # this - as opposed to the other issues - is an error
                ret = False
        return ret

    def _test_localized(self, doc, key):
        ldict = doc.get(key, None)
        if not ldict:
            return True

        return self._test_localized_dict(doc, ldict, key)

    def validate_data(self, data):
        self.reset()
        ret = True
        lines = data.split('\n')

        # see if there are any Python-specific objects encoded
        ret = self._test_custom_objects(lines)

        try:
            docs = yaml.safe_load_all(data)
            header = next(docs)
        except Exception as e:
            self.add_issue('Could not parse file: %s' % (str(e)))
            return False

        try:
            schema_header(header)
        except Exception as e:
            self.add_issue('Invalid DEP-11 header: %s' % (str(e)))
            ret = False

        for doc in docs:
            cptid = doc.get('ID')
            pkgname = doc.get('Package')
            cpttype = doc.get('Type')
            if not doc:
                self.add_issue('FATAL: Empty document found.')
                ret = False
                continue
            if not cptid:
                self.add_issue('FATAL: Component without ID found.')
                ret = False
                continue
            if not pkgname:
                if doc.get('Merge'):
                    # merge instructions do not need a package name
                    continue
                if cpttype not in ['web-application', 'operating-system', 'repository']:
                    self.add_issue('[%s]: %s' % (cptid, 'Component is missing a \'Package\' key.'))
                    ret = False
                    continue

            try:
                schema_component(doc)
            except Exception as e:
                self.add_issue('[%s]: %s' % (cptid, str(e)))
                ret = False
                continue

            # more tests for the icon key
            icon = doc.get('Icon')
            if cpttype in ['desktop-application', 'web-application']:
                if not doc.get('Icon'):
                    self.add_issue(
                        '[%s]: %s' % (cptid, 'Components containing an application must have an \'Icon\' key.')
                    )
                    ret = False
            if icon:
                if (not icon.get('stock')) and (not icon.get('cached')) and (not icon.get('local')):
                    self.add_issue(
                        '[%s]: %s'
                        % (
                            cptid,
                            'A \'stock\', \'cached\' or \'local\' icon must at least be provided. @ data[\'Icon\']',
                        )
                    )
                    ret = False

            if not self._test_localized(doc, 'Name'):
                ret = False
            if not self._test_localized(doc, 'Summary'):
                ret = False
            if not self._test_localized(doc, 'Description'):
                ret = False
            if not self._test_localized(doc, 'DeveloperName'):
                ret = False

            for shot in doc.get('Screenshots', list()):
                caption = shot.get('caption')
                if caption:
                    if not self._test_localized_dict(doc, caption, 'Screenshots.x.caption'):
                        ret = False

        return ret

    def validate_file(self, fname, reset=True):
        if reset:
            self.reset()
        if fname.endswith('.gz'):
            opener = gzip.open
        elif fname.endswith('.xz'):
            opener = lzma.open
        else:
            opener = open

        with opener(fname, 'rt', encoding='utf-8') as fh:
            data = fh.read()

        return self.validate_data(data)

    def validate_dir(self, dirname):
        ret = True
        asfiles = []
        self.reset()

        # find interesting files
        for root, subfolders, files in os.walk(dirname):
            for fname in files:
                fpath = os.path.join(root, fname)
                if os.path.islink(fpath):
                    self.add_issue('FATAL: Symlinks are not allowed')
                    return False
                if fname.endswith('.yml.gz') or fname.endswith('.yml.xz'):
                    asfiles.append(fpath)

        # validate the files, use multiprocessing to speed up the validation
        with mp.Pool() as pool:
            results = [pool.apply_async(self.validate_file, (fname, False)) for fname in asfiles]
            for res in results:
                if not res.get():
                    ret = False

        return ret


def check_dep11_path(path: T.PathUnion) -> T.Tuple[bool, T.List[str]]:
    validator = DEP11Validator()
    if os.path.isdir(path):
        ret = validator.validate_dir(path)
    elif os.path.islink(path):
        validator.add_issue('FATAL: Symlinks are not allowed')
        ret = False
    else:
        ret = validator.validate_file(path)
    if ret:
        return True, None
    else:
        return False, validator.issues
