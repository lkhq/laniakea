/*
 * Copyright (C) 2016 Matthias Klumpp <matthias@tenstral.net>
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

import laniakea.repository.dak;

/**
 * Execute package synchronization in Synchrotron
 */
class SyncEngine
{

private:

    Dak dak;
    bool m_importsTrusted;

public:

    this ()
    {
        dak = new Dak ();
    }

    @property
    bool importsTrusted ()
    {
        return m_importsTrusted;
    }

    @property
    void importsTrusted (bool v)
    {
        m_importsTrusted = v;
    }

    bool importPackageFiles (const string suite, const string component, const string[] fnames)
    {
        return dak.importPackageFiles (suite, component, fnames, importsTrusted, true);
    }

    bool importPackages (const string suite, const string component, const string[] pkgnames)
    {
        // TODO: Analyze the input, fetch the packages from the source distribution and
        // import them into the target in their correct order.
        // Then apply the correct, synced override from the source distro.

        return false;
    }

}
