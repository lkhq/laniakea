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

module lknative.repository.dscfile;

import std.string : strip, split;

import lknative.logging;
import lknative.tagfile;
import lknative.repository.types;

/**
 * Read information from a Debian source package (.dsc file)
 */
class DscFile
{

private:
    TagFile tf;

public:

    this ()
    {
        tf = new TagFile ();
    }

    void open (string fname)
    {
        tf.open (fname);
    }

    SourcePackage getSourcePackage ()
    {
        // skip PGP signature block
        tf.first ();
        if (tf.readField ("Source") is null)
            tf.nextSection ();

        auto sp = new SourcePackage;

        sp.format = tf.readField ("Format");
        sp.name = tf.readField ("Source");
        sp.architectures = tf.readField ("Architecture", "").split (" ");

        sp.ver = tf.readField ("Version");
        sp.maintainer = tf.readField ("Maintainer");
        sp.standardsVersion = tf.readField ("Standards-Version");
        sp.vcsBrowser = tf.readField ("Vcs-Browser");

        sp.buildDepends = tf.readField ("Build-Depends", "").split (", ");

        immutable pkgListRaw = tf.readField ("Package-List");
        if (pkgListRaw is null) {
            foreach (bin; tf.readField ("Binary", "").split (", ")) {
                PackageInfo pi;
                pi.name = bin;
                pi.ver = sp.ver;
                sp.binaries ~= pi;
            }
        } else {
            sp.binaries = parsePackageListString (pkgListRaw, sp.ver);
        }

        return sp;
    }

}
