#
# Copyright (C) 2021 Matthias Klumpp <matthias@tenstral.net>
# Copyright (C) 2017 pytest-docker contributors
#
# SPDX-License-Identifier: MIT OR LGPL-3.0+

import os
import re
import json
import time
import uuid
import timeit
import contextlib
import subprocess

import attr
import pytest


def execute(command, success_codes=(0,)):
    """Run a shell command."""
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
        status = 0
    except subprocess.CalledProcessError as error:
        output = error.output or b""
        status = error.returncode
        command = error.cmd

    if status not in success_codes:
        raise Exception('Command {} returned {}: """{}""".'.format(command, status, output.decode("utf-8")))
    return output


def get_podman_ip():
    # When talking to the Podman daemon via a UNIX socket, route all TCP
    # traffic to podman containers via the TCP loopback interface.
    podman_host = os.environ.get("PODMAN_HOST", "").strip()
    if not podman_host:
        return "127.0.0.1"

    match = re.match(r"^tcp://(.+?):\d+$", podman_host)
    if not match:
        raise ValueError('Invalid value for PODMAN_HOST: "%s".' % (podman_host,))
    return match.group(1)


@pytest.fixture(scope="session")
def podman_ip():
    """Determine the IP address for TCP connections to Podman containers."""

    return get_podman_ip()


@attr.s(frozen=True)
class Services:

    _podman_compose = attr.ib()
    _services = attr.ib(init=False, default=attr.Factory(dict))

    def port_for(self, service, container_port):
        """Return the "host" port for `service` and `container_port`.

        E.g. If the service is defined like this:

            version: '2'
            services:
              httpbin:
                build: .
                ports:
                  - "8000:80"

        this method will return 8000 for container_port=80.
        """

        # Lookup in the cache.
        cache = self._services.get(service, {}).get(container_port, None)
        if cache is not None:
            return cache

        output = self._podman_compose.execute("ps -q")
        host_port = ''
        data = None
        for line in output.decode('utf-8').split('\n'):
            # sanity check to ignore any debug output
            if not line or len(line) > 16 or len(line) < 6:
                continue

            data = json.loads(execute('podman inspect {}'.format(line.strip())))[0]
            if '{}:'.format(service) not in data['ImageName']:
                continue
            ports = data['NetworkSettings']['Ports']
            port_data = ports.get('{}/tcp'.format(container_port), ports.get('{}/udp'.format(container_port)))
            if not port_data:
                continue
            host_port = port_data[0]['HostPort']
            break

        if not host_port:
            print('podman-compose ps output:', output.decode('utf-8'))
            print('podman inspect output:', data)
            raise ValueError('Could not detect port for "%s:%d".' % (service, container_port))
        host_port = int(host_port.strip())

        # Store it in cache in case we request it multiple times.
        self._services.setdefault(service, {})[container_port] = host_port

        return host_port

    def wait_until_responsive(self, check, timeout, pause, clock=timeit.default_timer):
        """Wait until a service is responsive."""

        ref = clock()
        now = ref
        while (now - ref) < timeout:
            if check():
                return
            time.sleep(pause)
            now = clock()

        raise Exception("Timeout reached while waiting on service!")


def str_to_list(arg):
    if isinstance(arg, (list, tuple)):
        return arg
    return [arg]


@attr.s(frozen=True)
class PodmanComposeExecutor:

    _compose_files = attr.ib(converter=str_to_list)
    _compose_project_name = attr.ib()

    def execute(self, subcommand):
        command = "podman-compose"
        for compose_file in self._compose_files:
            command += ' -f "{}"'.format(compose_file)
        command += ' -p "{}" {}'.format(self._compose_project_name, subcommand)
        return execute(command)


@pytest.fixture(scope="session")
def podman_compose_file(pytestconfig):
    """Get an absolute path to the  `podman-compose.yml` file. Override this
    fixture in your tests if you need a custom location."""

    return os.path.join(str(pytestconfig.rootdir), "tests", "podman-compose.yml")


@pytest.fixture(scope="session")
def podman_compose_project_name():
    """Generate a project name using the current process PID. Override this
    fixture in your tests if you need a particular project name."""

    return "pytest{}".format(os.getpid())


@pytest.fixture(scope="package")
def podman_compose_package_project_name():
    """Generate a project name using the current process PID and a random uid.
    Override this fixture in your tests if you need a particular project name.
    This is a package scoped fixture. The project name will contain the scope"""

    return "pytest{}-package{}".format(os.getpid(), str(uuid.uuid4()).split("-")[1])


@pytest.fixture(scope="module")
def podman_compose_module_project_name():
    """Generate a project name using the current process PID. Override this
    fixture in your tests if you need a particular project name.
    This is a module scoped fixture. The project name will contain the scope"""

    return "pytest{}-module{}".format(os.getpid(), str(uuid.uuid4()).split("-")[1])


@pytest.fixture(scope="class")
def podman_compose_class_project_name():
    """Generate a project name using the current process PID. Override this
    fixture in your tests if you need a particular project name.
    This is a class scoped fixture. The project name will contain the scope"""

    return "pytest{}-class{}".format(os.getpid(), str(uuid.uuid4()).split("-")[1])


@pytest.fixture(scope="function")
def podman_compose_function_project_name():
    """Generate a project name using the current process PID. Override this
    fixture in your tests if you need a particular project name.
    This is a function scoped fixture. The project name will contain the scope"""

    return "pytest{}-function{}".format(os.getpid(), str(uuid.uuid4()).split("-")[1])


def get_cleanup_command():

    return "down -t 240"


@pytest.fixture(scope="session")
def podman_cleanup():
    """Get the podman_compose command to be executed for test clean-up actions.
    Override this fixture in your tests if you need to change clean-up actions."""

    return get_cleanup_command()


@contextlib.contextmanager
def get_podman_services(podman_compose_file, podman_compose_project_name, podman_cleanup):
    podman_compose = PodmanComposeExecutor(podman_compose_file, podman_compose_project_name)

    # Spawn containers.
    podman_compose.execute("up --build -d")

    try:
        # Let test(s) run.
        yield Services(podman_compose)
    finally:
        # Clean up.
        podman_compose.execute(podman_cleanup)


@pytest.fixture(scope="session")
def podman_services(podman_compose_file, podman_compose_project_name, podman_cleanup):
    """Start all services from a podman compose file (`podman-compose up`).
    After test are finished, shutdown all services (`podman-compose down`)."""

    with get_podman_services(podman_compose_file, podman_compose_project_name, podman_cleanup) as podman_service:
        yield podman_service


@pytest.fixture(scope="package")
def podman_package_services(podman_compose_file, podman_compose_package_project_name, podman_cleanup):
    """Start all services from a podman compose file (`podman-compose up`).
    After test are finished, shutdown all services (`podman-compose down`).
    This is a package scoped fixture, container are destroy at the end of pytest class."""

    with get_podman_services(
        podman_compose_file, podman_compose_package_project_name, podman_cleanup
    ) as podman_class_services:
        yield podman_class_services


@pytest.fixture(scope="module")
def podman_module_services(podman_compose_file, podman_compose_module_project_name, podman_cleanup):
    """Start all services from a podman compose file (`podman-compose up`).
    After test are finished, shutdown all services (`podman-compose down`).
    This is a module scoped fixture, container are destroy at the end of pytest class."""

    with get_podman_services(
        podman_compose_file, podman_compose_module_project_name, podman_cleanup
    ) as podman_class_services:
        yield podman_class_services


@pytest.fixture(scope="class")
def podman_class_services(podman_compose_file, podman_compose_class_project_name, podman_cleanup):
    """Start all services from a podman compose file (`podman-compose up`).
    After test are finished, shutdown all services (`podman-compose down`).
    This is a class scoped fixture, container are destroy at the end of pytest class."""

    with get_podman_services(
        podman_compose_file, podman_compose_class_project_name, podman_cleanup
    ) as podman_class_services:
        yield podman_class_services


@pytest.fixture(scope="function")
def podman_function_services(podman_compose_file, podman_compose_function_project_name, podman_cleanup):
    """Start all services from a podman compose file (`podman-compose up`).
    After test are finished, shutdown all services (`podman-compose down`).
    This is a function scoped fixture, container are destroy at the end of single test."""

    with get_podman_services(
        podman_compose_file, podman_compose_function_project_name, podman_cleanup
    ) as podman_function_services:
        yield podman_function_services
