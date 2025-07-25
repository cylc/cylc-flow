# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
from cylc.flow.workflow_files import (
    KeyInfo,
    KeyOwner,
    KeyType,
    WorkflowFiles
)
from cylc.flow.pathutil import make_symlink_dir
from cylc.flow.resources import get_resources
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
            workflow_srv_dir=srvd),
        "client_public_key": KeyInfo(
            KeyType.PUBLIC,
            KeyOwner.CLIENT,
            workflow_srv_dir=srvd,
            install_target=install_target,
            server_held=False),
    }
    # WARNING, DESTRUCTIVE. Removes old keys if they already exist.
    if full_clean:
        keys.update({"server_public_key": KeyInfo(
            KeyType.PUBLIC, KeyOwner.SERVER, workflow_srv_dir=srvd)})
    for k in keys.values():
        if os.path.exists(k.full_key_path):
            os.remove(k.full_key_path)


def create_client_keys(srvd, install_target):
    """Create or renew authentication keys for workflow 'id_' in the .service
     directory.
     Generate a pair of ZMQ authentication keys"""

    cli_pub_key = KeyInfo(
        KeyType.PUBLIC,
        KeyOwner.CLIENT,
        workflow_srv_dir=srvd,
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


def remote_init(install_target: str, rund: str, *dirs_to_symlink: str) -> None:
    """cylc remote-init

    Arguments:
        install_target: target to be initialised
        rund: workflow run directory
        dirs_to_symlink: directories to be symlinked in form
        [directory=symlink_location, ...]
    """
    rund = os.path.expandvars(rund)
    for item in dirs_to_symlink:
        key, val = item.split("=", 1)
        if key == 'run':
            path = rund
        else:
            path = os.path.join(rund, key)
        target = os.path.expandvars(val)
        if '$' in target:
            print(REMOTE_INIT_FAILED)
            print(f'Error occurred when symlinking.'
                  f' {target} contains an invalid environment variable.')
            return
        if cylc.flow.flags.verbosity > 1:
            print(f'$ ln -s "{target}" "{path}"')
        make_symlink_dir(path, target)
    srvd = os.path.join(rund, WorkflowFiles.Service.DIRNAME)
    os.makedirs(srvd, exist_ok=True)

    client_pub_keyinfo = KeyInfo(
        KeyType.PUBLIC,
        KeyOwner.CLIENT,
        workflow_srv_dir=srvd,
        install_target=install_target,
        server_held=False
    )
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
    get_resources(
        'job.sh',
        os.path.join(WorkflowFiles.Service.DIRNAME, 'etc')
    )
    # Extract sent contact file from stdin:
    try:
        with tarfile.open(fileobj=sys.stdin.buffer, mode='r|') as tarhandle:
            tarhandle.extractall()  # nosec B202 - there should not be any
            # untrusted members in the tar stream, only the contact file
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
        rund (str): workflow run directory
    """
    rund = os.path.expandvars(rund)
    srvd = os.path.join(rund, WorkflowFiles.Service.DIRNAME)
    fname = os.path.join(srvd, WorkflowFiles.Service.CONTACT)
    try:
        os.unlink(fname)
    except OSError:
        if os.path.exists(fname):
            raise
    else:
        if cylc.flow.flags.verbosity > 1:
            print('Deleted: %s' % fname)
    remove_keys_on_client(srvd, install_target, full_clean=True)
    try:
        os.rmdir(srvd)  # remove directory if empty
    except OSError:
        pass
    else:
        if cylc.flow.flags.verbosity > 1:
            print('Deleted: %s' % srvd)
