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
    libglib2.0-dev \
    libgirepository1.0-dev \
    libappstream-dev \
    gir-to-d \
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
    dub \
    mkdocs \
    curl

# Meson, to work around bugs in current version in Debian
RUN git clone --depth 1 https://github.com/mesonbuild/meson.git /opt/meson/
RUN rm /usr/bin/meson
RUN ln -s /opt/meson/meson.py /usr/bin/meson

# Install dscanner
RUN mkdir -p /usr/local/bin/
RUN curl -L https://github.com/dlang-community/D-Scanner/releases/download/v0.5.1/dscanner-v0.5.1-linux-x86_64.tar.gz -o /tmp/dscanner.tar.gz
RUN tar -xzf /tmp/dscanner.tar.gz -C /usr/local/bin/
RUN rm /tmp/dscanner.tar.gz
RUN dscanner --version

# build & install 3rd-party libraries
RUN mkdir -p /build/extra
WORKDIR /build/extra

# GLibD
RUN git clone --depth 1 https://github.com/ximion/GlibD.git glibd
RUN mkdir glibd/b
RUN cd glibd/b/ && meson --prefix=/usr ..
RUN cd glibd/b/ && ninja && ninja install

# FluentAsserts
RUN git clone --depth 1 https://github.com/lkorigin/fluent-asserts.git fluent-asserts
RUN mkdir fluent-asserts/b
RUN cd fluent-asserts/b/ && meson --prefix=/usr ..
RUN cd fluent-asserts/b/ && ninja && ninja install

# finish
WORKDIR /build
RUN rm -rf extra
