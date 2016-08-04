Laniakea
========

A new tool to manage (Debian) derivatives.

This software is currently under development. Its tasks include:
 * Synchronizing the source distribution with the target derivative
 * Centralizing information from other tools (Britney, Ben, ...) under one frontend
 * Automatically taking maintenance action on the archive (e.g. rebuilding packages)
 * Provide an interactive web frontend to perform archive management tasks
 * Propagate information between the archive repository, bugtrackers and other websites
 * Pull information about the state of packages from other distributions and check the CVE
   databases for security issues. Present all of this information (patches, bugs, issue data, ...)
   to developers in a nice way.
 * Possibly more related tasks

In order to achieve these tasks and stay maintainable, Laniakea is split into multiple parts which can act independently
(but all connect to the same database).
That way, more security-sensitive bits can also be isolated out and run on different machines.

At time, only the Synchrotron part is under development, as soon as it is working and the concept has proven to work, more modules will
be added.
Until then, this is an experimental project. Please take a look at "rapidumo", which is the predecessor of this project and currently in
active use at Tanglu if you want to have something working right now.
