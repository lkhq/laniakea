# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
import signal
import logging as log
from argparse import ArgumentParser
from multiprocessing import Queue, Process

__mainfile = None
server_processes: list[Process] = []


def run_jobs_server(endpoint, pub_queue):
    '''
    Run a server process which serves job requests to
    Laniakea Spark instances.
    '''
    from lighthouse.jobs_server import JobsServer

    server = JobsServer(endpoint, pub_queue)
    server.run()


def run_events_receiver_server(endpoint, pub_queue):
    '''
    Run a server process which handles submissions to the
    event stream and publishes new events publicly.
    '''
    from lighthouse.events_receiver import EventsReceiver

    receiver = EventsReceiver(endpoint, pub_queue)
    receiver.run()


def run_events_publisher_server(endpoints, pub_queue):
    '''
    Run a server process which publishes processed events on
    one or multiple ZeroMQ publisher sockets.
    '''
    from lighthouse.events_publisher import EventsPublisher

    publisher = EventsPublisher(endpoints, pub_queue)
    publisher.run()


def term_signal_handler(signum, frame):
    log.info('Received signal {}, shutting down.'.format(signum))
    for p in server_processes:
        try:
            p.terminate()
            p.join(10)
        finally:
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

    # event stream plumbing
    pub_queue = None
    publish_endpoints = lconf.lighthouse.endpoints_publish
    if publish_endpoints:
        log.info('Creating event stream publisher.')
        pub_queue = Queue()
        spub = Process(
            target=run_events_publisher_server, args=(publish_endpoints, pub_queue), name='EventsPublisher', daemon=True
        )
        spub.start()
        server_processes.append(spub)

        # spawn processes that handle event stream submissions
        log.info('Creating event stream receivers ({}).'.format(len(lconf.lighthouse.endpoints_submit)))
        for i, submit_endpoint in enumerate(lconf.lighthouse.endpoints_submit):
            p = Process(
                target=run_events_receiver_server,
                args=(submit_endpoint, pub_queue),
                name='EventsServer-{}'.format(i),
                daemon=True,
            )
            p.start()
            server_processes.append(p)

    # spawn processes to serve job requests
    log.info('Creating job handlers.')
    for i, jobs_endpoint in enumerate(lconf.lighthouse.endpoints_jobs):
        p = Process(
            target=run_jobs_server, args=(jobs_endpoint, pub_queue), name='JobsServer-{}'.format(i), daemon=True
        )
        p.start()
        server_processes.append(p)

    # set up termination signal handler
    signal.signal(signal.SIGQUIT, term_signal_handler)
    signal.signal(signal.SIGTERM, term_signal_handler)
    signal.signal(signal.SIGINT, term_signal_handler)

    # signal readiness
    log.info('Ready.')
    systemd.daemon.notify('READY=1')

    # wait for processes to terminate (possibly forever)
    while True:
        for p in server_processes:
            p.join(20)
            if not p.is_alive():
                log.info('Server worker process has died, shutting down.')
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
    '''Create Lighthouse CLI argument parser'''

    parser = ArgumentParser(description='Message relay and job assignment')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose', help='Enable debug messages.')
    parser.add_argument(
        '--version', action='store_true', dest='show_version', help='Display the version of Laniakea itself.'
    )
    parser.add_argument(
        '--config',
        action='store',
        dest='config_fname',
        default=None,
        help='Location of the base configuration file to use.',
    )

    parser.set_defaults(func=run_server)

    return parser


def run(mainfile, args):
    from laniakea.utils import set_process_title

    set_process_title('laniakea-lighthouse')
    global __mainfile
    __mainfile = mainfile

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    args.func(args)
