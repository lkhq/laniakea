#
# Docker file for Laniakea CI
#
FROM debian:testing

# prepare
ENV LANG C.UTF-8
ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update -qq && apt-get upgrade -y

# install build essentials
RUN apt-get install -yq git build-essential ldc

# install dependencies for Laniakea
RUN apt-get install -yq --no-install-recommends \
    pkg-config \
    meson \
    systemd \
    libcurl4-gnutls-dev \
    libczmq-dev \
    libarchive-dev \
    libpq-dev \
    postgresql \
    libappstream-dev \
    gir1.2-appstream-1.0 \
    ostree \
    flatpak \
    flatpak-builder

RUN apt-get install -yq --no-install-recommends \
    python3-pip \
    python3-setuptools \
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
    python3-flask \
    python3-flask-script \
    python3-flask-restful \
    python3-pytest-flask \
    python3-humanize \
    python3-marshmallow

# install PyD dependencies
RUN apt-get install -yq --no-install-recommends \
    git \
    zlib1g-dev \
    python3-dev

# misc packages
RUN apt-get install -yq --no-install-recommends \
    mkdocs \
    curl

# JavaScript stuff
RUN curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add -
RUN echo "deb https://dl.yarnpkg.com/debian/ stable main" | tee /etc/apt/sources.list.d/yarn.list
RUN apt-get update -qq
RUN apt-get install -yq --no-install-recommends nodejs yarn

# Install dscanner
RUN mkdir -p /usr/local/bin/
RUN curl -L https://github.com/dlang-community/D-Scanner/releases/download/v0.7.1/dscanner-v0.7.1-linux-x86_64.tar.gz -o /tmp/dscanner.tar.gz
RUN tar -xzf /tmp/dscanner.tar.gz -C /usr/local/bin/
RUN rm /tmp/dscanner.tar.gz
RUN dscanner --version

# build & install 3rd-party libraries
RUN mkdir -p /build/extra
WORKDIR /build/extra

# PyD
RUN git clone --depth 1 https://github.com/lkorigin/pyd.git pyd
RUN mkdir pyd/b
RUN cd pyd/b/ && meson --prefix=/usr ..
RUN cd pyd/b/ && ninja && ninja install

# Flake8
RUN pip3 install flake8

# finish
WORKDIR /build
RUN rm -rf extra
