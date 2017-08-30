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

module rubicon.fileimport;
@safe:

import std.conv : to;
import std.array : empty;
import std.string : format, endsWith;
import std.path : baseName, buildPath;
import std.datetime : SysTime, parseRFC822DateTime;
import std.digest.sha : SHA256;
import std.typecons : No;
import vibe.data.bson : Bson, BsonObjectID;

import laniakea.db;
import laniakea.logging;
import laniakea.tagfile;
import laniakea.pkgitems : ArchiveFile;
import laniakea.utils : findFilesBySuffix, SignedFile, hashFile, randomString;

import rubicon.rubiconfig : RubiConfig;


/**
 * Information contained in an upload description file.
 */
struct DudData
{
    string fname;

    string format;
    SysTime date;

    string architecture;
    string jobId;
    bool success;

    ArchiveFile[] files;

    bool rejected;
    string rejectReason;
}

/**
 * First, try to rename the file (which might fail, e.g. in cross-device-link situations),
 * in case of an error, fall back to copy & delete.
 */
public void safeRename (const string from, const string to) @trusted
{
    import std.file;
    try {
        from.rename (to);
    } catch (Throwable) {
        from.copy (to);
        from.remove ();
    }
}

/**
 * Accept the upload and move its data to the right places.
 */
private void acceptUpload (RubiConfig conf, DudData dud) @trusted
{
    import std.file;
    auto db = Database.get;
    auto collJobs = db.collJobs ();

    // mark job as accepted and done
    auto jobResult = dud.success? JobResult.SUCCESS : JobResult.FAILURE;
    auto job = collJobs.findAndModify (["_id": Bson(BsonObjectID.fromString(dud.jobId))],
                                    ["$set": [
                                        "result": Bson(jobResult.to!int)
                                        ]]);
    if (job.isNull) {
        logError ("Unable to mark job '%s' as done: The Job was not found.", dud.jobId);

        // this is a weird situation, there is no proper way to handle it as this indicates a bug
        // in the Laniakea setup or some other oddity.
        // The least harmful thing to do is to just leave the upload alone and try again later.
        return;
    }

    // move the log file to the log storage
    foreach (ref af; dud.files) {
        if (!af.fname.endsWith (".log"))
            continue;

        auto targetDir = buildPath (conf.logStorageDir, dud.jobId[0..2]);
        mkdirRecurse (targetDir);

        // move the logfile to its destination
        auto targetFname = buildPath (targetDir, dud.jobId ~ ".log");
        af.fname.safeRename (targetFname);
        break;
    }

    // some modules get special treatment
    if (jobResult == JobResult.SUCCESS) {
        import rubicon.importisotope;

        if (job["module"].get!string == LkModule.ISOTOPE)
            handleIsotopeUpload (conf, dud, job);
    }

    // remove the upload description file from incoming
    dud.fname.remove ();
    logInfo ("Upload %s accepted.",  dud.fname.baseName);
}

/**
 * If a file has issues, we reject it and put it into the rejected queue.
 */
private void rejectUpload (RubiConfig conf, DudData dud) @trusted
{
    import std.file;
    mkdirRecurse (conf.rejectedDir);

    // move the files referenced by the .dud file
    foreach (ref af; dud.files) {
        auto targetFname = buildPath (conf.rejectedDir, af.fname.baseName);
        if (targetFname.exists)
            targetFname = targetFname ~ "+" ~ randomString (4);

        // move the file to the rejected dir
        af.fname.safeRename (targetFname);
    }

    // move the .dud file itself
    auto targetFname = buildPath (conf.rejectedDir, dud.fname.baseName);
    if (targetFname.exists)
        targetFname = targetFname ~ "+" ~ randomString (4);
    dud.fname.safeRename (targetFname);

    // also store the reject reason for future reference
    auto rejectReasonFile = targetFname ~ ".reason";
    rejectReasonFile.write (dud.rejectReason ~ "\n");

    logInfo ("Upload %s rejected.", dud.fname.baseName);
}

/**
 * Get information contained in the upload description file.
 */
private DudData loadDataFromDudFile (TagFile tf, string incomingDir)
{
    // ensure we don't try to read the GPG header
    if (!tf.readField ("Hash").empty)
        tf.nextSection ();

    DudData dud;
    dud.fname = tf.fname;
    dud.format = tf.readField ("Format");
    dud.date = parseRFC822DateTime (tf.readField ("Date"));

    dud.architecture = tf.readField ("Architecture");
    dud.jobId = tf.readField ("X-Spark-Job");
    dud.success = (tf.readField ("X-Spark-Success") == "Yes");
    dud.files = parseChecksumsList (tf.readField ("Checksums-Sha256"), incomingDir);

    if (dud.jobId.empty) {
        dud.rejected = true;
        dud.rejectReason = "No valid job ID is present for this upload.";
    }
    if (dud.files.empty) {
        dud.rejected = true;
        dud.rejectReason = "No valid file list is present for this upload.";
    }

    return dud;
}

/**
 * Import files from an untrusted incoming source.
 *
 * IMPORTANT: We assume that the uploader can not edit their files post-upload.
 * If they could, we would be vulnerable to timing attacks here.
 */
void importFilesFrom (RubiConfig conf, string incomingDir) @trusted
{
    auto dudFiles = findFilesBySuffix (incomingDir, ".dud");

    foreach (ref dudf; dudFiles) {
        auto sf = new SignedFile (conf.trustedGpgKeyrings);

        DudData dud;
        // try to verify the signature
        try {
            sf.open (dudf);
        } catch (Exception e) {
            auto tf = new TagFile;
            tf.open (dudf, No.compressed);
            dud = loadDataFromDudFile (tf, incomingDir);

            dud.rejected = true;
            dud.rejectReason = e.to!string;

            rejectUpload (conf, dud);
            continue;
        }

        // try to load the .dud file data
        try {
            auto tf = new TagFile;
            tf.load (sf.content);
            dud = loadDataFromDudFile (tf, incomingDir);
            dud.fname = dudf;
        } catch (Exception e) {
            dud.rejected = true;
            dud.rejectReason = e.to!string;
            rejectUpload (conf, dud);
            continue;
        }

        if (!sf.isValid) {
            dud.rejected = true;
            dud.rejectReason = "Signature on this upload is not valid.";

            rejectUpload (conf, dud);
        }

        // verify the integrity of the uploaded files
        foreach (ref af; dud.files) {
            immutable hash = hashFile!SHA256 (af.fname);
            if (hash != af.sha256sum) {
                dud.rejected = true;
                dud.rejectReason = "Checksum validation of '%s' failed (%s != %s).".format (baseName (af.fname), hash, af.sha256sum);

                rejectUpload (conf, dud);
                continue;
            }
        }
        assert (!dud.rejected);

        // if we are here, the file is good to go
        acceptUpload (conf, dud);
    }
}
