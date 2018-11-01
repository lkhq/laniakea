module synchrotron.pywrap;

import autowrap.python;

mixin(
    wrapAll(
        LibraryName("laniakea_synchrotron"),
        Modules(
            Module("syncengine", Yes.alwaysExport)
        ),
    )
);
