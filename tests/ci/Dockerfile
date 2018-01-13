#
# Docker file for Laniakea CI
#
FROM debian:testing

# prepare
RUN apt-get update -qq

# install build essentials
RUN apt-get install -yq git build-essential ldc

# install dependencies for Laniakea
RUN apt-get install -yq --no-install-recommends \
    pkg-config \

    #meson \
    python3-pip \
    python3-setuptools \

    libssl-dev \
    libcurl4-gnutls-dev \
    libczmq-dev \
    libarchive-dev \
    libpq-dev \
    postgresql

# Temporarily install Meson from master, we need the bugfixed version
RUN pip3 install git+https://github.com/mesonbuild/meson.git

# install vibe.d
RUN apt-get install -yq --no-install-recommends \
    git \
    systemd \
    dlang-libevent \
    dlang-openssl \
    libevent-dev \
    libssl-dev \
    zlib1g-dev

# build & install 3rd-party libraries
RUN mkdir -p /build/extra
WORKDIR /build/extra

# Vibe.d
RUN git clone -b v0.8.1 --depth 1 https://github.com/rejectedsoftware/vibe.d.git vibe.d
RUN mkdir vibe.d/b
RUN cd vibe.d/b/ && meson --prefix=/usr ..
RUN cd vibe.d/b/ && ninja && ninja install

# D-YAML
RUN git clone --depth 1 https://github.com/dlang-community/D-YAML.git dyaml
RUN mkdir dyaml/b
RUN cd dyaml/b/ && meson --prefix=/usr ..
RUN cd dyaml/b/ && ninja && ninja install

# Hibernated
RUN git clone --depth 1 https://github.com/lkorigin/hibernated.git hibernated
RUN mkdir hibernated/b
RUN cd hibernated/b/ && meson --prefix=/usr ..
RUN cd hibernated/b/ && ninja && ninja install

# FluentAsserts
RUN git clone --depth 1 https://github.com/lkorigin/fluent-asserts.git fluent-asserts
RUN mkdir fluent-asserts/b
RUN cd fluent-asserts/b/ && meson --prefix=/usr ..
RUN cd fluent-asserts/b/ && ninja && ninja install

# finish
WORKDIR /build
RUN rm -rf extra
