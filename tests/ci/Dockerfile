#
# Docker file for Laniakea CI
#
FROM debian:sid

# prepare
RUN apt-get update -qq

# install build essentials
RUN apt-get install -yq git build-essential ldc

# install dependencies for Laniakea
RUN apt-get install -yq --no-install-recommends \
    pkg-config \
    meson \
    libssl-dev \
    libcurl4-gnutls-dev \
    libarchive-dev

# install vibe.d
RUN apt-get install -yq --no-install-recommends \
    git \
    systemd \
    dlang-libevent \
    dlang-openssl \
    libevent-dev \
    libssl1.0-dev \
    zlib1g-dev

# build & install 3rd-party libraries
RUN mkdir -p /build/extra
WORKDIR /build/extra

# Vibe.d
RUN git clone --depth 1 -b 0.7.x https://github.com/ximion/vibe.d.git vibe.d
RUN mkdir vibe.d/b
RUN cd vibe.d/b/ && meson --prefix=/usr ..
RUN cd vibe.d/b/ && ninja && ninja install

# Tinyendian
RUN git clone --depth 1 https://github.com/ximion/tinyendian.git tinyendian
RUN mkdir tinyendian/b
RUN cd tinyendian/b/ && meson --prefix=/usr ..
RUN cd tinyendian/b/ && ninja && ninja install

# D-YAML
RUN git clone --depth 1 https://github.com/lkorigin/D-YAML.git dyaml
RUN mkdir dyaml/b
RUN cd dyaml/b/ && meson --prefix=/usr ..
RUN cd dyaml/b/ && ninja && ninja install

# finish
WORKDIR /build
RUN rm -rf extra
