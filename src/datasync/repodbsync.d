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

bool syncRepoData (string suiteName, string archiveName = "master") @trusted
{
    auto db = MongoLegacyDatabase.get;

    auto suite = db.getSuite (suiteName);
    if (suite.isNull) {
        logError ("Unable to find suite: %s", suiteName);
        return false;
    }

    Repository repo;
    if (archiveName == "master") {
        repo = new Repository (LocalConfig.get.archive.rootPath,
                                     db.getBaseConfig.projectName);
        repo.setTrusted (true);
    } else {
        assert (0, "The multiple repositories feature is not yet implemented.");
    }

    // the collection containing package data for this repository
    auto pkgColl = db.collRepoPackages (archiveName);

    // quick & dirty replacement of existing data in this collection: remove the old stuff and add the new stuff
    pkgColl.remove (["suite": suite.name]);

    foreach (ref component; suite.components) {
        // Source packages
        foreach (ref pkg; repo.getSourcePackages (suite.name, component.name)) {
            pkg.id = newBsonId ();
            pkgColl.insert (pkg);
        }

        foreach (ref arch; suite.architectures) {
            // binary packages
            foreach (ref pkg; repo.getBinaryPackages (suite.name, component.name, arch)) {
                pkg.id = newBsonId ();
                pkgColl.insert (pkg);
            }

            // binary packages of the debian-installer
            foreach (ref pkg; repo.getInstallerPackages (suite.name, component.name, arch)) {
                pkg.id = newBsonId ();
                pkgColl.insert (pkg);
            }
        }
    }

    db.fsync;

    return true;
}
