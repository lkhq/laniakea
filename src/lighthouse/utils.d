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

module lighthouse.utils;

import std.conv : to;
import std.string : toStringz, fromStringz;
import c.zmq;

string getErrnoStr ()
{
    import core.stdc.errno : errno;
    import core.stdc.string : strerror;

    return strerror (errno).fromStringz.to!string;
}

zframe_t *frameForStr (string s)
{
    import core.stdc.string : strlen;
    auto sZ = s.toStringz;
    // we use strlen here, so we can be sure the length is correct (in case of unicode chars)
    return zframe_new (sZ, strlen (sZ) * char.sizeof);
}
