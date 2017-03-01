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
    dlang-libevent \
    dlang-openssl \
    libevent-dev \
    libssl1.0-dev \
    zlib1g-dev

RUN git clone https://github.com/ximion/vibe.d.git vibe.d

RUN mkdir vibe.d/b
RUN cd vibe.d/b/ && meson --prefix=/usr ..
RUN cd vibe.d/b/ && ninja && ninja install

# finish
RUN mkdir /build
WORKDIR /build
