# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2019 Matthias Klumpp <matthias@tenstral.net>
#
# Licensed under the GNU Lesser General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the license, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import os
import pytest


def test_lknative_gpg(samplesdir):
    from laniakea.lknative import SignedFile

    keyring_path = os.path.join(samplesdir, 'gpg', 'keyrings', 'keyring.gpg')
    other_keyring_path = os.path.join(samplesdir, 'gpg', 'keyrings', 'other-keyring.gpg')
    signed_fname = os.path.join(samplesdir, 'gpg', 'SignedFile.txt')
    broken_sig_fname = os.path.join(samplesdir, 'gpg', 'BrokenSigFile.txt')

    # validate "properly signed file" case
    signed_file = SignedFile([keyring_path, other_keyring_path])
    signed_file.open(signed_fname)

    assert signed_file.isValid()
    assert signed_file.fingerprint() == '8BB746C63FF5346326C19ABDEFD8BD07D224478F'
    assert signed_file.primaryFingerprint() == '8BB746C63FF5346326C19ABDEFD8BD07D224478F'
    assert signed_file.signatureId() == 'pLJCPv+5E8eLtVtYPFZ9NWDGbvk'
    assert signed_file.content() == 'I am a harmless test file for the Laniakea Project that\nhas been signed for the testsuite to validate its signature.\n'

    # validate "file with broken signature" case
    broken_sig_file = SignedFile([keyring_path])
    with pytest.raises(RuntimeError) as e:
        broken_sig_file.open(broken_sig_fname)
    assert 'GPGError' in str(e.value)
    assert 'No valid signature found' in str(e.value)

    assert not broken_sig_file.isValid()
    assert not broken_sig_file.content()

    # validate "file which is signed with an untrusted key" case
    signed_file = SignedFile([other_keyring_path])
    with pytest.raises(RuntimeError) as e:
        signed_file.open(signed_fname)
    assert 'GPGError' in str(e.value)
    assert 'No valid signature found' in str(e.value)

    assert not signed_file.isValid()
    assert not signed_file.content()
