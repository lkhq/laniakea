# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import re
import shutil

from flask import Blueprint, request

from ..app import gdata

upload = Blueprint('upload', __name__)

_filename_ascii_strip_re = re.compile(r'[^A-Za-z0-9_.\-~\+]')


def secure_upload_filename(filename):
    """Create a secure version of a filename that can safely be stored
    on a regular file system and passed to :func:`os.path.join`.

    Unlike the function from Werkzeug, this method allows certain characters
    commonly used in Debian package names as well.

    :param filename: the filename to secure
    :return: the secured filename, or an empty string
    """
    if isinstance(filename, str):
        from unicodedata import normalize

        filename = normalize('NFKD', filename).encode('ascii', 'ignore')
        filename = filename.decode('ascii')
    for sep in os.path.sep, os.path.altsep:
        if sep:
            filename = filename.replace(sep, ' ')
    filename = str(_filename_ascii_strip_re.sub('', '_'.join(filename.split()))).strip('._')
    return filename


@upload.route('/<repo_name>', methods=['PUT'], defaults={'filename': None})
@upload.route('/<repo_name>/<path:filename_raw>', methods=['PUT'])
def upload_repo_artifact(repo_name: str, filename_raw=None):
    if not filename_raw:
        return 'no repository name given', 400
    if repo_name not in gdata.repo_names:
        return 'repository not found or does not accept uploads', 422

    filename = secure_upload_filename(filename_raw)
    if not filename:
        return 'bad filename: {}'.format(filename_raw), 422

    target_fname = os.path.join(gdata.incoming_dir, repo_name, filename)
    if os.path.exists(target_fname):
        return 'upload already exists', 403
    with open(target_fname, 'wb') as f:
        while True:
            chunk = request.stream.read(gdata.upload_chunk_size)
            if len(chunk) == 0:
                break
            f.write(chunk)
    shutil.chown(target_fname, group=gdata.master_user)
    os.chmod(target_fname, 0o664)
    return 'created', 201


@upload.route('/')
def index():
    return '<html>Upload endpoint for <a href="https://dput.readthedocs.io/en/latest/">dput(1)</a>.'
