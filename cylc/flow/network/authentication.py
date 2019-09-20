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
"""Network authentication layer."""

import getpass
import json
import os
import shutil
import stat

import zmq.auth

from cylc.flow.suite_files import UserFiles


# Directory to contain the sub-directories holding server authentication keys:
SERVER_KEYS_PARENT_DIR = os.path.join(
    os.path.expanduser("~"), UserFiles.DIRNAME)
# Tails of paths (file name with parent directory) to keys:
PUBLIC_KEY_LOC_TAIL = os.path.join(
        UserFiles.Auth.DIRNAME, UserFiles.get_certificate_name())
PRIVATE_KEY_LOC_TAIL = os.path.join(
        UserFiles.Auth.DIRNAME, UserFiles.get_certificate_name(private=True))


def return_key_locations(store_dir):
    """ Return a tuple w/ paths to a dir's public and private key files. """
    return (
        os.path.join(store_dir, SuiteSrvFilesManager.FILE_BASE_PUBLIC_KEY),
        os.path.join(store_dir, SuiteSrvFilesManager.FILE_BASE_PRIVATE_KEY)
    )


def generate_key_store(store_parent_dir, keys_tag):
    """ Generate two sub-directories, each holding a file with a CURVE key. """
    # Define the directory structure to store the CURVE keys in
    store_dir = os.path.join(
        store_parent_dir, UserFiles.Auth.DIRNAME)
    public_key_location = os.path.join(
        store_dir, UserFiles.get_certificate_name())
    private_key_location = os.path.join(
        store_dir, UserFiles.get_certificate_name(private=True))

    # Create, or wipe, that directory structure
    for directory in [store_dir, public_key_location, private_key_location]:
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.mkdir(directory)

    # Make a new public-private CURVE key pair
    zmq.auth.create_certificates(store_dir, keys_tag)

    # Move the pair of keys to appropriate directories, & lock private key file
    for key_file in os.listdir(store_dir):
        if key_file.endswith(".key"):
            shutil.move(os.path.join(store_dir, key_file),
                        os.path.join(public_key_location, '.'))
            # The public key keeps standard '-rw-r--r--.' file permissions
        elif key_file.endswith(".key_secret"):
            loc = shutil.move(os.path.join(store_dir, key_file),
                              os.path.join(private_key_location, '.'))
            # Now lock the prviate key in its permanent location
            try:
                lockdown_private_keys(loc)
            except Exception:  # catch anything; private keys must get locked
                raise OSError(
                    "Unable to lock private keys for authentication. Abort.")


def key_store_exists(store_dir_path):
    """ Check a valid key store directory exists at the given location. """
    public_key_location = os.path.join(
        store_dir_path, UserFiles.get_certificate_name())
    private_key_location = os.path.join(
        store_dir_path, UserFiles.get_certificate_name(private=True))
    return (os.path.exists(public_key_location) and
            os.path.exists(private_key_location))


def lockdown_private_keys(private_key_file_path):
    """ Change private key file permissions to lock from other users. """
    # This means that the owner can read & write, but others (including group)
    # cannot do anything, to the file, i.e. '-rw-------.' file permissions.
    if not os.path.exists(private_key_file_path):
        raise FileNotFoundError(
            "Private key not found at location '%s'." % private_key_file_path)
    os.chmod(private_key_file_path, stat.S_IRUSR | stat.S_IWUSR)


def decode_(message):
    """ Decode a message from a string to JSON, with an added 'user' field. """
    msg = json.loads(message)
    # if able to decode assume this is the user
    msg['user'] = getpass.getuser()
    return msg


def encode_(message):
    """ Encode a message from JSON format to a string. """
    return json.dumps(message)
