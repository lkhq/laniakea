#!/bin/sh
#
# Install Laniakea native dependencies
#
set -e
set -x

export DEBIAN_FRONTEND=noninteractive

# update caches
apt-get update -qq

# install build essentials
apt-get install -yq \
    eatmydata \
    build-essential \
    gdb

# install dependencies for Laniakea
eatmydata apt-get install -yq podman fuse-overlayfs
eatmydata apt-get install -yq --no-install-recommends \
    pkg-config \
    meson \
    systemd-dev \
    libsystemd-dev \
    postgresql-client \
    apt-utils \
    libappstream-dev \
    gir1.2-appstream-1.0 \
    ostree \
    flatpak \
    flatpak-builder \
    git \
    debhelper \
    dpkg-dev \
    devscripts \
    lintian \
    bubblewrap \
    npm

eatmydata apt-get install -yq --no-install-recommends \
    flake8 \
    isort \
    mypy \
    pylint \
    python3-alembic \
    python3-apscheduler \
    python3-apt \
    python3-click \
    python3-cryptography \
    python3-debian \
    python3-firehose \
    python3-flask \
    python3-flask-caching \
    python3-flask-login \
    python3-gi \
    python3-humanize \
    python3-jinja2 \
    python3-marshmallow \
    python3-mautrix \
    python3-mesonpy \
    python3-nacl \
    python3-pebble \
    python3-pip \
    python3-psycopg2 \
    python3-pylint-flask \
    python3-pytest \
    python3-pytest-flask \
    python3-pytz \
    python3-requests \
    python3-rich \
    python3-setproctitle \
    python3-sqlalchemy  \
    python3-systemd \
    python3-tomlkit \
    python3-tornado \
    python3-typeshed \
    python3-virtualenv \
    python3-voluptuous \
    python3-yaml \
    python3-zmq

# install if available
eatmydata apt-get install -yq --no-install-recommends \
    python3-flask-rebar || true
