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

import std.stdio : writeln, writefln;
import std.getopt;
import std.string : format;
import std.array : empty;
import core.stdc.stdlib : exit;

import laniakea.localconfig;
import laniakea.logging;
import keytool.zcurveutils;


private immutable helpText =
"Usage:
  lk-keytool <subcommand> [OPTION...] - Manage keys and certs

Administrative tool for creating and installing new keys and certificates
for clients and servers on the command-line.

Help Options:
  -h, --help       Show help options

Application Options:
  --version        Show the program version.
  --verbose        Show extra debugging information.";

void main (string[] args)
{
    bool verbose;
    bool showHelp;
    bool showVersion;

    // parse command-line options
    try {
        getopt (args,
            std.getopt.config.passThrough,
            "help|h", &showHelp,
            "verbose", &verbose,
            "version", &showVersion);
    } catch (Exception e) {
        writeln ("Unable to parse parameters: ", e.msg);
        exit (1);
    }

    if (showHelp) {
        writeln (helpText);
        return;
    }

    if (showVersion) {
        writeln ("Version: ", laniakea.localconfig.laniakeaVersion);
        return;
    }

    if (args.length < 2) {
        writeln ("No subcommand specified!");
        return;
    }

    auto conf = LocalConfig.get;
    try {
        conf.load (LkModule.KEYTOOL);
    } catch (Exception e) {
        writefln ("Unable to load configuration: %s", e.msg);
        exit (4);
    }

    // globally enable verbose mode, if requested
    if (verbose) {
        laniakea.logging.setVerboseLog (true);
    }

    immutable command = args[1];
    switch (command) {
        case "cert-new":
            string k_name;
            string k_email;
            string k_organization;
            try {
                getopt (args,
                    std.getopt.config.required, "name", &k_name,
                    std.getopt.config.required, "email", &k_email,
                    std.getopt.config.required, "organization", &k_organization);
            } catch (Exception e) {
                writeln ("Unable to parse parameters: ", e.msg);
                exit (1);
            }

            if (args.length != 3) {
                writeln ("Invalid number of arguments: A base filename to write the new certificate to is needed.");
                exit (1);
            }

            // create our new certificate
            createSavePrintCertificate (k_name, k_email, k_organization, args[2]);
            break;

        case "install-service-cert":
            bool force = false;
            try {
                getopt (args,
                    "force", &force);
            } catch (Exception e) {
                writeln ("Unable to parse parameters: ", e.msg);
                exit (1);
            }

            if (args.length != 3) {
                writeln ("Invalid number of arguments: A filename to the secret cert file is required.");
                exit (1);
            }

            if (!installServiceCert (args[2], force))
                exit (2);
            break;

        case "install-client-cert":
            bool force = false;
            try {
                getopt (args,
                    "force", &force);
            } catch (Exception e) {
                writeln ("Unable to parse parameters: ", e.msg);
                exit (1);
            }

            if (args.length != 3) {
                writeln ("Invalid number of arguments: A filename to the public cert file is required.");
                exit (1);
            }

            if (!installTrustedCert (args[2], force))
                exit (2);
            break;

        default:
            writeln ("The command '%s' is unknown.".format (command));
            exit (1);
            break;
    }
}
