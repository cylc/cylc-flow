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
import re
import sys
import tarfile
import zmq

import cylc.flow.flags
from cylc.flow.suite_files import (
    KeyInfo,
    KeyOwner,
    KeyType,
    SuiteFiles
)
from cylc.flow.pathutil import make_symlink
from cylc.flow.resources import extract_resources
from cylc.flow.task_remote_mgr import (
    REMOTE_INIT_DONE,
    REMOTE_INIT_FAILED
)


def remove_keys_on_client(srvd, install_target, full_clean=False):
    """Removes client authentication keys"""
    keys = {
        "client_private_key": KeyInfo(
            KeyType.PRIVATE,
            KeyOwner.CLIENT,
            suite_srv_dir=srvd),
        "client_public_key": KeyInfo(
            KeyType.PUBLIC,
            KeyOwner.CLIENT,
            suite_srv_dir=srvd,
            install_target=install_target,
            server_held=False),
    }
    # WARNING, DESTRUCTIVE. Removes old keys if they already exist.
    if full_clean:
        keys.update({"server_public_key": KeyInfo(
            KeyType.PUBLIC, KeyOwner.SERVER, suite_srv_dir=srvd)})
    for k in keys.values():
        if os.path.exists(k.full_key_path):
            os.remove(k.full_key_path)


def create_client_keys(srvd, install_target):
    """Create or renew authentication keys for suite 'reg' in the .service
     directory.
     Generate a pair of ZMQ authentication keys"""

    cli_pub_key = KeyInfo(
        KeyType.PUBLIC,
        KeyOwner.CLIENT,
        suite_srv_dir=srvd,
        install_target=install_target,
        server_held=False)
    # ZMQ keys generated in .service directory.
    # ZMQ keys need to be created with stricter file permissions, changing
    # umask default denials.
    old_umask = os.umask(0o177)  # u=rw only set as default for file creation
    client_public_full_key_path, _client_private_full_key_path = (
        zmq.auth.create_certificates(
            srvd, KeyOwner.CLIENT.value))

    os.rename(client_public_full_key_path, cli_pub_key.full_key_path)
    # Return file permissions to default settings.
    os.umask(old_umask)


def remote_init(install_target, rund, *dirs_to_symlink):
    """cylc remote-init

    Arguments:
        install_target (str): target to be initialised
        rund (str): suite run directory
        dirs_to_symlink (list): directories to be symlinked in form
        [directory=symlink_location, ...]
    """
    rund = os.path.expandvars(rund)
    for item in dirs_to_symlink:
        key, val = item.split("=", 1)
        if key == 'run':
            dst = rund
        else:
            dst = os.path.join(rund, key)
        src = os.path.expandvars(val)
        if '$' in src:
            print(REMOTE_INIT_FAILED)
            print(f'Error occurred when symlinking.'
                  f' {src} contains an invalid environment variable.')
            return
        make_symlink(src, dst)
    srvd = os.path.join(rund, SuiteFiles.Service.DIRNAME)
    os.makedirs(srvd, exist_ok=True)

    client_pub_keyinfo = KeyInfo(
        KeyType.PUBLIC,
        KeyOwner.CLIENT,
        suite_srv_dir=srvd, install_target=install_target, server_held=False)
    # Check for existence of client key dir (should only exist on server)
    # Fail if one exists - this may occur on mis-configuration of install
    # target in global.cylc
    client_key_dir = os.path.join(
        srvd, f"{KeyOwner.CLIENT.value}_{KeyType.PUBLIC.value}_keys")
    if os.path.exists(client_key_dir):
        print(REMOTE_INIT_FAILED)
        print(f"Unexpected key directory exists: {client_key_dir}"
              " Check global.cylc install target is configured correctly "
              "for this platform.")
        return
    pattern = re.compile(r"^client_\S*key$")
    for filepath in os.listdir(srvd):
        if pattern.match(filepath) and f"{install_target}" not in filepath:
            # client key for a different install target exists
            print(REMOTE_INIT_FAILED)
            print(f"Unexpected authentication key \"{filepath}\" exists. "
                  "Check global.cylc install target is configured correctly "
                  "for this platform.")
            return
    try:
        remove_keys_on_client(srvd, install_target)
        create_client_keys(srvd, install_target)
    except Exception:
        # Catching all exceptions as need to fail remote init if any problems
        # with key generation.
        print(REMOTE_INIT_FAILED)
        return
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
    print("KEYSTART", end='')
    with open(client_pub_keyinfo.full_key_path) as keyfile:
        print(keyfile.read(), end='KEYEND')
    print(REMOTE_INIT_DONE)
    return


def remote_tidy(install_target, rund):
    """cylc remote-tidy

    Arguments:
        install_target (str): install target name
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
    remove_keys_on_client(srvd, install_target, full_clean=True)
    try:
        os.rmdir(srvd)  # remove directory if empty
    except OSError:
        pass
    else:
        if cylc.flow.flags.debug:
            print('Deleted: %s' % srvd)
