
#
# Build interfaces from GIR
#
gir_to_d_prog = find_program('girtod')
gir_wrap_dir = source_root + '/contrib/wrap/'
gir_d_intf_dir = build_root + '/wrap/'

message('Generating D interfaces from GIR...')
girtod_gen = run_command(gir_to_d_prog.path(),
                         '-i', gir_wrap_dir,
                         '-o', gir_d_intf_dir)
if girtod_gen.returncode() != 0
    error('Unable to build D intefaces from GIR:\n' + girtod_gen.stderr() + girtod_gen.stdout())
endif

# Enlist D GIR interface sources
dgir_glob_script = run_command(source_root + '/contrib/wrap/find-d-intf-files.py')
if dgir_glob_script.returncode() != 0
    error('Unable to find D GIR interface source code:\n' + dgir_glob_script.stdout() + dgir_glob_script.stderr())
endif
gir_binding_sources = dgir_glob_script.stdout().strip().split('\n')

gir_bind_dir = include_directories('../../wrap')

# static library of bindings automatically generated from GIR
girbind_lib = static_library('girbindings',
    [gir_binding_sources],
    dependencies: [glibd_dep],
    include_directories: [gir_bind_dir],
    pic: true
)

girbinding_dep = declare_dependency(
    link_with: [girbind_lib],
    include_directories: [gir_bind_dir]
)
