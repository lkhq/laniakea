# Laniakea Porting Progress

All Laniakea modules are current being either ported to pure Python 3, or to hybrid Python+D modules where that route makes sense.
In order to use SQLAlchemy through all parts of Laniakea, all D code parts that directly interact with the database need to be rewritten to
be wrapped by Python code instead.
Additionally, all modules that interact with the ZeroMQ-based communication hub need to be adapted as well.
Since these changes touch every single module of Laniakea, the porting is also used to correct a few design mistakes that could not be
fixed before without disruptive changes.
There will be no direct migration from the pure-D Laniakea version to the new version, running the two versions in parallel will be
impossible.


## Why?

D is an awesome language for writing quick algorithms, for string processing and for writing fast code with less effort than doing the same in C or C++.
However, when it comes to database connectivity, the existing 3rd-party projects have serious issues. In the past, I have run into bugs related to these modules so often,
that I spent more time addressing issues related to database connectivity than actually working on Laniakea itself. Additionally, writing web applications
in pure-D is still less fun than doing the same in Python.
All of these issues could be fixed, but Laniakea is not a project to fix issues in 3rd-party D modules and those were at some point just slowing progress down too much.
Python is a much better choice, so going the hybrid rout of Python+D is the way forward.
Since much cleverness and testing exists for the existing D code, as much of it as possible will be reused.


## Status

Module | Purpose | Depends on | Status
------------ | ------------ | ------------ | -------------
Core facilities | Generic helper library and tools | - | :heavy_check_mark: Completed
Spark | Generic task processing daemon | ZMQ communication protocol | :heavy_check_mark: Completed
Synchrotron | Synchronize packages from different suites | Core | :heavy_check_mark: Completed
Admin CLI | CLI tool for configuring modules | Core | :large_orange_diamond: In progress / Blocked
Dataimport | Import archive (meta)data into the database | Core | :heavy_check_mark: Completed
Daktape | Glue code to communicate with dak | - | :large_orange_diamond: In progress
Debcheck | Check package dependency graph for issues | Core, Dataimport | :heavy_check_mark: Completed
ZMQ communication protocol | Protocol modules use to communicate, needs a few design changes (e.g. messages must be versioned now) | Core | :heavy_check_mark: Completed
Lighthouse | ZeroMQ communication hub | Core, Dataimport, Debcheck, Communication Protocol | :soon: In progress
Keytool | Manage cryptographic keys and signatures | Core, Lighthouse | :heavy_check_mark: Completed
Planter | Generate metapackage information from seeds | Core | :red_circle: Not started
Rubicon | Accept build artifacts into a trusted area | Core, Lighthouse | :red_circle: Not started
Spears | Migrate packages between suites with Britney | Core | :heavy_check_mark: Completed
Ariadne | Package build scheduler | Dataimport, Debcheck, Lighthouse | :soon: In progress
Web | Web UI | All backend modules | :red_circle: Not started
Web-SWView | Web package and application browser | Dataimport, AppStream | :red_circle: Not started
Irk | IRC bot | Lighthouse | :broken_heart: Will not be ported and has been removed
Mirk | Matrix bot | Lighthouse | :red_circle: Not started
PhabBridge | Bridge to Phabricator | Lighthouse | :red_circle: Not started


:bangbang: The module ports have different complexities. The core port was the most difficult, the Lighthouse and Dataimport ports will also be time-intensive, while the other
modules will be much easier. Since all modules share quite a lot of code and design ideas, each subsequent module port will be easier than the
one before it.
The web UIs and chat / phabricator bridges will be the last items to be ported, as they depend on the other modules to be mostly done.
