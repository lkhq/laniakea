#!/usr/bin/env python3

import os
import sys
import glob
import subprocess
import signal

def get_sources_list(source_root):
    res = list()
    for fname in glob.iglob(source_root + '/src/**/*.d', recursive=True):
        if os.path.basename(fname) != 'app.d' \
        and not fname.startswith((source_root + '/src/c/', source_root + '/src/web/', source_root + '/src/webswview/')):
            res.append(fname)
    return res


def find_local_include_dirs(source_root):
    res = list()
    for fname in glob.iglob(source_root + '/contrib/subprojects/**/*'):
        basename = os.path.basename(fname)
        if basename == 'src' or basename == 'source':
            res.append(fname)
    return res


def build_include_dir_cmd(source_root):
    incdirs = list()

    extra_inc_dirs = ['/usr/include/d/vibe/',
                      '/usr/include/d/diet/',
                      '/usr/include/d/stdx-allocator/',
                      './src',
                      './build/wrap/']

    for d in extra_inc_dirs + find_local_include_dirs(source_root):
        if os.path.isdir(d):
            incdirs.append('-I' + d)
    return incdirs


def get_string_import_dirs(source_root):
    import_dirs = ['data/', 'src/web/views/', 'src/webswview/views/']

    return ['-J' + os.path.join(source_root, d) for d in import_dirs]


def run_mkdocs(source_root, build_root):
    cmd = ['mkdocs',
	   'build',
	   '--site-dir', os.path.abspath(os.path.join(build_root, 'docs'))]
    print('RUN: ' + ' '.join(cmd))
    subprocess.run(cmd, cwd=os.path.join(source_root, 'docs'), check=True)


def run_ddox(source_root, build_root):
    doc_json_fname = os.path.join(build_root, 'documentation.json')

    ldc_cmd = ['ldc2',
               '-D',
               '-dw',
               '-c',
               '-o-',
               '-Dd=/tmp/lk-unused/',
               '-Xf=' + doc_json_fname,
               '-oq', '-d-version=USE_PGSQL', '-d-version=Derelict_Static', '-d-version=Have_diet_ng']

    ldc_cmd.extend(get_sources_list(source_root) + build_include_dir_cmd(source_root) + get_string_import_dirs(source_root))

    print('RUN: ' + ' '.join(ldc_cmd))
    subprocess.run(ldc_cmd, check=True)

    ddox_cmd = ['ddox',
                'generate-html',
                doc_json_fname,
                os.path.abspath(os.path.join(build_root, 'docs', 'api'))]

    print('RUN: ' + ' '.join(ddox_cmd))
    res = subprocess.run(ddox_cmd)
    if res.returncode == -signal.SIGSEGV:
        print("DDOX crashed!")
        print(res)
    else:
        res.check_returncode()


def run(source_root, build_root):

    # build Markdown documentation
    run_mkdocs(source_root, build_root)

    # build API documentation
    run_ddox(source_root, build_root)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Need at least source-root and build-root directories as parameters!')
        sys.exit(1)
    run(source_root=sys.argv[1], build_root=sys.argv[2])
