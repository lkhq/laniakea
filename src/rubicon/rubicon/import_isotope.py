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

import os
import time
import logging as log
from laniakea import LkModule
from laniakea.db import ImageBuildRecipe
from email.utils import parsedate
from .utils import safe_rename


def handle_isotope_upload(session, success, conf, dud, job, event_emitter):
    '''
    Handle an upload of disk images.
    '''

    result_move_to = ''
    recipe = session.query(ImageBuildRecipe) \
        .filter(ImageBuildRecipe.uuid == job.trigger).one_or_none()
    if not recipe:
        log.error('Could not find recipe for "{}". Can not process the file.'.format(dud.get_filename()))
        return

    result_move_to = recipe.result_move_to

    event_data = {'kind': str(recipe.kind),
                  'distribution': recipe.distribution,
                  'suite': recipe.suite,
                  'flavor': recipe.flavor,
                  'architectures': recipe.architectures,
                  'job_id': str(job.uuid)}

    if not success:
        # validation failed, we couldn't accept this upload
        event_emitter.submit_event_for_mod(LkModule.ISOTOPE, 'image-build-failed', event_data)
        return

    image_dir_tmpl = os.path.join(conf.isotope_root_dir, result_move_to).strip()
    if not image_dir_tmpl:
        log.error('Found an Isotope ISO image build, but we have no idea where to put it. Is "IsotopeRootDir" set correctly?')
        return

    try:
        time_tuple = parsedate(dud.get('Date'))
        date = time.gmtime(time.mktime(time_tuple))
    except Exception as e:
        log.error('Unable to get time from Dud: {}'.format(str(e)))
        date = time.gmtime(time.time())

    image_dir = image_dir_tmpl.replace('%{DATETIME}', time.strftime('%Y-%m-%d_%H.%M', date)) \
        .replace('%{DATE}', time.strftime('%Y-%m-%d', date)) \
        .replace('%{TIME}', time.strftime('%H.%M', date))

    os.makedirs(image_dir, exist_ok=True)

    # move the image build artifacts
    for fname in dud.get_files():
        if fname.endswith(('.log', '.xml')):
            continue  # logs are handled already by the generic tool

        safe_rename(fname, image_dir)

    # if we're here, the build worked and we can announce the new image
    event_emitter.submit_event_for_mod(LkModule.ISOTOPE, 'image-build-success', event_data)
