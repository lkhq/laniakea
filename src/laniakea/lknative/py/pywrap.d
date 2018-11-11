module pywrap;

// We only add the Python bindings if not in unittest mode
version(unittest) {}
else {

import pyd.pyd;
import pyd.embedded;
import lknative.py.pyhelper;

import lkshared.utils : SignedFile, compareVersions;
import lkshared.utils.namegen : generateName;
import lknative.config;

extern(C) void PydMain()
{
    /* Common */
    def!(compareVersions, PyName!"compare_versions")();
    def!(generateName, PyName!"generate_name")();

    module_init();

    /* Common */
    wrap_class!(SignedFile,
            Init!(string[]),

            Def!(SignedFile.open),
    )();

    wrapAggregate!(BaseConfig)();
    wrapAggregate!(SuiteInfo)();

    /* Synchrotron */
    import lknative.synchrotron;
    wrap_class!(SyncEngine,
            Init!(BaseConfig, SynchrotronConfig),

            Def!(SyncEngine.setSourceSuite),
            Def!(SyncEngine.setBlacklist),

            Def!(SyncEngine.autosync),
            Def!(SyncEngine.syncPackages),
    )();

    wrapAggregate!(SynchrotronConfig)();
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

} // End of unittest conditional
