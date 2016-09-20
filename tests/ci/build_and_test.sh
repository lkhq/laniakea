#!/bin/sh
set -e

echo "D compiler: $DC"
set -x
$DC --version

#
# This script is supposed to run inside the Laniakea Docker container
# on the CI system.
#

mkdir build && cd build
meson ..
ninja

DESTDIR=/tmp/lk-root ninja install
