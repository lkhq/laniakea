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

# Test
./main_test ../tests/data/

# Test Install
DESTDIR=/tmp/lk-root ninja install
