# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

from flask import Blueprint, request, current_app
from werkzeug.utils import secure_filename

upload = Blueprint('upload', __name__)


@upload.route('/<repo_name>', methods=['PUT'], defaults={'filename': None})
@upload.route('/<repo_name>/<path:filename>', methods=['PUT'])
def upload_repo_artifact(repo_name: str, filename=None):
    if not filename:
        return 'no repository name given', 400
    if repo_name not in current_app.gdata.repo_names:
        return 'repository not found or does not accept uploads', 422

    filename = secure_filename(filename)
    target_fname = os.path.join(current_app.gdata.incoming_dir, repo_name, filename)
    if os.path.exists(target_fname):
        return 'upload already exists', 403
    with open(target_fname, 'wb') as f:
        while True:
            chunk = request.stream.read(current_app.gdata.upload_chunk_size)
            if len(chunk) == 0:
                break
            f.write(chunk)
    return 'created', 201


@upload.route('/')
def index():
    return '<html>Upload endpoint for <a href="https://dput.readthedocs.io/en/latest/">dput(1)</a>.'
