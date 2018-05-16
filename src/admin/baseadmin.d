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

module admin.baseadmin;

import std.stdio : writeln;
import std.string : format;

import laniakea.db;
import admin.admintool;


/**
 * Perform various basic administrative actions.
 */
final class BaseAdmin : AdminTool
{
    @property
    override SubcommandInfo toolInfo ()
    {
        return SubcommandInfo ("base", "Modify fundamental and shared settings.");
    }

    override
    int run (string[] args)
    {

        immutable command = args[0];

        bool ret = true;
        switch (command) {
            case "init":
                ret = initDb ();
                break;
            case "dump":
                baseDumpConfig ();
                break;
            case "add-suite":
                addNewSuite ();
                break;
            default:
                writeln ("The command '%s' is unknown.".format (command));
                return 1;
        }

        if (!ret)
            return 2;
        return 0;
    }

    override
    void printHelp (string progname)
    {
        auto cmds = [SubcommandInfo ("init", "Run initial setup guide."),
                     SubcommandInfo ("dump", "Print database information."),];

        printHelpText (progname,
                       toolInfo.summary,
                       "Modify core settings of Laniakea",
                       cmds, [], toolInfo.name);
    }

    override
    bool initDb ()
    {
        writeHeader ("Configuring base settings for Laniakea");

        BaseConfig bconf;
        auto factory = db.newSessionFactory ();
        auto session = factory.openSession();
        scope (exit) session.close();

        writeQS ("Name of this project");
        bconf.projectName = readString ();

        // we only support one repository at time, so add the default
        auto repo = session.createQuery ("FROM ArchiveRepository WHERE name=:rname")
                            .setParameter ("rname", "master")
                            .uniqueResult!ArchiveRepository;
        if (repo is null) {
            repo = new ArchiveRepository;
            repo.name = "master";
            session.save (repo);
        }

        bool addSuite = true;
        while (addSuite) {
            addNewSuite (repo);

            writeQB ("Add another suite?");
            addSuite = readBool ();
        }

        writeQS ("Name of the 'incoming' suite which new packages are usually uploaded to");
        bconf.archive.incomingSuite = readString ();

        writeQS ("Name of the 'development' suite which is rolling or will become a final release");
        bconf.archive.develSuite = readString ();

        writeQS ("Distribution version tag (commonly found in package versions, e.g. 'tanglu' for OS 'Tanglu' with versions like '1.0-0tanglu1'");
        bconf.archive.distroTag = readString ();

        // update database with new configuration
        db.update (bconf);

        return true;
    }

    /**
     * Interactively register a new suite.
     */
    void addNewSuite (ArchiveRepository repo = null)
    {
        import std.algorithm : canFind;
        import std.string : strip;
        import std.array : empty;

        auto factory = db.newSessionFactory ();
        auto session = factory.openSession();
        scope (exit) session.close();

        if (repo is null) {
            repo = session.createQuery ("FROM ArchiveRepository WHERE name=:rname")
                            .setParameter ("rname", "master")
                            .uniqueResult!ArchiveRepository;
            if (repo is null) {
                repo = new ArchiveRepository;
                repo.name = "master";
                session.save (repo);
            }
        }

        writeQS ("Adding a new suite. Please set a name");
        auto suiteName = readString ();

        auto suite = session.createQuery ("FROM ArchiveSuite WHERE name=:sname")
                            .setParameter ("sname", suiteName)
                            .uniqueResult!ArchiveSuite;
        if (suite !is null)
            session.remove (suite);
        suite = new ArchiveSuite;
        suite.repo = repo;
        suite.name = suiteName;

        writeQS ("List of components for suite '%s'".format (suite.name));
        auto componentsList = readList ();
        auto addMainDep = false;
        addMainDep = componentsList.canFind ("main");
        foreach (ref cname; componentsList) {
            auto c = session.createQuery ("FROM ArchiveComponent WHERE name=:cname")
                            .setParameter ("cname", cname)
                            .uniqueResult!ArchiveComponent;
            if (c is null) {
                c = new ArchiveComponent;
                c.name = cname;
                session.save (c);
            }

            if (addMainDep && c.name != "main")
                c.dependencies ~= "main";
            suite.components ~= c;
        }

        writeQS ("List of architectures for suite '%s'".format (suite.name));
        // every suite has the "all" architecture, so add it straight away
        auto selectedArchs = ["all"] ~ readList ();
        foreach (archName; selectedArchs) {
            auto arch = session.createQuery ("FROM ArchiveArchitecture WHERE name=:aname")
                                .setParameter ("aname", archName)
                                .uniqueResult!ArchiveArchitecture;
            if (arch is null) {
                arch = new ArchiveArchitecture;
                arch.name = archName;
                session.save (arch);
            }

            suite.architectures ~= arch;
        }

        writeQS ("Set a name of the suite this suite is an overlay to. Leave empty for primary suite.");
        auto baseSuiteName = readString (true);
        if (!baseSuiteName.strip.empty)
            suite.baseSuiteName = baseSuiteName;

        session.save (suite);
    }

    void baseDumpConfig ()
    {
        writeln (db.getBaseConfig ().serializeToPrettyJson);
    }
}
