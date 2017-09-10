
module laniakea.db.schema;

public import laniakea.db.schema.core;
public import laniakea.db.schema.jobs;
public import laniakea.db.schema.synchrotron;
public import laniakea.db.schema.eggshell;
public import laniakea.db.schema.spears;
public import laniakea.db.schema.debcheck;
public import laniakea.db.schema.workers;
public import laniakea.db.schema.isotope;

/// Used internally to automatically call member functions of schema modules
private import std.typecons : tuple;
static immutable __laniakea_db_schema_names = tuple(
    "core",
    "jobs",
    "synchrotron",
    "eggshell",
    "spears",
    "debcheck",
    "workers",
    "isotope"
);
