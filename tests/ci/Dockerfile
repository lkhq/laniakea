#
# Docker file for Laniakea CI
#
FROM debian:sid

# prepare
RUN apt-get update -qq

# install build essentials
RUN apt-get install -yq git build-essential ldc

# install dependencies used by both appstream and appstream-generator
RUN apt-get install -yq --no-install-recommends \
    meson \
    libcurl4-gnutls-dev \
    libarchive-dev

# finish
RUN mkdir /build
WORKDIR /build
