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
import std.stdio : writeln, writefln;

import core.sys.posix.sys.stat : chmod;

import laniakea.localconfig;

/**
 * Create a new ZeroMQ ZAP curve certificate with the given details.
 */
public auto newCertWithDetails (string name, string email, string organization)
{
    auto cert = zcert_new ();
    auto timestr = zclock_timestr ();
    scope(exit) free (timestr);

    zcert_set_meta (cert, "name".toStringz, name.toStringz);
    zcert_set_meta (cert, "email".toStringz, email.toStringz);
    if (!organization.empty)
        zcert_set_meta (cert, "organization".toStringz, organization.toStringz);

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

/**
 * Install a certificate for the current machine/service to use for encrypted
 * communication.
 */
public bool installServiceCert (string fname, bool force = false)
{
    import std.file : exists, mkdirRecurse;
    import std.path : dirName;
    import std.conv : octal;

    auto localConf = LocalConfig.get;
    if (localConf.serviceCurveCertFname.exists && !force) {
        writeln ("This machine already has a curve private key installed for encryption. Specify --force to override it.");
        return false;
    }

    auto cert = zcert_load (fname.toStringz);
    scope(exit) zcert_destroy (&cert);

    mkdirRecurse (localConf.serviceCurveCertFname.dirName);
    auto r = zcert_save_secret (cert, localConf.serviceCurveCertFname.toStringz);
    if (r != 0) {
        writefln ("Unable to install certificate (%s).", r);
        return false;
    } else {
        // FIXME: We actually want the Laniakea service own this, instead of just granting the whole
        // machine read access. The keyutil needs to grow a method to specify groups to have access to
        // the key explicitly.
        chmod (localConf.serviceCurveCertFname.toStringz, octal!644);
    }

    writefln ("Installed as '%s'.", localConf.serviceCurveCertFname);
    return true;
}

/**
 * Install certificate file into the directory of trusted certificates.
 */
public bool installTrustedCert (string fname, bool force = false)
{
    import std.file : exists, mkdirRecurse, copy;
    import std.path : baseName, buildPath;
    import std.conv : octal;
    import std.typecons : Yes;

    auto localConf = LocalConfig.get;

    immutable targetFname = buildPath (localConf.trustedCurveCertsDir, fname.baseName);
    if (targetFname.exists && !force) {
        writeln ("This client certificate already exists in the trusted keyring. Specify --force to override it.");
        return false;
    }

    mkdirRecurse (localConf.trustedCurveCertsDir);
    copy (fname, targetFname, Yes.preserveAttributes);

    // FIXME: We actually want the Laniakea service own this, instead of just granting the whole
    // machine read access. The keyutil needs to grow a method to specify groups to have access to
    // the key explicitly.
    chmod (localConf.serviceCurveCertFname.toStringz, octal!644);

    writefln ("Installed as '%s'.", targetFname);
    return true;
}
