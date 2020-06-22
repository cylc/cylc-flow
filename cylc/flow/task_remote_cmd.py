# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
import zmq
import tarfile
import sys
import datetime

import cylc.flow.flags
from cylc.flow.suite_files import (
    KeyInfo,
    KeyOwner,
    KeyType,
    ContactFileFields,
    get_suite_srv_dir,
    SuiteFiles
)
from cylc.flow.resources import extract_resources


FILE_BASE_UUID = 'uuid'
REMOTE_INIT_DONE = 'REMOTE INIT DONE'
REMOTE_INIT_NOT_REQUIRED = 'REMOTE INIT NOT REQUIRED'


def remove_keys_on_platform(srvd):
    """Removes platform-held authentication keys"""
    keys = {
        "client_private_key": KeyInfo(
            KeyType.PRIVATE,
            KeyOwner.CLIENT,
            suite_srv_dir=srvd),
        "client_public_key": KeyInfo(
            KeyType.PUBLIC,
            KeyOwner.CLIENT,
            suite_srv_dir=srvd, server_held=False),
        "server_public_key": KeyInfo(
            KeyType.PUBLIC,
            KeyOwner.SERVER,
            suite_srv_dir=srvd),
    }
    # WARNING, DESTRUCTIVE. Removes old keys if they already exist.

    for k in keys.values():
        if os.path.exists(k.full_key_path):
            os.remove(k.full_key_path)


def create_platform_keys(srvd):
    """Create or renew authentication keys for suite 'reg' in the .service
     directory.
     Generate a pair of ZMQ authentication keys"""
    # ZMQ keys generated in .service directory.
    # ZMQ keys need to be created with stricter file permissions, changing
    # umask default denials.

    old_umask = os.umask(0o177)  # u=rw only set as default for file creation
    _client_public_full_key_path, _client_private_full_key_path = (
        zmq.auth.create_certificates(srvd, KeyOwner.CLIENT.value))
    # Return file permissions to default settings.
    os.umask(old_umask)


def remote_init(uuid_str, rund, indirect_comm=None):
    """cylc remote-init

    Arguments:
        uuid_str (str): suite host UUID
        rund (str): suite run directory
        *indirect_comm (str): use indirect communication via e.g. 'ssh'
    """
    rund = os.path.expandvars(rund)
    srvd = os.path.join(rund, SuiteFiles.Service.DIRNAME)
    try:
        orig_uuid_str = open(os.path.join(srvd, FILE_BASE_UUID)).read()
    except IOError:
        pass
    else:
        if orig_uuid_str == uuid_str:
            print(REMOTE_INIT_NOT_REQUIRED)
            return
    os.makedirs(srvd, exist_ok=True)
    remove_keys_on_platform(srvd)
    create_platform_keys(srvd)
    oldcwd = os.getcwd()
    os.chdir(rund)
    # Extract job.sh from library, for use in job scripts.
    extract_resources(SuiteFiles.Service.DIRNAME, ['etc/job.sh'])
    try:
        tarhandle = tarfile.open(fileobj=sys.stdin.buffer, mode='r|')
        tarhandle.extractall()
        tarhandle.close()
    finally:
        os.chdir(oldcwd)
    if indirect_comm:
        fname = os.path.join(srvd, SuiteFiles.Service.CONTACT)
        with open(fname, 'a') as handle:
            handle.write('%s=%s\n' % (
                ContactFileFields.COMMS_PROTOCOL_2, indirect_comm))
    path_to_pub_key = os.path.join(srvd, "client.key")
    print("KEYSTART", end='')
    with open(path_to_pub_key) as keyfile:
        print(keyfile.read(), end='KEYEND')
    print(REMOTE_INIT_DONE)
    return


def remote_tidy(rund):
    """cylc remote-tidy

    Arguments:
        rund (str): suite run directory
    """
    rund = os.path.expandvars(rund)
    srvd = os.path.join(rund, SuiteFiles.Service.DIRNAME)
    fname = os.path.join(srvd, SuiteFiles.Service.CONTACT)
    try:
        os.unlink(fname)
    except OSError:
        if os.path.exists(fname):
            raise
    else:
        if cylc.flow.flags.debug:
            print('Deleted: %s' % fname)
    remove_keys_on_platform(srvd)
    try:
        os.rmdir(srvd)  # remove directory if empty
    except OSError:
        pass
    else:
        if cylc.flow.flags.debug:
            print('Deleted: %s' % srvd)
