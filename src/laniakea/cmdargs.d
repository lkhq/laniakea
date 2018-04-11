/*
 * Copyright (C) 2018 Matthias Klumpp <matthias@tenstral.net>
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

module laniakea.cmdargs;

import std.array : empty;
public import std.getopt : Option, getopt, GetoptResult;
import std.getopt : defaultGetoptPrinter;

/**
 * Short information on a program subcommand.
 */
struct SubcommandInfo
{
    string name;    /// Name of the subcommand
    string summary; /// Short information about the subcommand
}

/**
 * Print help text to stdout.
 */
void printHelpText (string progname, string summary, string description,
                    SubcommandInfo[] subcommands, Option[] opts, string subcommand = null)
{
    import std.stdio : writeln, writefln;

    // we don't want the automatically added --help option
    Option[] optsFiltered;
    bool hasHelp = false;
    foreach (ref o; opts) {
        if (o.optLong != "--help")
            optsFiltered ~= o;
        else
            hasHelp = true;
    }

    writeln ("Usage:");
    if (subcommand.empty)
        writeln (progname, " <subcommand> [OPTION...] - ", summary);
    else
        writeln (progname, " ", subcommand, " [OPTION...] - ", summary);
    writeln ("\n", description, "\n");

    if (!subcommands.empty) {
        writeln ("Subcommands:");

        size_t longestCmdLength = 2;
        foreach (ref cmd; subcommands) {
            if (cmd.name.length > longestCmdLength)
                longestCmdLength = cmd.name.length;
        }

        foreach (ref cmd; subcommands)
            writefln (" %*s    %s", longestCmdLength, cmd.name, cmd.summary);

        writeln ();
    }

    if (hasHelp) {
        writeln ("Help Options:");
        writeln (" -h, --help    Show helpful information.");
        writeln ();
    }

    if (!optsFiltered.empty) {
        size_t longestShortOptionLen;
        size_t longestLongOptionLen;
        foreach (ref it; optsFiltered) {
            if (it.optShort.length > longestShortOptionLen)
                longestShortOptionLen = it.optShort.length;
            if (it.optLong.length > longestLongOptionLen)
                longestLongOptionLen = it.optLong.length;
        }

        writeln ("Program Options:");
        foreach (ref it; optsFiltered) {
            if (it.optShort.empty)
                writefln (" %*s  %*s%s   %s",
                          longestShortOptionLen, it.optShort,
                          longestLongOptionLen, it.optLong,
                          it.required ? " Required: " : " ",
                          it.help);
            else
                writefln (" %*s, %*s%s   %s",
                          longestShortOptionLen, it.optShort,
                          longestLongOptionLen, it.optLong,
                          it.required ? " Required: " : " ",
                          it.help);
        }
    }
}

/**
 * Print Laniakea version in a new line on stdout.
 */
void printLaniakeaVersion ()
{
    import std.stdio : writeln;
    import laniakea.localconfig : laniakeaVersion;
    writeln ("Version: ", laniakeaVersion);
}
