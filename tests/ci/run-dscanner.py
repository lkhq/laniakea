#!/usr/bin/env python3

import os
import sys
import glob
import subprocess

def find_local_include_dirs(source_root):
    res = list()
    for fname in glob.iglob(source_root + '/contrib/subprojects/**/*'):
        basename = os.path.basename(fname)
        if basename == 'src' or basename == 'source':
            res.append(fname)
    return res


def find_include_dirs(source_root):
    incdirs = find_local_include_dirs(source_root)
    incdirs.append(os.path.join(source_root, 'src'))

    extra_inc = ['vibe',
                 'diet',
                 'stdx-allocator',
                 'fluentasserts']

    for d in extra_inc:
        for inc_root in ['/usr/include/d/', '/usr/local/include/d/']:
            idir = os.path.join(inc_root, d)
            if os.path.isdir(idir):
                incdirs.append(idir)

    # LDC internal includes
    incdirs.extend(glob.glob('/usr/lib/ldc/*/include/d/'))
    incdirs.extend(glob.glob('/usr/lib/ldc/*/include/d/ldc/'))

    return ['-I' + d for d in incdirs]


def run(source_root, dscanner_config):
    print('===========================')
    print('=       D-Scanner         =')
    print('===========================')

    subprocess.run(['dscanner', '--version'])

    cmd = ['dscanner',
           '--styleCheck', os.path.join(source_root, 'src'),
           '--config', dscanner_config]
    cmd.extend(find_include_dirs(source_root))

    pres = subprocess.run(cmd, cwd=source_root)

    if pres.returncode == 0:
        print('\033[92m:) Success \033[0m')
        sys.exit(0)
    else:
        print('\033[91m:( D-Scanner found issues \033[0m')
        print(pres)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Need at least source-root and dscanner configuration as parameters!')
        sys.exit(1)
    run(source_root=sys.argv[1], dscanner_config=sys.argv[2])
