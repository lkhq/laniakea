# -*- coding: utf-8 -*-
#
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

import zmq
import logging as log


class EventsPublisher:
    '''
    Lighthouse helper which handles the actual event publishing from multiple
    receiver processes.
    '''

    def __init__(self, endpoints, pub_queue):
        self._sockets = []
        self._endpoints = endpoints
        self._ctx = zmq.Context.instance()
        self._pub_queue = pub_queue

    def run(self):
        if self._sockets:
            log.warning('Tried to run an already running event publisher again.')
            return

        for endpoint in self._endpoints:
            socket = self._ctx.socket(zmq.PUB)
            socket.bind(endpoint)
            self._sockets.append(socket)

        while True:
            msg = self._pub_queue.get()
            for socket in self._sockets:
                try:
                    socket.send_multipart(msg)
                except Exception as e:
                    log.warning('Unable to publish event: {} (data was: {})'.format(str(e), str(msg)))
