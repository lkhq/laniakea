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

module lknative.git;

import std.stdio : File;
import std.process;
import std.string : format;
import std.array : appender;
import std.path : baseName;
static import std.file;

import lknative.logging;

/**
 * Thrown on an error from Git.
 */
class GitException: Error
{
    @safe pure nothrow
    this (string msg, string file = __FILE__, size_t line = __LINE__, Throwable next = null)
    {
        super (msg, file, line, next);
    }
}

/**
 * Interface with Git (currently the cli tool)
 * to perform some basic operations on Git repositories.
 */
class Git
{

private:

    struct GitResult
    {
        bool success;
        string data;
    }

    string gitExe;
    string repo;

public:

    this ()
    {
        gitExe = "git";
    }

    @property
    string repository () const
    {
        return repo;
    }

    @property
    void repository (string repoPath)
    {
        repo = repoPath;
    }

    private bool executeGit (const string command, const string[] args, string useRepo = null, bool throwError = true)
    {
        string getOutput (File f)
        {
            char[] buf;
            auto output = appender!string;
            while (f.readln (buf)) {
                output ~= buf;
            }
            return output.data;
        }

        auto gitArgs = [gitExe] ~ command ~ args;
        auto gitCmd = pipeProcess (gitArgs,
                                   cast(Redirect) 7,
                                   cast(const(string[string])) null, // env
                                   cast(Config) null, // config
                                   useRepo);

        if (wait (gitCmd.pid) != 0) {
            if (throwError)
                throw new GitException ("%s\n%s".format (getOutput (gitCmd.stdout), getOutput (gitCmd.stderr)));
            else
                return false;
        }

        return true;
    }

    bool clone (string repoUrl)
    {
        return executeGit ("clone", [repoUrl, repo]);
    }

    bool pull (string origin = null, string branch = null)
    {
        string[] args = [];
        if ((origin !is null) && (branch !is null))
            args = [origin, branch];

        return executeGit ("pull", args, repo);
    }

}
