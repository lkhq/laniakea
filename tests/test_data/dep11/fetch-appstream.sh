#!/bin/bash
set -e

if [ "${LK_REPO_NAME}" != "master" ]; then
    # we will only have data for the "master" repository
    exit 0
fi

SCRIPT_PATH=$(readlink -f "$0")
BASEDIR=$(dirname "$SCRIPT_PATH")

# A production script would maybe download from a network location here,
# but we just copy our sample data to the destination.
mkdir -p ${LK_DATA_TARGET_DIR}/unstable/main
cp ${BASEDIR}/*.xz ${BASEDIR}/*.tar.gz ${LK_DATA_TARGET_DIR}/unstable/main/
