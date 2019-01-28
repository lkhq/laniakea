module pywrap;

// We only add the Python bindings if not in unittest mode
version(unittest) {}
else {

import pyd.pyd;
import pyd.embedded;
import lknative.py.pyhelper;

import lkshared.utils : SignedFile, compareVersions;
import lkshared.utils.namegen : generateName;
import lkshared.logging : setVerboseLog;
import lknative.config;

extern(C) void PydMain()
{
    /* Common */
    def!(compareVersions, PyName!"compare_versions")();
    def!(generateName, PyName!"generate_name")();
    def!(setVerboseLog, PyName!"logging_set_verbose")();
    def!(intToVersionPriority, PyName!"int_to_versionpriority")();

    module_init();

    /* Common */
    wrap_class!(SignedFile,
            Init!(string[]),

            Def!(SignedFile.open),
    )();

    wrapAggregate!(BaseConfig)();
    wrapAggregate!(BaseArchiveConfig)();
    wrapAggregate!(SuiteInfo)();

    /* Repo infrastructure */
    import lkshared.repository;
    //wrap_class!(Repository,
    //        Init!(string, string, string, string[]),

    //        Def!(Repository.getSourcePackages),
    //        Def!(Repository.getBinaryPackages),
    //        Def!(Repository.getInstallerPackages),
    //)();

    /* Synchrotron */
    import lknative.synchrotron;
    wrapAggregate!(SyncSourceSuite)();
    wrapAggregate!(SyncSourceInfo)();
    wrapAggregate!(SynchrotronConfig)();
    wrapAggregate!(SynchrotronIssue)();
    wrap_class!(SyncEngine,
            Init!(BaseConfig, SynchrotronConfig, SuiteInfo),

            Def!(SyncEngine.setSourceSuite),
            Def!(SyncEngine.setBlacklist),

            Def!(SyncEngine.autosync),
            Def!(SyncEngine.syncPackages),
    )();

    /* Spears */
    import lknative.spears;
    wrapAggregate!(SpearsHint)();
    wrapAggregate!(SpearsConfigEntry)();
    wrapAggregate!(SpearsConfig)();
    wrapAggregate!(SpearsAgePolicy)();
    wrapAggregate!(SpearsMissingBuilds)();
    wrapAggregate!(SpearsOldBinaries)();
    wrapAggregate!(SpearsReason)();

    wrapAggregate!(SpearsExcuse)();
    wrap_class!(SpearsEngine,
            Init!(BaseConfig, SpearsConfig, SuiteInfo[]),

            Def!(SpearsEngine.updateConfig),
            Def!(SpearsEngine.runMigration),
    )();
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
