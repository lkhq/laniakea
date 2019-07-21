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

import sys
import signal
import logging as log
from argparse import ArgumentParser
from multiprocessing import Process

__mainfile = None
server_processes = []


def run_jobs_server(endpoint):
    '''
    Run a server process which serves job requests to
    Laniakea Spark instances.
    '''
    from lighthouse.jobs_server import JobsServer

    server = JobsServer(endpoint)
    server.run()


def run_events_server(endpoint):
    '''
    Run a server process which handles submissions to the
    event stream and publishes new events publicly.
    '''
    from lighthouse.events_server import EventsServer

    server = EventsServer(endpoint)
    server.run()


def term_signal_handler(signum, frame):
    log.info('Received signal {}, shutting down.'.format(signum))
    for p in server_processes:
        p.terminate()
        p.join(10)
        p.kill()


def run_server(options):
    import systemd.daemon
    from laniakea.localconfig import LocalConfig

    if options.config_fname:
        LocalConfig(options.config_fname)

    if options.verbose:
        from laniakea.logging import set_verbose
        set_verbose(True)

    lconf = LocalConfig()

    # TODO: Disable server features requiring the database if Lighthouse is
    # configured as relay, making it only forward requests to other instances.

    # spawn processes to serve job requests
    log.info('Creating job handlers.')
    for i, jobs_endpoint in enumerate(lconf.lighthouse.endpoints_jobs):
        p = Process(target=run_jobs_server,
                    args=(jobs_endpoint,),
                    name='JobsServer-{}'.format(i),
                    daemon=True)
        p.start()
        server_processes.append(p)

    # spawn processes that handle event stream submissions
    log.info('Creating event stream handlers.')
    for submit_endpoint in lconf.lighthouse.endpoints_submit:
        p = Process(target=run_events_server,
                    args=(submit_endpoint,),
                    name='EventsServer-{}'.format(i),
                    daemon=True)
        p.start()
        server_processes.append(p)

    # set up termination signal handler
    signal.signal(signal.SIGQUIT, term_signal_handler)
    signal.signal(signal.SIGTERM, term_signal_handler)
    signal.signal(signal.SIGINT, term_signal_handler)

    log.info('Ready.')
    systemd.daemon.notify('READY=1')

    # wait for processes to terminate
    for p in server_processes:
        p.join(20)
        if not p.is_alive():
            log.info('Worker process has died, shutting down.')
            # one of our workers must have failed, shut down
            for pr in server_processes:
                pr.terminate()
                pr.join(10)
                pr.kill()
            sys.exit(p.exitcode)


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__
        print(__version__)
        sys.exit(0)


def create_parser():
    ''' Create Lighthouse CLI argument parser '''

    parser = ArgumentParser(description='Message relay and job assignment')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')
    parser.add_argument('--config', action='store', dest='config_fname', default=None,
                        help='Location of the base configuration file to use.')

    parser.set_defaults(func=run_server)

    return parser


def run(mainfile, args):
    global __mainfile
    __mainfile = mainfile

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    args.func(args)
