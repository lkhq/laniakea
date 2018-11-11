module pywrap;

import pyd.pyd, pyd.embedded;
import lknative.py.pyhelper;

import lknative.utils : SignedFile, compareVersions;
import lknative.utils.namegen : generateName;
import lknative.config;

extern(C) void PydMain()
{
    def!(compareVersions, PyName!"compare_versions")();
    def!(generateName, PyName!"generate_name")();

    module_init();

    wrap_class!(SignedFile,
            Init!(string[]),

            Def!(SignedFile.open),
    )();

    wrapAggregate!(BaseConfig)();
    wrapAggregate!(SuiteInfo)();
}


import deimos.python.object: PyObject;
extern(C) export PyObject* PyInit_lknative() {
    import pyd.thread : ensureAttached;
    return pyd.exception.exception_catcher(delegate PyObject*() {
        ensureAttached();
        pyd.def.pyd_module_name = "lknative";
        PydMain();
        return pyd.def.pyd_modules[""];
    });
}

extern(C) void _Dmain(){
    // make druntime happy
}
