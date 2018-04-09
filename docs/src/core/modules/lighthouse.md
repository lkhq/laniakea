# Lighthouse - communication relay

Laniakea modules are almost always their own executables or even services. This allows to run them on separate
machines, to improve security by isolation or to balance load.

The *Lighthouse* core module is a daemon that provides a way for Laniakea modules to get notified about changes,
distribute jobs to them and receive information to store in the database.

There can be an arbitrary number of Lighthouse instances on multiple servers. Due to Lighthouse directly
distributing jobs and interacting with the central database, currently each Lighthouse server needs write access
to a Postgres database.

## TODO


---
#### About the name

A lighthouse guides ships on the sea to stay on course. The same way the Lighthouse module is a fixpoint for Laniakea
modules, and is the place they gets tasks and information from (if they don't have a direct database connection already).
