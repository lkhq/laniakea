#!/bin/bash
set -e
set -x

#
# This script is supposed to run inside the Laniakea Container
# on the CI system.
#

#
# Prepare Virtualenv and install dependencies
#

mkdir build && cd build
virtualenv --system-site-packages venv

set +x
source venv/bin/activate
set -x

pip install -r ../requirements.txt
pip install -r ../requirements.tests.txt

if [ "$1" = "lint-only" ]; then
    meson \
        --prefix=/tmp/lk-install-root \
        -Ddownload-js=false \
        -Dlinting=true \
        ..
else
    meson \
        --prefix=/tmp/lk-install-root \
        ..
fi;
