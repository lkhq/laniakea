module wrap_all;

import autowrap.python;

mixin(
    wrapAll(
        LibraryName("lknative"),
        Modules(
            Module("localconfig", Yes.alwaysExport),
            "utils.namegen",
            "utils.versioncmp",
           // "utils.utils",
            "utils.gpg"
        ),
    )
);
