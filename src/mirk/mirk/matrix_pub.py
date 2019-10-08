# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Matthias Klumpp <matthias@tenstral.net>
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

import sys
import zmq
import json
import logging as log
from laniakea.msgstream import create_event_listen_socket
from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from .config import MirkConfig


message_templates = {'_lk.job.package-build-success':
                     'Package build for <b>{pkgname} {version}</b> on <code>{architecture}</code> was <font color="#27ae60">successful</font>.',

                     '_lk.job.package-build-failed':
                     'Package build for <b>{pkgname} {version}</b> on <code>{architecture}</code> has <font color="#da4453">failed</font>.',

                     '_lk.synchrotron.src-package-imported':
                     'Imported package <b>{name}</b> from {src_os} <em>{src_suite}</em> → <em>{dest_suite}</em>, new version is <code>{version}</code>.',

                     '_lk.synchrotron.src-package-imported:forced':
                     'Enforced import of package <b>{name}</b> from {src_os} <em>{src_suite}</em> → <em>{dest_suite}</em>, new version is <code>{version}</code>.',

                     '_lk.synchrotron.new-autosync-issue':
                     '''New automatic synchronization issue for <font color="#da4453"><b>{name}</b></font> from {src_os} <em>{src_suite}</em> → <em>{dest_suite}</em>
                     (source: <code>{src_version}</code>, destination: <code>{dest_version}</code>). Type: {kind}''',

                     '_lk.synchrotron.resolved-autosync-issue':
                     '''The <em>{kind}</em> synchronization issue for <b>{name}</b> from {src_os} <em>{src_suite}</em> → <em>{dest_suite}</em> was <font color="#27ae60">resolved</font>.''',

                     '_lk.jobs.job-assigned':
                     '''Assigned {job_kind} job <a href="{webview_url}/jobs/job/{job_id}">{job_id}</a> on architecture <code>{job_architecture}</code> to <em>{client_name}</em>''',

                     '_lk.jobs.job-accepted':
                     '''Job <a href="{webview_url}/jobs/job/{job_id}">{job_id}</a> was <font color="#27ae60">accepted</font> by <em>{client_name}</em>''',

                     '_lk.jobs.job-rejected':
                     '''Job <a href="{webview_url}/jobs/job/{job_id}">{job_id}</a> was <font color="#da4453">rejected</font> by <em>{client_name}</em>''',

                     '_lk.jobs.job-finished':
                     '''Job <a href="{webview_url}/jobs/job/{job_id}">{job_id}</a> finished with result <em>{result}</em>''',

                     '_lk.rubicon.upload-accepted':
                     '''Accepted upload for <font color="#27ae60">successful</font> job <a href="{webview_url}/jobs/job/{job_id}">{job_id}</a>.''',

                     '_lk.rubicon.upload-accepted:failed':
                     '''Accepted upload for <font color="#da4453">failed</font> job <a href="{webview_url}/jobs/job/{job_id}">{job_id}</a>.''',

                     '_lk.rubicon.upload-rejected':
                     '''<b>Rejected</b> upload <code>{dud_filename}</code>. Reason: {reason}''',

                     '_lk.isotope.recipe-created':
                     '''Created new <em>{kind}</em> image build recipe "{name}" for {os}/{suite} of flavor {flavor} on <code>{architectures}</code>''',

                     '_lk.isotope.build-job-added':
                     '''Created image build job <a href="{webview_url}/jobs/job/{job_id}">{job_id}</a> on <code>{architecture}</code> for "{name}" ({os}/{suite} of flavor {flavor})''',

                     '_lk.archive.source-package-published':
                     '''Source package <b>{name}</b> {version} ({component}) was <font color="#27ae60">published</font> in the archive, available in suites <em>{suites_str}</em>.''',

                     '_lk.archive.source-package-published-in-suite':
                     '''Source package <b>{name}</b> {version} was <font color="#27ae60">added</font> to suite <em>{new_suite} ({component})</em>.''',

                     '_lk.archive.source-package-suite-removed':
                     '''Source package <b>{name}</b> {version} was <font color="#da4453">removed</font> from suite <em>{old_suite} ({component})</em>.''',

                     '_lk.archive.removed-source-package':
                     '''Package <b>{name}</b> {version} ({component}) was <font color="#da4453">removed</font> from the archive.''',

                     '_lk.spears.new-excuse':
                     '''Package <b>{source_package}</b> {version_new} was <font color="#da4453">blocked</font> from its <em>{suite_source}</em> → <em>{suite_target}</em> migration. Version in target is: {version_old}
                     <a href="{webview_url}/migrations/excuse/{uuid}">Details</a>''',

                     '_lk.spears.excuse-removed':
                     '''Migration excuse for package <b>{source_package}</b> {version_new} was <font color="#27ae60">invalidated</font>. The package migrated from <em>{suite_source}</em> → <em>{suite_target}</em>.
                     Previous version in target was: <code>{version_old}</code>''',

                     }


class MatrixPublisher:
    '''
    Publish messages from the Laniakea Message Stream in Matrix rooms.
    '''

    def __init__(self):
        self._zctx = zmq.Context()
        self._lhsub_socket = create_event_listen_socket(self._zctx)
        self._mconf = MirkConfig()
        self._mconf.load()

    def _tag_data_to_html_message(self, tag, data):
        ''' Convert the JSON message into a nice HTML string for display. '''

        if data.get('forced'):
            tag = tag + ':forced'
        if data.get('job_failed'):
            tag = tag + ':failed'
        if tag == '_lk.archive.source-package-published':
            data['suites_str'] = ', '.join(data['suites'])
        elif tag == '_lk.spears.new-excuse' or tag == '_lk.spears.excuse-removed':
            if data['version_new'] == '-':
                data['version_new'] = '(<font color="#da4453">removal</font>)'

        text = ''
        templ = message_templates.get(tag)
        if templ:
            text = templ.format(webswview_url=self._mconf.webswview_url,
                                webview_url=self._mconf.webview_url,
                                **data)
        else:
            text = 'Received event type <code>{}</code> with data <code>{}</code>'.format(tag, str(data))

        return text

    def _on_room_message(self, room, event):
        pass

    def _on_event_received(self, event):
        tag = event['tag']
        data = event['data']
        text = self._tag_data_to_html_message(tag, data)
        self._rooms_publish_text(text)

    def _rooms_publish_text(self, text):
        for room in self._rooms:
            room.send_html(text)

    def run(self):
        client = MatrixClient(self._mconf.host)

        try:
            log.debug('Logging into Matrix')
            client.login_with_password(self._mconf.username, self._mconf.password)
        except MatrixRequestError as e:
            if e.code == 403:
                log.error('Bad username or password: {}'.format(str(e)))
                sys.exit(2)
            else:
                log.error('Could not log in - check the server details are correct: {}'.format(str(e)))
                sys.exit(2)
        except Exception as e:
            log.error('Error while logging in: {}'.format(str(e)))
            sys.exit(2)

        log.debug('Joining rooms')
        self._rooms = []
        for room_id in self._mconf.rooms:
            try:
                room = client.join_room(room_id)
            except MatrixRequestError as e:
                if e.code == 400:
                    log.error('Room ID/Alias ("{}") in the wrong format. Can not join room: {}'.format(room_id, str(e)))
                    sys.exit(2)
                else:
                    log.error('Could not find room "{}"'.format(room_id))
                    sys.exit(2)

            room.add_listener(self._on_room_message)
            self._rooms.append(room)

        log.info('Logged into Matrix, ready to publish information')
        client.start_listener_thread()

        while True:
            topic, msg_b = self._lhsub_socket.recv_multipart()
            # TODO: Validate signature here!
            event = json.loads(str(msg_b, 'utf-8'))
            self._on_event_received(event)
