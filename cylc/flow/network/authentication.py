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
import os
import shutil

import zmq.auth


# Names for directories (topmost holding the following two) to store auth keys:
STORE_DIR_NAME = ".curve"
PUBLIC_KEY_DIR_NAME = "public_key"  # dirname <root>/STORE_DIR_NAME/
PRIVATE_KEY_DIR_NAME = "private_key"  # dirname <root>/STORE_DIR_NAME/


def generate_key_store(store_parent_dir, keys_tag):
    """ Generate two sub-directories, each holding a file with a CURVE key. """
    # Define the directory structure to store the CURVE keys in
    store_dir = os.path.join(store_parent_dir, STORE_DIR_NAME)
    public_key_location = os.path.join(store_dir, PUBLIC_KEY_DIR_NAME)
    private_key_location = os.path.join(store_dir, PRIVATE_KEY_DIR_NAME)

    # Create, or wipe, that directory structure
    for directory in [store_dir, public_key_location, private_key_location]:
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.mkdir(directory)

    # Make a new public-private CURVE key pair
    private_key_file, public_key_file = zmq.auth.create_certificates(
        store_dir, keys_tag)

    # Move the pair of keys to the appropriate directories
    for key_file in os.listdir(store_dir):
        if key_file.endswith(".key"):
            shutil.move(os.path.join(store_dir, key_file),
                        os.path.join(public_key_location, '.'))
        elif key_file.endswith(".key_secret"):
            shutil.move(os.path.join(store_dir, key_file),
                        os.path.join(private_key_location, '.'))


def key_store_exists(store_dir_path):
    """ Check a valid key store directory exists at the given location. """
    public_key_location = os.path.join(store_dir_path, PUBLIC_KEY_DIR_NAME)
    private_key_location = os.path.join(store_dir_path, PRIVATE_KEY_DIR_NAME)
    return (os.path.exists(public_key_location) and
            os.path.exists(private_key_location))
