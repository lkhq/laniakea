Laniakea
========
[![Build Test](https://github.com/lkhq/laniakea/actions/workflows/build-test.yml/badge.svg)](https://github.com/lkhq/laniakea/actions/workflows/build-test.yml)
[![Documentation Status](https://readthedocs.org/projects/laniakea-hq/badge/?version=latest)](https://laniakea-hq.readthedocs.io/en/latest/?badge=latest)
<img align="right" width="136" src="docs/_graphics/logo.svg">

Laniakea is a software suite to manage [Debian](https://www.debian.org/) derivatives.
It provides tooling to maintain an APT archive (and multiple individual package repositories),
perform QA on it, autobuild packages, and provides various tools for better insight into the archive, such as
web applications to view archive details, a [Matrix](https://matrix.org/) bot and a ZeroMQ-based message bus to plug
in custom tooling.

Laniakea is built using experience from prior solutions used to maintain the Tanglu Debian derivative, which was
using a full fork of the Debian archive and therefore needed to replicate a large portion of Debian's own infrastructure,
including multiple QA tools.

Laniakea is built on top of a lot of preexisting Debian tooling, such as APT, Britney2, Dose and many more.

This software is in active development, and used by the PureOS Debian derivative. Its development is supported
by [Purism](https://puri.sm/).
In future, it will also integrate Flatpak bundles into the archive management workflow.

Laniakea is based on the following principles:
 * Have one source for all configuration
 * Integrate components tightly, by making them speak the same protocols
 * Minimize human interventions when maintaining a derivative
 * Allow to manage most (all?) functions via a web interface and Git repositories
 * Reuse existing tools whenever possible, via wrappers

Its tasks include, but are not limited to:
 * Managing multiple APT repositories in a package archive
 * Synchronizing packages from a source distribution suite with the target derivative
 * Migrating packages between suites using Britney2
 * Building disk images for the derivative
 * Validating dependencies of packages
 * Managing default package selections
 * Building packages
 * Automatic package maintenance actions
 * Propagate information between the archive repository, bugtrackers and other websites
 * etc.

![Laniakea Overview](docs/_graphics/laniakea-overview.svg "Laniakea Overview")

##  Development

Laniakea is split into multiple parts which can be run on separate machines to increase service isolation and improve
security. Many services do need at least read access to the PostgreSQL-based Laniakea database, while pretty much all
of them need to read & verify/decrypt messages from the ZeroMQ-based message bus.

At the moment, not much documentation for Laniakea exists, and the project is used and tested internally.
This is supposed to change though, and at that point we will also have better information on how to contribute to the project.

Pull requests and bug reports are of course always welcome, as well as questions in case you are having trouble with
setting up your own Laniakea deployment.

### Building Laniakea & Running Tests

Laniakea uses Meson to test and install the Python components. To build and install Laniakea,
run the following commands:

```bash
meson setup build
sudo ninja -C build install
```

You can also use a virtual environment:

```bash
virtualenv --system-site-packages venv
source venv/bin/activate
pip3 install -r requirements.txt
meson setup build
ninja -C build install
```

The Laniakea testsuite uses `podman` automatically to spawn a PostgreSQL database container for
testing purposes. Make sure you have `podman` installed, an internet connection, and the
required permissions before running the tests.
To run the Laniakea test suite, setup the Meson build directory as shown above, then run:

```bash
meson -C build test -v --maxfail 1
```

If you just want to run the `pytest` based tests, you can also run:

```bash
pytest-3 -sx
```
