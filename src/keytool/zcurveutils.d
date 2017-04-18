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

import c.zmq;
import c.zmq.zclock;
import std.string : toStringz, fromStringz, format;
import std.array : empty;
import core.stdc.stdlib : free;

/**
 * Create a new ZeroMQ ZAP curve certificate with the given details.
 */
public auto newCertWithDetails (string name, string email, string organization)
{
    auto cert = zcert_new ();
    auto timestr = zclock_timestr ();
    scope(exit) free (timestr);

    zcert_set_meta (cert, "created-by".toStringz, "Laniakea Keytool".toStringz);
    zcert_set_meta (cert, "date-created".toStringz, "%s".toStringz, timestr);

    return cert;
}

/**
 * Save certificate to the give file(s).
 */
public void saveCert (zcert_t *cert, string pubkey_fname, string privkey_fname = null)
{
    if (privkey_fname.empty)
        privkey_fname = pubkey_fname;
    auto pub_fname = "%s.pub".format (pubkey_fname);
    auto priv_fname = "%s_private.sec".format (privkey_fname);

    auto r = zcert_save_public (cert, pub_fname.toStringz);
    if (r != 0)
        throw new Exception ("Error %s while trying to write public key file.".format (r));

    r = zcert_save_secret (cert, priv_fname.toStringz);
    if (r != 0)
        throw new Exception ("Error %s while trying to write private key file.".format (r));
}

/**
 * Convenience method for quickly building, saving and displaying a certificate.
 */
public void createSavePrintCertificate (string name, string email, string organization, string base_fname)
{
    import std.stdio : writeln;
    auto cert = newCertWithDetails (name, email, organization);
    scope(exit) zcert_destroy (&cert);

    saveCert (cert, base_fname);

    writeln ("Created new certificate with public key: %s".format (zcert_public_txt (cert).fromStringz));
}
