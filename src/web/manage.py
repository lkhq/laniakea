#!/usr/bin/env python3
#
# Copyright (C) 2015-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from flask_script import Manager
from lkweb import create_app
from lkweb.config import DebugConfig

app = create_app(config=DebugConfig)
manager = Manager(app)


@manager.command
def run():
    """Run on local machine."""

    app.run()


manager.add_option('-c', '--config',
                   dest='config',
                   required=False,
                   help="config file")


if __name__ == '__main__':
    manager.run()
