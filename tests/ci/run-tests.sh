#!/bin/bash
set -e

#
# This script is supposed to run inside the Laniakea Container
# on the CI system.
#

cd build
source venv/bin/activate
set -x

#
# Build & Test
#

ninja

# Test all the things!
meson test -t10 --print-errorlogs -v

# Test Installation
ninja install
