/*
 * Copyright (C) 2016-2017 Matthias Klumpp <matthias@tenstral.net>
 *
 * Licensed under the GNU Lesser General Public License Version 3
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation, either version 3 of the license, or
 * (at your option) any later version.
 *
 * This software is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this software.  If not, see <http://www.gnu.org/licenses/>.
 */

module laniakea.db.schema.archive;
@safe:

import laniakea.pkgitems;

import laniakea.db.database;

private enum ArchiveTab {
    SRCPKGS    = "archive_src_packages",
    BINPKGS    = "archive_bin_packages",
    REPOS      = "archive_repos",
    SUITES     = "archive_suites",
    COMPONENTS = "archive_components",

    BIN_PKG_ASSOC = "archive_bin_package_associations",
    SRC_PKG_ASSOC = "archive_src_package_associations"
};


/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    // Source packages
    conn.exec (
        "CREATE TABLE IF NOT EXISTS " ~ ArchiveTab.SRCPKGS ~ " (
          lkid VARCHAR(32) PRIMARY KEY,
          name             TEXT NOT NULL,
          version          DEBVERSION NOT NULL,
          suite            TEXT NOT NULL,
          component        TEXT NOT NULL,
          repository       TEXT NOT NULL,

          architectures    JSONB,
          binaries         JSONB,

          standards_version TEXT NOT NULL,
          format           TEXT NOT NULL,

          homepage         TEXT,
          vcs_browser      TEXT,

          mainteiner       TEXT NOT NULL,
          uploaders        JSONB,

          build_depends    JSONB,
          files            JSONB,

          directory        TEXT NOT NULL
        )"
    );

    conn.exec ("CREATE INDEX IF NOT EXISTS archive_srcpkg_name_version_idx
                ON archive_srcpkg (name, version)");
    conn.exec ("CREATE INDEX IF NOT EXISTS archive_srcpkg_repo_suite_idx
                ON archive_srcpkg (repository, suite)");
    conn.exec ("CREATE INDEX IF NOT EXISTS archive_srcpkg_ftsearch
                ON archive_srcpkg USING GIN(to_tsvector('english', name));");

    // Binary packages
    conn.exec (
        "CREATE TABLE IF NOT EXISTS archive_binpkg (
          lkid VARCHAR(32) PRIMARY KEY,
          name             TEXT NOT NULL,
          version          DEBVERSION NOT NULL,
          suite            TEXT NOT NULL,
          component        TEXT NOT NULL,

          deb_kind         SMALLINT,
          repository       TEXT NOT NULL,

          architecture     TEXT NOT NULL,
          size_installed   INTEGER,

          description      TEXT,
          description_md5  TEXT,

          source_name      TEXT NOT NULL,
          source_version   DEBVERSION NOT NULL,

          priority         SMALLINT,
          section          TEXT NOT NULL,

          depends          JSONB,
          pre_depends      JSONB,

          maintainer       TEXT NOT NULL,

          file             JSONB,
          homepage         TEXT
        )"
    );

    conn.exec ("CREATE INDEX IF NOT EXISTS archive_binpkg_name_version_idx
                ON archive_binpkg (name, version)");
    conn.exec ("CREATE INDEX IF NOT EXISTS archive_binpkg_repo_suite_idx
                ON archive_binpkg (repository, suite)");
    conn.exec ("CREATE INDEX IF NOT EXISTS archive_binpkg_ftsearch
                ON archive_binpkg USING GIN(to_tsvector('english', name || ' ' || description));");
}

/**
 * Add/update a source package.
 */
void update (PgConnection conn, SourcePackage spkg) @trusted
{
    QueryParams p;
    p.sqlCommand = "INSERT INTO archive_srcpkg
                    VALUES ($1,
                            $2,
                            $3,
                            $4,
                            $5,
                            $6,
                            $7::jsonb,
                            $8::jsonb,
                            $9,
                            $10,
                            $11,
                            $12,
                            $13,
                            $14::jsonb,
                            $15::jsonb,
                            $16::jsonb,
                            $17
                        )
                    ON CONFLICT (lkid) DO UPDATE SET
                      name       = $2,
                      version    = $3,
                      suite      = $4,
                      component  = $5,
                      repository = $6,

                      architectures = $7::jsonb,
                      binaries      = $8::jsonb,

                      standards_version = $9,
                      format            = $10,

                      homepage          = $11,
                      vcs_browser       = $12,

                      mainteiner        = $13,
                      uploaders         = $14::jsonb,

                      build_depends     = $15::jsonb,
                      files             = $16::jsonb,

                      directory         = $17";

    p.setParams (spkg.lkid,
                 spkg.name,
                 spkg.ver,
                 spkg.suite,
                 spkg.component,
                 spkg.repository,
                 spkg.architectures,
                 spkg.binaries,
                 spkg.standardsVersion,
                 spkg.format,
                 spkg.homepage,
                 spkg.vcsBrowser,
                 spkg.maintainer,
                 spkg.uploaders,
                 spkg.buildDepends,
                 spkg.files,
                 spkg.directory
    );

    conn.execParams (p);
}


/**
 * Add/update a binary package.
 */
void update (PgConnection conn, BinaryPackage bpkg) @trusted
{
    QueryParams p;
    p.sqlCommand = "INSERT INTO archive_binpkg
                    VALUES ($1,
                            $2,
                            $3,
                            $4,
                            $5,
                            $6,
                            $7,
                            $8,
                            $9,
                            $10,
                            $11,
                            $12,
                            $13,
                            $14,
                            $15,
                            $16::jsonb,
                            $17::jsonb,
                            $18,
                            $19::jsonb,
                            $20
                        )
                    ON CONFLICT (lkid) DO UPDATE SET
                      name      = $2,
                      version   = $3,
                      suite     = $4,
                      component = $5,

                      deb_kind   = $6,
                      repository = $7,

                      architecture   = $8,
                      size_installed = $9,

                      description     = $10,
                      description_md5 = $11,

                      source_name    = $12,
                      source_version = $13,

                      priority       = $14,
                      section        = $15,

                      depends        = $16::jsonb,
                      pre_depends    = $17::jsonb,

                      maintainer     = $18,

                      file           = $19::jsonb,
                      homepage       = $20";

    p.setParams (bpkg.lkid,
                 bpkg.name,
                 bpkg.ver,
                 bpkg.suite,
                 bpkg.component,
                 bpkg.debType,
                 bpkg.repository,
                 bpkg.architecture,
                 bpkg.installedSize,
                 bpkg.description,
                 bpkg.descriptionMd5,
                 bpkg.sourceName,
                 bpkg.sourceVersion,
                 bpkg.priority,
                 bpkg.section,
                 bpkg.depends,
                 bpkg.preDepends,
                 bpkg.maintainer,
                 bpkg.file,
                 bpkg.homepage
    );

    conn.execParams (p);
}

void removeSuiteContents (PgConnection conn, string repoName, string suiteName) @trusted
{
    QueryParams p;

    p.sqlCommand = "DELETE FROM archive_binpkg WHERE repository=$1 AND suite=$2";
    p.setParams (repoName, suiteName);
    conn.execParams (p);

    p.sqlCommand = "DELETE FROM archive_srcpkg WHERE repository=$1 AND suite=$2";
    p.setParams (repoName, suiteName);
    conn.execParams (p);
}

auto findBinaryPackage (PgConnection conn, string repoName, string term) @trusted
{
    import std.array : replace, split, join;
    import std.algorithm : map;

    QueryParams p;

    immutable termPrepared = term.replace ("|", " ").replace ("&", " ").split.join ("|");
    p.sqlCommand = "SELECT * FROM archive_binpkg WHERE
                    repository=$1 AND to_tsvector(name || '. ' || description) @@ to_tsquery($2);";
    p.setParams (repoName, termPrepared);

    auto ans = conn.execParams(p);
    return rowsTo!BinaryPackage (ans);
}

/**
 * Get the package with the highest version number matching the given parameters.
 */
auto getPackageFor (T) (PgConnection conn, string repoName, string suiteName, string component, string name) @trusted
{
    static assert (is(T == SourcePackage) || is(T == BinaryPackage));

    QueryParams p;

    static if (is(T == SourcePackage))
        p.sqlCommand = "SELECT * FROM archive_srcpkg WHERE
                        repository=$1 AND suite=$2 AND component=$3 AND name=$4
                        ORDER BY version LIMIT 1;";
    else
        p.sqlCommand = "SELECT * FROM archive_binpkg WHERE
                        repository=$1 AND suite=$2 AND component=$3 AND name=$4
                        ORDER BY version LIMIT 1;";

    p.setParams (repoName, suiteName, component, name);

    auto ans = conn.execParams(p);
    return rowsToOne!T (ans);
}

auto getPackageVersions (T) (PgConnection conn, string repoName, string suiteName, string component, string name) @trusted
{
    static assert (is(T == SourcePackage) || is(T == BinaryPackage));

    QueryParams p;
    static if (is(T == SourcePackage))
        p.sqlCommand = "SELECT version FROM archive_srcpkg WHERE
                        repository=$1 AND suite=$2 AND component=$3 AND name=$4
                        ORDER BY version;";
    else
        p.sqlCommand = "SELECT version FROM archive_binpkg WHERE
                        repository=$1 AND suite=$2 AND component=$3 AND name=$4
                        ORDER BY version;";

    p.setParams (repoName, suiteName, component, name);

    auto ans = conn.execParams(p);
    return rowsToStringList (ans);
}

auto getPackageSuites (T) (PgConnection conn, string repoName, string component, string name) @trusted
{
    static assert (is(T == SourcePackage) || is(T == BinaryPackage));

    import std.algorithm : uniq;
    QueryParams p;

    static if (is(T == SourcePackage))
        p.sqlCommand = "SELECT suite FROM archive_srcpkg WHERE
                        repository=$1 AND component=$2 AND name=$3
                        ORDER BY suite;";
    else
        p.sqlCommand = "SELECT suite FROM archive_binpkg WHERE
                        repository=$1 AND component=$2 AND name=$3
                        ORDER BY suite;";

    p.setParams (repoName, component, name);

    auto ans = conn.execParams(p);
    return rowsToStringList (ans).uniq;
}
