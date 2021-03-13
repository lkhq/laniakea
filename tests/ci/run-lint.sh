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
# Linting
#

meson test -t10 -v --suite linters
