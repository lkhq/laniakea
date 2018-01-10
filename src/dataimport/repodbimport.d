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

    foreach (ref component; suite.components) {
        // Source packages
        foreach (ref pkg; repo.getSourcePackages (suite.name, component.name, session)) {
            session.save (pkg);
        }

        foreach (ref arch; suite.architectures) {
            // binary packages
            foreach (ref pkg; repo.getBinaryPackages (suite.name, component.name, arch.name, session)) {
                session.save (pkg);
            }

            // binary packages of the debian-installer
            foreach (ref pkg; repo.getInstallerPackages (suite.name, component.name, arch.name, session)) {
                session.save (pkg);
            }
        }
    }

    return true;
}
