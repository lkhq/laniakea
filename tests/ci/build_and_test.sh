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
meson ..
ninja

# Test
ninja test -v

# Test Install
DESTDIR=/tmp/lk-install-root ninja install

cd ..

#
# Style checks
#
#! ./tests/ci/run-dscanner.py . tests/dscanner.ini

#
# Make Documentation
#
#! ./tests/ci/make-documentation.py . build
