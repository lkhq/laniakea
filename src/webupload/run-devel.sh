#!/usr/bin/env bash
set -e

BASEDIR=$(dirname "$0")
cd $BASEDIR

export FLASK_DEBUG=1
export FLASK_ENV=development
exec flask run --with-threads $@
