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
eatmydata apt-get install -yq --no-install-recommends \
    pkg-config \
    meson \
    systemd \
    postgresql \
    libappstream-dev \
    gir1.2-appstream-1.0 \
    ostree \
    flatpak \
    flatpak-builder

eatmydata apt-get install -yq --no-install-recommends \
    python3-pip \
    python3-setuptools \
    python3-virtualenv \
    python3-pytest \
    python3-gi \
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
    python3-flask-script \
    python3-flask-restful \
    python3-pytest-flask \
    python3-humanize \
    python3-marshmallow
