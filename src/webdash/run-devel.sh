#!/usr/bin/env bash
set -e

BASEDIR=$(dirname "$0")
cd $BASEDIR

export FLASK_DEBUG=1
export FLASK_ENV=development
exec python3 -m flask run --with-threads $@
