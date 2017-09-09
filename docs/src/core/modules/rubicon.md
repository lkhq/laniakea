# Rubicon - import artifacts into a trusted area

Rubicon imports (build)artifacts from a less-trusted space into a trusted area. It verifies GPG signatures of the
artifacts against a trusted keyring, and if the files can be trusted, moves them to a predefined location.

It can be used for importing arbitrary files, as long as they are accompanied by a signed `.dud` ("Debian Upload Description") file.

## TODO


---
#### About the name

The [Rubicon](https://en.wikipedia.org/wiki/Rubicon) river was historically the border between the Roman province Cisalpine Gaul and Italy.
Governors of northern provinces were not allowed to cross it with their troups, doing so was a capital offense (something that a certain
Julius Caesar famously ignored). The `rubicon` tool ensures only trusted allies cross the border in Laniakea.
