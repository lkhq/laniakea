module synchrotron.pywrap;

import pyd.pyd, pyd.embedded;
import lknative.py.pyhelper;
import lknative.config : BaseConfig;
import synchrotron.syncengine : SyncEngine;
import synchrotron.syncconfig : SynchrotronConfig;

extern(C) void PydMain()
{
    module_init();

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
extern(C) export PyObject* PyInit_lknative_synchrotron () {
    import pyd.thread : ensureAttached;
    return pyd.exception.exception_catcher(delegate PyObject*() {
        ensureAttached();
        pyd.def.pyd_module_name = "lknative_synchrotron";
        PydMain();
        return pyd.def.pyd_modules[""];
    });
}

extern(C) void _Dmain(){
    // make druntime happy
}
