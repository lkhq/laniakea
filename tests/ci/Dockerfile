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
    libssl-dev \
    libcurl4-gnutls-dev \
    libczmq-dev \
    libarchive-dev \
    libpq-dev \
    postgresql

# install vibe.d dependencies
RUN apt-get install -yq --no-install-recommends \
    git \
    systemd \
    dlang-libevent \
    dlang-openssl \
    libevent-dev \
    libssl-dev \
    zlib1g-dev

# misc packages
RUN apt-get install -yq --no-install-recommends \
    dub

# Meson, to work around bugs in current version in Debian
RUN git clone --depth 1 https://github.com/mesonbuild/meson.git /opt/meson/
RUN rm /usr/bin/meson
RUN ln -s /opt/meson/meson.py /usr/bin/meson

# build & install 3rd-party libraries
RUN mkdir -p /build/extra
WORKDIR /build/extra

# Vibe.d
RUN git clone -b v0.8.1 --depth 1 https://github.com/vibe-d/vibe.d.git vibe.d
RUN mkdir vibe.d/b
RUN cd vibe.d/b/ && meson --prefix=/usr ..
RUN cd vibe.d/b/ && ninja && ninja install

RUN pkg-config --cflags vibe-core

# finish
WORKDIR /build
RUN rm -rf extra
