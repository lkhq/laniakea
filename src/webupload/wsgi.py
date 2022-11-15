# -*- coding: utf-8 -*-

import os
import sys

BASE_DIR = os.path.join(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from lkwebupload import create_app

application = create_app()
