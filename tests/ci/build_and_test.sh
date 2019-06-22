#!/bin/sh
set -e

echo "D compiler: $DC"
set -x
$DC --version

#
# This script is supposed to run inside the Laniakea Docker container
# on the CI system.
#

#
# Build & Test
#

mkdir build && cd build
meson -Dtest-flake8=true \
      -Dtest-dscanner=true \
      ..
ninja

# Test all the things!
meson test -v

# Test Installation
DESTDIR=/tmp/lk-install-root ninja install

cd ..

#
# Make Documentation
#
#! ./tests/ci/make-documentation.py . build
