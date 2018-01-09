/*
 * Copyright (C) 2017 Matthias Klumpp <matthias@tenstral.net>
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

module laniakea.debcheck;

import std.string : format;
import std.array : appender, empty, array;
import std.algorithm : startsWith, map;
import std.conv : to;
import std.path : buildPath;
import std.typecons : Tuple;
static import dyaml;

import laniakea.db;
import laniakea.utils : currentDateTime;
import laniakea.localconfig;
import laniakea.pkgitems;
import laniakea.repository;
import laniakea.logging;

class Debcheck
{

    private {
        struct DoseResult
        {
            bool success;
            string data;
        }

        Database db;
        SessionFactory sFactory;
        Repository repo;
    }

    this ()
    {
        db = Database.get;
        sFactory = db.newSessionFactory! (DebcheckIssue);

        const conf = LocalConfig.get;
        const baseConfig = db.getBaseConfig;
        repo = new Repository (conf.archive.rootPath,
                                baseConfig.projectName);
        repo.setTrusted (true);
    }

    private string getDefaultNativeArch (ArchiveSuite suite)
    {
        // determine a default native architecture in case
        // we are processing arch:all
        auto defaultNativeArch = "amd64";
        auto nativeArchFound = false;
        foreach (ref a; suite.architectures) {
            if (a.name == defaultNativeArch) {
                nativeArchFound = true;
                break;
            }
        }

        if (!nativeArchFound)
            defaultNativeArch = suite.architectures[0].name;

        if (defaultNativeArch.empty)
            throw new Exception ("Unable to determine a valid default architecture.");
        return defaultNativeArch;
    }

    private DoseResult executeDose (const string dose_exe, const string[] args, const string[] files) @trusted
    {
        import std.process;
        import std.stdio;

        string getOutput (File f)
        {
            char[1024] buf;
            auto output = appender!string;
            while (!f.eof) {
                auto res = f.rawRead (buf);
                output ~= res;
            }
            return output.data;
        }

        auto doseArgs = [dose_exe] ~ args ~ files;
        auto cmd = pipeProcess (doseArgs);

        // wait for the command to exit, a non-null exit code indicates errors in
        // the dependencies of the analyzed packages.
        // Read stdout continuously
        auto doseStdout = appender!string;
        while (!tryWait (cmd.pid).terminated) {
            char[1024] buf;
            while (!cmd.stdout.eof) {
                auto res = cmd.stdout.rawRead (buf);
                doseStdout ~= res;
            }
        }

        immutable yamlData = doseStdout.data;
        if (!yamlData.startsWith ("output-version")) {
            // the output is weird, assume an error
            return DoseResult (false, yamlData ~ "\n" ~ getOutput (cmd.stderr));
        }

        return DoseResult (true, yamlData);
    }

    /**
     * Get a list of index files for the specific suite and architecture,
     * for all components, as well as all the suites it depends on.
     *
     * The actual indices belonging to the suite are added as "foreground" (fg), the
     * ones of the dependencies are added as "background" (bg).
     */
    private Tuple!(string[], "fg", string[], "bg")
    getFullIndexFileList (Session session, ArchiveSuite suite, string arch, bool sourcePackages, string binArch)
    {
        Tuple!(string[], "fg", string[], "bg") res;

        foreach (ref component; suite.components) {
            string fname;
            if (sourcePackages) {
                fname = repo.getIndexFile (suite.name, buildPath (component.name, "source", "Sources.xz"));
                if (!fname.empty)
                    res.fg ~= fname;

                fname = repo.getIndexFile (suite.name, buildPath (component.name, "binary-%s".format (arch), "Packages.xz"));
                if (!fname.empty)
                    res.bg ~= fname;
            } else {
                fname = repo.getIndexFile (suite.name, buildPath (component.name, "binary-%s".format (arch), "Packages.xz"));
                if (!fname.empty)
                    res.fg ~= fname;
            }

            if (arch == "all")
                res.bg ~= repo.getIndexFile (suite.name, buildPath (component.name, "binary-%s".format (binArch), "Packages.xz"));
        }

        // add base suite packages
        if (!suite.baseSuiteName.empty) {
            auto baseSuite = session.getSuite (suite.baseSuiteName);
            if (baseSuite !is null) {
                foreach (ref component; baseSuite.components) {
                    string fname;

                    fname = repo.getIndexFile (baseSuite.name, buildPath (component.name, "binary-%s".format (arch), "Packages.xz"));
                    if (!fname.empty)
                        res.bg ~= fname;

                    if (arch == "all")
                        res.bg ~= repo.getIndexFile (baseSuite.name, buildPath (component.name, "binary-%s".format (binArch), "Packages.xz"));
                }
            }
        }

        return res;
    }

    /**
     * Get Dose YAML data for build dependency issues in the selected suite.
     */
    private string[string] getBuildDepCheckYaml (Session session, ArchiveSuite suite)
    {
        string[string] archIssueMap;

        immutable defaultNativeArch = getDefaultNativeArch (suite);
        foreach (ref arch; suite.architectures.map! (a => a.name)) {
            // fetch source-package-centric index list
            auto indices = getFullIndexFileList (session, suite, arch, true, defaultNativeArch);
            if (indices.fg.empty) {
                if (arch == "all")
                    continue;
                throw new Exception ("Unable to get any indices for %s/%s to check for dependency issues.".format (suite.name, arch));
            }

            auto doseArgs = ["--quiet",
                             "--latest=1",
                             "-e",
                             "-f",
                             "--summary",
                             "--deb-emulate-sbuild",
                             "--deb-native-arch=%s".format ((arch == "all")? defaultNativeArch : arch)];

            // run builddepcheck
            auto doseResult = executeDose ("dose-builddebcheck", doseArgs, indices.bg ~ indices.fg);
            if (!doseResult.success)
                throw new Exception ("Unable to run Dose for %s/%s: %s".format (suite.name, arch, doseResult.data));
            archIssueMap[arch] = doseResult.data;
        }

        return archIssueMap;
    }

    /**
     * Get Dose YAML data for build installability issues in the selected suite.
     */
    private string[string] getDepCheckYaml (Session session, ArchiveSuite suite)
    {
        import std.algorithm : map;
        import std.array : array;
        string[string] archIssueMap;

        immutable defaultNativeArch = getDefaultNativeArch (suite);

        auto allArchs = array (suite.architectures.map!(a => a.name)) ~ ["all"];
        foreach (ref arch; allArchs) {
            // fetch binary-package index list
            auto indices = getFullIndexFileList (session, suite, arch, false, defaultNativeArch);
            if (indices.fg.empty) {
                if (arch == "all")
                    continue;
                throw new Exception ("Unable to get any indices for %s/%s to check for dependency issues.".format (suite.name, arch));
            }

            auto doseArgs = ["--quiet",
                             "--latest=1",
                             "-e",
                             "-f",
                             "--summary",
                             "--deb-native-arch=%s".format ((arch == "all")? defaultNativeArch : arch)];

            // run builddepcheck
            auto doseResult = executeDose ("dose-debcheck",
                                doseArgs,
                                indices.bg.map! (f => ("--bg=" ~ f)).array ~
                                indices.fg.map! (f => ("--fg=" ~ f)).array);
            if (!doseResult.success)
                throw new Exception ("Unable to run Dose for %s/%s: %s".format (suite.name, arch, doseResult.data));
            archIssueMap[arch] = doseResult.data;
        }

        return archIssueMap;
    }

    private DebcheckIssue[] doseYamlToDatabaseEntries (string yamlData, string suiteName, string arch) @trusted
    {
        import std.uuid : randomUUID;
        auto res = appender!(DebcheckIssue[]);

        void setBasicPackageInfo (T) (ref T v, dyaml.Node entry) {
            if (entry.containsKey ("type") && entry["type"].as!string == "src")
                v.packageKind = PackageType.SOURCE;
            else
                v.packageKind = PackageType.BINARY;

            v.packageName = entry["package"].as!string;
            v.packageVersion = entry["version"].as!string;
            v.architecture = entry["architecture"].as!string;
        }

        auto yroot = dyaml.Loader.fromString (yamlData.to!(char[])).load ();
        auto report = yroot["report"];
        auto archAll = arch == "all";

        foreach (ref dyaml.Node entry; report) {
            auto issue = new DebcheckIssue;

            if (!archAll) {
                // we ignore entries from "all" unless we are explicitly reading information
                // for that fake architecture.
                if (entry["architecture"].as!string == "all")
                    continue;
            }

            issue.uuid = randomUUID ();
            issue.date = currentDateTime ();
            issue.suiteName = suiteName;

            setBasicPackageInfo!DebcheckIssue (issue, entry);

            auto reasons = entry["reasons"];
            foreach (ref dyaml.Node reason; reasons) {
                if (reason.containsKey ("missing")) {
                    // we have a missing package issue
                    auto ymissing = reason["missing"]["pkg"];
                    PackageIssue pkgissue;
                    setBasicPackageInfo!PackageIssue(pkgissue, ymissing);
                    pkgissue.unsatDependency = ymissing["unsat-dependency"].as!string;

                    issue.missing ~= pkgissue;
                } else if (reason.containsKey ("conflict")) {
                    // we have a conflict in the dependency chain
                    auto yconflict = reason["conflict"];
                    PackageConflict conflict;

                    setBasicPackageInfo!PackageIssue(conflict.pkg1, yconflict["pkg1"]);
                    if (yconflict["pkg1"].containsKey ("unsat-conflict"))
                        conflict.pkg1.unsatConflict = yconflict["pkg1"]["unsat-conflict"].as!string;

                    setBasicPackageInfo!PackageIssue(conflict.pkg2, yconflict["pkg2"]);
                    if (yconflict["pkg2"].containsKey ("unsat-conflict"))
                        conflict.pkg2.unsatConflict = yconflict["pkg2"]["unsat-conflict"].as!string;

                    // parse the depchain
                    if (yconflict.containsKey ("depchain1")) {
                        foreach (ref dyaml.Node ypkg; yconflict["depchain1"][0]["depchain"]) {
                            PackageIssue pkgissue;
                            setBasicPackageInfo!PackageIssue(pkgissue, ypkg);
                            pkgissue.depends = ypkg["depends"].as!string;
                            conflict.depchain1 ~= pkgissue;
                        }
                    }
                    if (yconflict.containsKey ("depchain2")) {
                        foreach (ref dyaml.Node ypkg; yconflict["depchain2"][0]["depchain"]) {
                            PackageIssue pkgissue;
                            setBasicPackageInfo!PackageIssue(pkgissue, ypkg);
                            pkgissue.depends = ypkg["depends"].as!string;
                            conflict.depchain2 ~= pkgissue;
                        }
                    }

                    issue.conflicts ~= conflict;
                } else {
                    throw new Exception ("Found unknown dependency issue: " ~ reason.to!string);
                }
            }

            res ~= issue;
        }

        return res.data;
    }

    public bool updateBuildDepCheckIssues (Session session, ArchiveSuite suite) @trusted
    {
        import std.typecons : tuple;

        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        auto issuesYaml = getBuildDepCheckYaml (session, suite);
        conn.removeDebcheckIssues (suite.name, PackageType.SOURCE);
        foreach (ref arch, ref yamlData; issuesYaml) {
            auto entries = doseYamlToDatabaseEntries (yamlData, suite.name, arch);

            foreach (ref entry; entries)
                session.save (entry);
        }

        return true;
    }

    public bool updateBuildDepCheckIssues (string suiteName)
    {
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        return updateBuildDepCheckIssues (session, session.getSuite (suiteName));
    }

    public bool updateBuildDepCheckIssues ()
    {
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        foreach (ref suite; session.getSuites ()) {
            immutable ret = updateBuildDepCheckIssues (session, suite);
            if (!ret)
                return false;
        }
        return true;
    }

    public bool updateDepCheckIssues (Session session, ArchiveSuite suite) @trusted
    {
        import std.typecons : tuple;

        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        auto issuesYaml = getDepCheckYaml (session, suite);
        foreach (ref arch, ref yamlData; issuesYaml) {
            auto entries = doseYamlToDatabaseEntries (yamlData, suite.name, arch);

            conn.removeDebcheckIssues (suite.name, PackageType.BINARY, arch);
            foreach (ref entry; entries)
                session.save (entry);
        }

        return true;
    }

    public bool updateDepCheckIssues (string suiteName)
    {
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        return updateDepCheckIssues (session, session.getSuite (suiteName));
    }

    public bool updateDepCheckIssues ()
    {
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        foreach (ref suite; session.getSuites ()) {
            auto ret = updateDepCheckIssues (session, suite);
            if (!ret)
                return false;
        }
        return true;
    }

    public auto getBinaryIssuesList (ArchiveSuite suite, string arch) @trusted
    {
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        auto q = session.createQuery ("FROM DebcheckIssue issue WHERE issue.suiteName=:suite
                                                                  AND issue.architecture=:arch
                                                                  AND issue.packageKind=:kind")
                                      .setParameter ("suite", suite.name)
                                      .setParameter ("arch", arch)
                                      .setParameter ("kind", PackageType.BINARY.to!short);
        return q.list!DebcheckIssue();
    }

    public auto getSourceIssuesList (ArchiveSuite suite, string arch) @trusted
    {
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        auto q = session.createQuery ("FROM DebcheckIssue issue WHERE issue.suiteName=:suite
                                                                  AND issue.architecture=:arch
                                                                  AND issue.packageKind=:kind")
                                      .setParameter ("suite", suite.name)
                                      .setParameter ("arch", arch)
                                      .setParameter ("kind", PackageType.SOURCE.to!short);
        return q.list!DebcheckIssue();
    }
}
