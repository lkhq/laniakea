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

module datasync.repodbsync;
@safe:

import laniakea.logging;
import laniakea.localconfig;
import laniakea.repository;
import laniakea.db;
import laniakea.db.schema.archive;

bool syncRepoData (string suiteName, string repoName = "master") @trusted
{
    import core.sys.posix.unistd : fork, pid_t;
    import core.sys.posix.sys.wait;
    import core.stdc.stdlib : exit;
    import std.exception : errnoEnforce;

    auto db = Database.get;

    auto sFactory = db.newSessionFactory ();
    scope (exit) sFactory.close ();
    auto session = sFactory.openSession ();
    scope (exit) session.close ();

    auto suite = session.getSuite (suiteName);
    if (suite is null) {
        logError ("Unable to find suite: %s", suiteName);
        return false;
    }

    Repository repo;
    if (repoName == "master") {
        repo = new Repository (LocalConfig.get.archive.rootPath, repoName);
        repo.setTrusted (true);
    } else {
        assert (0, "The multiple repositories feature is not yet implemented.");
    }

    // FIXME: Hibernated doesn't work well in multithreaded environments, therefore we fork here
    // to have some temporary parallelization. Ultimately, Hibernated needs to be fixed though.

    bool ret = true;
    foreach (ref component; suite.components) {
        // Source packages
        repo.getSourcePackages (suite.name, component.name, session, true);

        pid_t[] processes;
        foreach (ref arch; suite.architectures) {
            pid_t pid = fork ();
            errnoEnforce (pid >= 0, "Fork failed");

            if (pid == 0) {
                // child process
                logDebug ("Child process forked.");

                auto childDb = Database.get;
                auto childSFactory = childDb.newSessionFactory ();
                scope (exit) childSFactory.close ();
                auto childSession = childSFactory.openSession ();
                scope (exit) childSession.close ();

                // binary packages
                repo.getBinaryPackages (suite.name, component.name, arch.name, childSession, true);

                // binary packages of the debian-installer
                repo.getInstallerPackages (suite.name, component.name, arch.name, childSession, true);

                exit (0);
            }

            processes ~= pid;
        }

        foreach (pid; processes) {
            int status = 0;
            do {
                errnoEnforce (waitpid (pid, &status, 0) != -1, "Waitpid failed");
            } while (!WIFEXITED (status));

            if (WEXITSTATUS (status) != 0)
                ret = false;
        }

        if (!ret)
            break;
    }

    return ret;
}
