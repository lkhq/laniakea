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
    python3-pip \
    python3-setuptools \
    python3-virtualenv \
    python3-pytest \
    python3-gi \
    python3-tomlkit \
    python3-cairo-dev \
    python3-sqlalchemy \
    python3-alembic \
    python3-psycopg2 \
    python3-nacl \
    python3-debian \
    python3-apt \
    python3-zmq \
    python3-yaml \
    python3-systemd \
    python3-flask \
    python3-flask-restful \
    python3-flask-login \
    python3-pytest-flask \
    python3-humanize \
    python3-marshmallow \
    python3-pebble \
    python3-requests \
    python3-apscheduler \
    python3-click \
    python3-rich \
    python3-voluptuous
