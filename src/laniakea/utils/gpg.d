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

module laniakea.utils.gpg;

import std.string : format, splitLines;
import std.array : empty, split;
import core.sys.posix.unistd : pid_t;

import laniakea.logging;



/**
 * Thrown on an error with GnuPG.
 */
class GPGError: Error
{
    @safe pure nothrow
    this (string msg, string file = __FILE__, size_t line = __LINE__, Throwable next = null)
    {
        super (msg, file, line, next);
    }
}

/**
 * Thrown on an error which sets errno.
 */
class SysError: Error
{
    @trusted
    this (string msg, string file = __FILE__, size_t line = __LINE__, Throwable next = null)
    {
        import core.stdc.errno;
        import core.stdc.string;

        super ("%s: %s".format (msg, strerror (errno)), file, line, next);
    }
}



/**
 * Helper class to create pipes.
 */
private class SysPipe
{
    private int[2] chan;

    this ()
    {
        import core.sys.posix.unistd;

        if (pipe (chan) < 0)
            throw new SysError ("Could not create pipe");
    }

    ~this ()
    {
        close ();
    }

    @property
    int r ()
    {
        return chan[0];
    }

    @property
    int w ()
    {
        return chan[1];
    }

    @property
    int wClosed ()
    {
        return chan[1] < 0;
    }

    /**
     * Close reading side of the pipe.
     */
    void closeR ()
    {
        import core.sys.posix.unistd : close;

        if (chan[0] != -1) {
            close (chan[0]);
            chan[0] = -1;
        }
    }

    /**
     * Close writing side of the pipe.
     */
    void closeW ()
    {
        import core.sys.posix.unistd : close;

        if (chan[1] != -1) {
            close (chan[1]);
            chan[1] = -1;
        }
    }

    /**
     * Close pipe.
     */
    void close ()
    {
        closeW ();
        closeR ();
    }
}

/**
 * Handle files signed with PGP
 *
 * The following attributes are available:
 *  contents            - string with the content (after removing PGP armor)
 *  valid               - Boolean indicating a valid signature was found
 *  fingerprint         - fingerprint of the key used for signing
 *  primary_fingerprint - fingerprint of the primary key associated to the key used for signing
 */
class SignedFile
{

private:

    string gpgExe;
    string data;
    string _content;

    string[] keyrings;

    bool valid;
    bool expired;
    bool invalid;

    string[] fingerprints;
    string[] primaryFingerprints;
    string[] signatureIds;

    size_t MAXFD;

public:

    this (string[] keyrings)
    {
        import core.sys.posix.unistd;

        gpgExe = "/usr/bin/gpg";
        this.keyrings = keyrings;

        MAXFD = sysconf (_SC_OPEN_MAX);
        if (MAXFD < 0)
            MAXFD = 256;

        valid = false;
    }

    void load (string data, bool requireSignature = true)
    {
        verify (data, requireSignature);
    }

    void open (string fname, bool requireSignature = true)
    {
        import std.stdio;
        import std.array : appender;

        auto f = File (fname, "r");
        auto data = appender!string;
        string line;
        while ((line = f.readln ()) !is null)
            data ~= line;

        load (data.data, requireSignature);
    }

    @property
    bool isValid ()
    {
        return valid;
    }

    @property
    string content ()
    {
        return _content;
    }

    @property
    string fingerprint ()
    {
        assert (fingerprints.length == 1);
        return fingerprints[0];
    }

    @property
    string primaryFingerprint ()
    {
        assert (primaryFingerprints.length == 1);
        return primaryFingerprints[0];
    }

    @property
    string signatureId ()
    {
        assert (signatureIds.length == 1);
        return signatureIds[0];
    }

    private void verify (string data, bool requireSignature)
    {
        import core.sys.posix.unistd : fork, pid_t;
        import core.sys.posix.sys.wait : waitpid;
        import std.stdio : writeln;

        // create out pipoes and close them as soon as the verification is done.
        auto stdinP = new SysPipe ();
        auto contentsP = new SysPipe ();
        auto statusP = new SysPipe ();
        auto stderrP = new SysPipe ();
        scope (exit) {
            stdinP.close ();
            contentsP.close ();
            statusP.close ();
            stderrP.close ();
        }

        auto pid = fork ();
        if (pid == 0) {
            // we are the forked process - run GPG
            execGpg (stdinP.r, contentsP.w, stderrP.w, statusP.w);
        } else {
            // communicate with GPG

            // close unnecessary end of the pipes
            stdinP.closeR ();
            contentsP.closeW ();
            stderrP.closeW ();
            statusP.closeW ();

            auto read = doIO (pid, [contentsP.r, stderrP.r, statusP.r], stdinP, data);

            waitpid (pid, null, 0);

            auto contents = read[contentsP.r];
            auto status   = read[statusP.r];
            auto stderr   = read[stderrP.r];

            if (status.empty)
                throw new GPGError ("No status output from GPG: %s".format (stderr));

            foreach (ref line; status.splitLines) {
                parseStatus (line);
            }

            if ((requireSignature) && (!this.valid))
                throw new GPGError ("No valid signature found: %s".format (stderr));

            assert (fingerprints.length == primaryFingerprints.length);
            assert (fingerprints.length == signatureIds.length);
            _content = contents;
        }
    }

    string[int] doIO (pid_t pid, int[] readFDs, SysPipe stdin, string inputData)
    {
        import core.sys.posix.fcntl;
        import core.sys.posix.sys.select;
        import core.sys.posix.unistd;
        import core.sys.posix.sys.wait : waitpid, WNOHANG;
        import std.conv : to;
        import std.string : toStringz, fromStringz;

        fd_set rfds;
        fd_set wfds;
        int nfds = 0;

        FD_ZERO (&rfds);
        foreach (ref fd; readFDs) {
            FD_SET (fd, &rfds);

            auto old = fcntl (fd, F_GETFL);
            fcntl (fd, F_SETFL, old | O_NONBLOCK);
            if (fd > nfds)
                nfds = fd;
        }

        FD_ZERO (&wfds);
        FD_SET (stdin.w, &rfds);
        auto old = fcntl (stdin.w, F_GETFL);
        fcntl (stdin.w, F_SETFL, old | O_NONBLOCK);
        if (stdin.w > nfds)
            nfds = stdin.w;

        string[int] readLines;
        foreach (ref fd; readFDs)
            readLines[fd] = "";

        size_t writePos = 0;
        bool working = true;
        nfds += 1;

        while (working) {
            working = waitpid (pid, null, WNOHANG) == 0;

            // wait for FDs to become ready
            //select (nfds, &rfds, &wfds, null, null);
            // FIXME: A working select() would make this much more efficient, unfortunately it
            // hangs indefinitely. As soon as there is more time, we need to investigate why.

            // read stuff from FDs
            foreach (ref fd; readFDs) {
                char[4096] data;
                auto len = read (fd, &data, 4096);
                if (len <= 0)
                    continue;

                working = true;
                readLines[fd] ~= to!string (data[0..len]);
            }

            auto dataSlice = inputData[writePos..$];
            if (dataSlice.empty) {
                stdin.closeW ();
            } else {
                auto data = dataSlice.toStringz;
                auto bytesWritten = write (stdin.w, data, char.sizeof * dataSlice.length);
                writePos += bytesWritten;
                working = true;
            }
        }

        return readLines;
    }

    private void execGpg (int stdin, int stdout, int stderr, int statusfd)
    {
        import std.string : toStringz, fromStringz;
        import core.sys.posix.unistd : dup2, close, execvp;
        import core.sys.posix.stdlib : exit, malloc;
        import core.sys.posix.fcntl;

        if (stdin != 0)
            dup2 (stdin, 0);
        if (stdout != 1)
            dup2 (stdout, 1);
        if (stderr != 2)
            dup2 (stderr, 2);
        if (statusfd != 3)
            dup2 (statusfd, 3);

        foreach (fd; [0, 1, 2, 3]) {
            auto old = fcntl (fd, F_GETFD);
            fcntl (fd, F_SETFD, old & ~FD_CLOEXEC);
        }

        // close all FDs that we don't need
        int fd = 4;
        while (fd < MAXFD) {
            close (fd);
            fd++;
        }

        auto args = [gpgExe,
                        "--status-fd=3",
                        "--no-default-keyring",
                        "--batch",
                        "--no-tty",
                        "--trust-model", "always",
                        "--fixed-list-mode"];
        foreach (ref k; keyrings)
            args ~= "--keyring=%s".format (k);
        args ~= "--decrypt";
        args ~= "-";

        auto cArgs = cast(immutable(char)**) malloc ((char*).sizeof * args.length);
        int i = 0;
        foreach (ref c; args) {
            cArgs[i] = c.toStringz;
            i++;
        }
        cArgs[args.length] = null;

        execvp (gpgExe.toStringz, cArgs);
    }

    private void parseStatus (string line)
    {
        import std.algorithm : canFind;

        auto fields = line.split (" ");

        if (fields[0] != "[GNUPG:]")
            throw new GPGError ("Unexpected output on status-fd: %s".format (line));

        if (fields[1].empty)
            return;

        // VALIDSIG    <fingerprint in hex> <sig_creation_date> <sig-timestamp>
        //             <expire-timestamp> <sig-version> <reserved> <pubkey-algo>
        //             <hash-algo> <sig-class> <primary-key-fpr>
        if (fields[1] == "VALIDSIG") {
            this.valid = true;

            fingerprints ~= fields[2];
            primaryFingerprints ~= fields[11];
            //signatureTimestamp = self._parse_timestamp (fields[4], fields[3])
        } else if (fields[1] == "BADARMOR") {
            throw new GPGError ("Bad armor.");
        } else if (fields[1] == "NODATA") {
            throw new GPGError ("No data.");
        } else if (fields[1] == "DECRYPTION_FAILED") {
            throw new GPGError ("Decryption failed.");
        } else if (fields[1] == "ERROR") {
            throw new GPGError ("Other error: %s %s".format (fields[2], fields[3]));
        } else if (fields[1] == "SIG_ID") {
            signatureIds ~= fields[2];
        } else if (["PLAINTEXT",
                    "GOODSIG",
                    "NOTATION_NAME",
                    "NOTATION_DATA",
                    "SIGEXPIRED",
                    "KEYEXPIRED",
                    "POLICY_URL"].canFind (fields[1])) {
            // we ignore these fields
        } else if (["EXPSIG", "EXPKEYSIG"].canFind (fields[1])) {
            this.expired = true;
            this.valid = false;
        } else if (["REVKEYSIG",
                    "BADSIG",
                    "ERRSIG",
                    "KEYREVOKED",
                    "NO_PUBKEY"].canFind (fields[1])) {
            this.valid = false;
        } else {
            throw new GPGError ("Keyword '%s' from GnuPG was not expected.".format (fields[1]));
        }

    }

}
