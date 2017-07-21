#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Implement "cylc remote-init" and "cylc remote-tidy"."""

import os
from subprocess import check_call
import sys
import cylc.flags
from cylc.mkdir_p import mkdir_p
from cylc.suite_srv_files_mgr import SuiteSrvFilesManager


REMOTE_INIT_DONE = 'REMOTE INIT DONE'
REMOTE_INIT_NOT_REQUIRED = 'REMOTE INIT NOT REQUIRED'


def remote_init(uuid_str, rund):
    """cylc remote-init

    Arguments:
        uuid_str (str): suite host UUID
        rund (str): suite run directory
    """
    rund = os.path.expandvars(rund)
    srvd = os.path.join(rund, SuiteSrvFilesManager.DIR_BASE_SRV)
    try:
        orig_uuid_str = open(os.path.join(srvd, 'uuid')).read()
    except IOError:
        pass
    else:
        if orig_uuid_str == uuid_str:
            print(REMOTE_INIT_NOT_REQUIRED)
            return
    mkdir_p(rund)
    # Use "tar" command. Python (2.6) standard library "tarfile" does not
    # appear to work even in stream mode.
    # If "tarfile" works, we can do:
    #
    # import tarfile
    # oldcwd = os.getcwd()
    # os.chdir(rund)
    # try:
    #     tarhandle = tarfile.open(fileobj=sys.stdin, mode='r|')
    #     print tarhandle.getnames()  # some diagnostics
    #     tarhandle.extractall()
    #     tarhandle.close()
    # finally:
    #     os.chdir(oldcwd)
    if cylc.flags.debug:
        check_call(['tar', '-C', rund, '-v', '-x', '-f', '-'], stdin=sys.stdin)
    else:
        check_call(['tar', '-C', rund, '-x', '-f', '-'], stdin=sys.stdin)
    print(REMOTE_INIT_DONE)
    return


def remote_tidy(rund):
    """cylc remote-tidy

    Arguments:
        rund (str): suite run directory
    """
    rund = os.path.expandvars(rund)
    srvd = os.path.join(rund, SuiteSrvFilesManager.DIR_BASE_SRV)
    fname = os.path.join(srvd, SuiteSrvFilesManager.FILE_BASE_CONTACT)
    try:
        os.unlink(fname)
    except OSError:
        if os.path.exists(fname):
            raise
    else:
        if cylc.flags.debug:
            print('Deleted: %s' % fname)
    try:
        os.rmdir(srvd)  # remove directory if empty
    except OSError:
        pass
    else:
        if cylc.flags.debug:
            print('Deleted: %s' % srvd)
