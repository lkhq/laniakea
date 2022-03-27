# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2018 Ansgar Burchardt <ansgar@debian.org>
# Copyright (C) 2018-2019 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import fcntl
import select
import datetime
import subprocess
from typing import List, Union, Optional
from pathlib import Path

import apt_pkg

from laniakea.logging import log

try:
    _MAXFD = os.sysconf('SC_OPEN_MAX')
except Exception:
    _MAXFD = 256


class GpgException(Exception):
    pass


class _Pipe:
    '''context manager for pipes

    Note: When the pipe is closed by other means than the close_r and close_w
    methods, you have to set self.r (self.w) to None.
    '''

    def __enter__(self):
        (self.r, self.w) = os.pipe()
        return self

    def __exit__(self, type, value, traceback):
        self.close_w()
        self.close_r()
        return False

    def close_r(self):
        '''close reading side of the pipe'''
        if self.r:
            os.close(self.r)
            self.r = None

    def close_w(self):
        '''close writing part of the pipe'''
        if self.w:
            os.close(self.w)
            self.w = None


class SignedFile:
    '''handle files signed with PGP

    The following attributes are available:
      contents            - byte-string with the content (after removing PGP armor)
      valid               - Boolean indicating a valid signature was found
      weak_signature      - signature uses a weak algorithm (e.g. SHA-1)
      fingerprint         - fingerprint of the key used for signing
      primary_fingerprint - fingerprint of the primary key associated to the key used for signing
    '''

    def __init__(self, data, keyrings: Optional[List[str]], *, require_signature=True, gpg='/usr/bin/gpg'):
        '''
        @param data: byte-string containing the message
        @param keyrings: sequence of keyrings
        @param require_signature: if True (the default), will raise an exception if no valid signature was found
        @param gpg: location of the gpg binary
        '''
        if not keyrings:
            keyrings = []

        self.gpg = gpg
        self.keyrings = keyrings

        self.valid = False
        self.expired = False
        self.invalid = False
        self.weak_signature = False
        self.fingerprints: List[str] = []
        self.primary_fingerprints: List[str] = []
        self.signature_ids: List[str] = []

        self._verify(data, require_signature)

    @property
    def fingerprint(self):
        assert len(self.fingerprints) == 1
        return self.fingerprints[0]

    @property
    def primary_fingerprint(self):
        assert len(self.primary_fingerprints) == 1
        return self.primary_fingerprints[0]

    @property
    def signature_id(self):
        assert len(self.signature_ids) == 1
        return self.signature_ids[0]

    def _verify(self, data, require_signature):
        with _Pipe() as stdin, _Pipe() as contents, _Pipe() as status, _Pipe() as stderr:
            pid = os.fork()
            if pid == 0:
                self._exec_gpg(stdin.r, contents.w, stderr.w, status.w)
            else:
                stdin.close_r()
                contents.close_w()
                stderr.close_w()
                status.close_w()

                read = self._do_io([contents.r, stderr.r, status.r], {stdin.w: data})
                stdin.w = None  # was closed by _do_io

                (pid_, exit_code, usage_) = os.wait4(pid, 0)

                self.contents = read[contents.r]
                self.status = read[status.r]
                self.stderr = read[stderr.r]

                if self.status == b'':
                    stderr = self.stderr.decode('ascii', errors='replace')
                    raise GpgException(
                        'No status output from GPG. (GPG exited with status code %s)\n%s' % (exit_code, stderr)
                    )

                for line in self.status.splitlines():
                    self._parse_status(line)

                if self.invalid:
                    self.valid = False

                if require_signature and not self.valid:
                    stderr = self.stderr.decode('ascii', errors='replace')
                    raise GpgException(
                        'No valid signature found. (GPG exited with status code %s)\n%s' % (exit_code, stderr)
                    )

        assert len(self.fingerprints) == len(self.primary_fingerprints)
        assert len(self.fingerprints) == len(self.signature_ids)

    def _do_io(self, read, write):
        for fd in write:
            old = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, old | os.O_NONBLOCK)

        read_lines = dict((fd, []) for fd in read)
        write_pos = dict((fd, 0) for fd in write)

        read_set = list(read)
        write_set = list(write)
        while len(read_set) > 0 or len(write_set) > 0:
            r, w, x_ = select.select(read_set, write_set, ())
            for fd in r:
                data = os.read(fd, 4096)
                if len(data) == 0:
                    read_set.remove(fd)
                else:
                    read_lines[fd].append(data)
            for fd in w:
                data = write[fd][write_pos[fd] :]
                if len(data) == 0:
                    os.close(fd)
                    write_set.remove(fd)
                else:
                    bytes_written = os.write(fd, data)
                    write_pos[fd] += bytes_written

        return dict((fd, b''.join(read_lines[fd])) for fd in read_lines)

    def _parse_timestamp(self, timestamp, datestring=None):
        '''parse timestamp in GnuPG's format

        @rtype:   L{datetime.datetime}
        @returns: datetime object for the given timestamp
        '''
        # The old implementation did only return the date. As we already
        # used this for replay production, return the legacy value for
        # old signatures.
        if datestring is not None:
            year, month, day = datestring.split(b'-')
            date = datetime.date(int(year), int(month), int(day))
            time = datetime.time(0, 0)
            if date < datetime.date(2014, 8, 4):
                return datetime.datetime.combine(date, time)

        if b'T' in timestamp:
            raise Exception('No support for ISO 8601 timestamps.')
        return datetime.datetime.utcfromtimestamp(int(timestamp))

    def _parse_status(self, line):
        fields = line.split()
        if fields[0] != b'[GNUPG:]':
            raise GpgException('Unexpected output on status-fd: %s' % line)

        # VALIDSIG    <fingerprint in hex> <sig_creation_date> <sig-timestamp>
        #             <expire-timestamp> <sig-version> <reserved> <pubkey-algo>
        #             <hash-algo> <sig-class> <primary-key-fpr>
        if fields[1] == b'VALIDSIG':
            # GnuPG accepted MD5 as a hash algorithm until gnupg 1.4.20,
            # which Debian 8 does not yet include.  We want to make sure
            # to not accept uploads covered by a MD5-based signature.
            # RFC 4880, table 9.4:
            #   1 - MD5
            #   2 - SHA-1
            #   3 - RIPE-MD/160
            if fields[9] == b'1':
                raise GpgException('Digest algorithm MD5 is not trusted.')
            if fields[9] in (b'2', b'3'):
                self.weak_signature = True

            self.valid = True
            self.fingerprints.append(fields[2].decode('ascii'))
            self.primary_fingerprints.append(fields[11].decode('ascii'))
            self.signature_timestamp = self._parse_timestamp(fields[4], fields[3])

        elif fields[1] == b'BADARMOR':
            raise GpgException('Bad armor.')

        elif fields[1] == b'NODATA':
            raise GpgException('No data.')

        elif fields[1] == b'DECRYPTION_FAILED':
            raise GpgException('Decryption failed.')

        elif fields[1] == b'ERROR':
            f2 = fields[2].decode('ascii', errors='replace')
            f3 = fields[3].decode('ascii', errors='replace')
            raise GpgException('Other error: %s %s' % (f2, f3))

        elif fields[1] == b'SIG_ID':
            self.signature_ids.append(fields[2])

        elif fields[1] in (
            b'PLAINTEXT',
            b'GOODSIG',
            b'KEY_CONSIDERED',
            b'NEWSIG',
            b'NOTATION_NAME',
            b'NOTATION_FLAGS',
            b'NOTATION_DATA',
            b'SIGEXPIRED',
            b'KEYEXPIRED',
            b'POLICY_URL',
            b'PROGRESS',
            b'VERIFICATION_COMPLIANCE_MODE',
        ):
            pass

        elif fields[1] in (b'EXPSIG', b'EXPKEYSIG'):
            self.expired = True
            self.invalid = True

        elif fields[1] in (b'REVKEYSIG', b'BADSIG', b'ERRSIG', b'KEYREVOKED', b'NO_PUBKEY'):
            self.invalid = True

        else:
            field = fields[1].decode('ascii', errors='replace')
            raise GpgException('Keyword "{0}" from GnuPG was not expected.'.format(field))

    def _exec_gpg(self, stdin, stdout, stderr, statusfd):
        try:
            if stdin != 0:
                os.dup2(stdin, 0)
            if stdout != 1:
                os.dup2(stdout, 1)
            if stderr != 2:
                os.dup2(stderr, 2)
            if statusfd != 3:
                os.dup2(statusfd, 3)
            for fd in range(4):
                old = fcntl.fcntl(fd, fcntl.F_GETFD)
                fcntl.fcntl(fd, fcntl.F_SETFD, old & ~fcntl.FD_CLOEXEC)
            os.closerange(4, _MAXFD)

            args = [
                self.gpg,
                '--status-fd=3',
                '--no-default-keyring',
                '--batch',
                '--no-tty',
                '--trust-model',
                'always',
                '--fixed-list-mode',
            ]
            for k in self.keyrings:
                args.extend(['--keyring', k])
            args.extend(['--decrypt', '-'])

            os.execvp(self.gpg, args)
        finally:
            os._exit(1)

    def contents_sha1(self):
        return apt_pkg.sha1sum(self.contents)


def sign(
    infile,
    outfile,
    keyids: list[str] = None,
    inline=False,
    pubring=None,
    secring=None,
    homedir=None,
    passphrase_file=None,
):

    if not keyids:
        keyids = []

    args = [
        '/usr/bin/gpg',
        '--no-options',
        '--no-tty',
        '--batch',
        '--armour',
        '--personal-digest-preferences',
        'SHA256',
    ]

    for keyid in keyids:
        args.extend(['--local-user', keyid])
    if pubring is not None:
        args.extend(['--keyring', pubring])
    if secring is not None:
        args.extend(['--secret-keyring', secring])
    if homedir is not None:
        args.extend(['--homedir', homedir])
    if passphrase_file is not None:
        args.extend(['--pinentry-mode', 'loopback', '--passphrase-file', passphrase_file])

    args.append('--clearsign' if inline else '--detach-sign')

    log.debug('Calling GPG: %s', ' '.join(args))
    subprocess.check_call(args, stdin=infile, stdout=outfile)


def import_keyfile(gpghome: Union[Path, str], fname: Union[Path, str]) -> List[str]:
    """Import a GPG (public) keyfile into the keyring set by :gpghome"""

    args = [
        '/usr/bin/gpg',
        '--no-default-keyring',
        '--homedir',
        str(gpghome),
        '--no-tty',
        '--batch',
        '--status-fd=1',
        '--import',
        str(fname),
    ]

    proc = subprocess.run(args, capture_output=True, check=False)
    if proc.returncode != 0:
        raise GpgException('Unable to import key: {!r}{!r}'.format(proc.stderr, proc.stdout))

    key_fingerprints = []
    for line in str(proc.stdout, 'utf-8').splitlines():
        if line.startswith('[GNUPG:] IMPORT_OK'):
            parts = line.split(' ')
            key_fingerprints.append(parts[3])
    if not key_fingerprints:
        raise GpgException('Imported key, but unable to determine fingerprint of the new key.:')

    return key_fingerprints
