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

import std.stdio;
import std.path : buildPath;
import std.string : startsWith, endsWith;
import std.exception;

import testutils;
import laniakea.utils.gpg;


void testGnuPG (const string datadir)
{
    printTestInfo ("GPG");

    immutable keyringPath = buildPath (datadir, "gpg", "keyrings", "keyring.gpg");
    immutable otherKeyringPath = buildPath (datadir, "gpg", "keyrings", "other-keyring.gpg");
    immutable signedFileName = buildPath (datadir, "gpg", "SignedFile.txt");
    immutable brokenSigFileName = buildPath (datadir, "gpg", "BrokenSigFile.txt");

    // validate "properly signed file" case
    auto signedFile = new SignedFile ([keyringPath, otherKeyringPath]);
    signedFile.open (signedFileName);

    assert (signedFile.isValid);
    assertEq (signedFile.fingerprint, "8BB746C63FF5346326C19ABDEFD8BD07D224478F");
    assertEq (signedFile.primaryFingerprint, "8BB746C63FF5346326C19ABDEFD8BD07D224478F");
    assertEq (signedFile.signatureId, "pLJCPv+5E8eLtVtYPFZ9NWDGbvk");
    assertEq (signedFile.content, "I am a harmless test file for the Laniakea Project that\nhas been signed for the testsuite to validate its signature.\n");

    // validate "file with broken signature" case
    auto brokenSigFile = new SignedFile ([keyringPath]);
    assertThrown!GPGError (brokenSigFile.open (brokenSigFileName));
    assert (!brokenSigFile.isValid);
    assertEq (brokenSigFile.content, "");

    // validate "file which is signed with an untrusted key" case
    signedFile = new SignedFile ([otherKeyringPath]);
    assertThrown!GPGError (signedFile.open (signedFileName));
    assert (!signedFile.isValid);
    assertEq (signedFile.content, "");
}
