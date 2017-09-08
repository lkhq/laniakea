# Lighthouse - communication relay

The Lighthouse daemon is used as a communication relay, to make individual services discover each other and to
distribute jobs.
There can be an arbitrary number of Lighthouse instances on multiple servers. Due to Lighthouse directly
distributing jobs and interacting with the central database, currently each Lighthouse server needs write access
to a Postgres database.

## TODO


---
#### About the name

A lighthouse guides ships on the sea to stay on course. The same way the Lighthouse module is a fixpoint for Laniakea
modules, and is the place they gets tasks and information from (if they don't have a direct database connection already).
