#!/usr/bin/env python3

import os
import sys
import glob

meson_build_root = os.environ.get('MESON_BUILD_ROOT')
meson_source_root = os.environ.get('MESON_SOURCE_ROOT')
meson_subdir = os.environ.get('MESON_SUBDIR')

if not meson_build_root or not meson_source_root:
    print('This script should only be run by the Meson build system.')
    sys.exit(1)

files = glob.glob(os.path.join(meson_build_root, 'wrap', '**', '*.d'), recursive=True)

for fname in sorted(files):
    # newer versions of Meson (>= 0.43) don't like absolute paths
    print(os.path.relpath(fname, os.path.join(meson_source_root, meson_subdir)))
