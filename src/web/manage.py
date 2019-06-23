#!/usr/bin/env python3
#
# Copyright (C) 2015 Matthias Klumpp <mak@debian.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public  License
# as published by the Free Software Foundation; either version
# 3.0 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this program.

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
