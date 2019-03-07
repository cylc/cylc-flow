#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
import sys
import tarfile

import cylc.flags
from cylc.suite_srv_files_mgr import SuiteSrvFilesManager


FILE_BASE_UUID = 'uuid'
REMOTE_INIT_DONE = 'REMOTE INIT DONE'
REMOTE_INIT_NOT_REQUIRED = 'REMOTE INIT NOT REQUIRED'


def remote_init(uuid_str, rund, indirect_comm=None):
    """cylc remote-init

    Arguments:
        uuid_str (str): suite host UUID
        rund (str): suite run directory
        *indirect_comm (str): use indirect communication via e.g. 'ssh'
    """
    rund = os.path.expandvars(rund)
    srvd = os.path.join(rund, SuiteSrvFilesManager.DIR_BASE_SRV)
    try:
        orig_uuid_str = open(os.path.join(srvd, FILE_BASE_UUID)).read()
    except IOError:
        pass
    else:
        if orig_uuid_str == uuid_str:
            print(REMOTE_INIT_NOT_REQUIRED)
            return
    os.makedirs(rund, exist_ok=True)
    oldcwd = os.getcwd()
    os.chdir(rund)
    try:
        tarhandle = tarfile.open(fileobj=sys.stdin.buffer, mode='r|')
        tarhandle.extractall()
        tarhandle.close()
    finally:
        os.chdir(oldcwd)
    if indirect_comm:
        fname = os.path.join(srvd, SuiteSrvFilesManager.FILE_BASE_CONTACT2)
        with open(fname, 'w') as handle:
            handle.write('%s=%s\n' % (
                SuiteSrvFilesManager.KEY_COMMS_PROTOCOL_2, indirect_comm))
    print(REMOTE_INIT_DONE)
    return


def remote_tidy(rund):
    """cylc remote-tidy

    Arguments:
        rund (str): suite run directory
    """
    rund = os.path.expandvars(rund)
    srvd = os.path.join(rund, SuiteSrvFilesManager.DIR_BASE_SRV)
    for name in [
            SuiteSrvFilesManager.FILE_BASE_CONTACT,
            SuiteSrvFilesManager.FILE_BASE_CONTACT2]:
        fname = os.path.join(srvd, name)
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
