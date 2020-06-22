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
"""Authentication key setup"""

from cylc.flow.suite_files import (
    KeyInfo,
    KeyOwner,
    KeyType,
    create_server_keys,
    get_suite_srv_dir,
    remove_keys_on_server)


def key_setup(reg, platform=None):

    """Clean any existing authentication keys and create new ones."""
    suite_srv_dir = get_suite_srv_dir(reg)
    keys = {
        "client_public_key": KeyInfo(
            KeyType.PUBLIC,
            KeyOwner.CLIENT,
            suite_srv_dir=suite_srv_dir, platform=platform),
        "client_private_key": KeyInfo(
            KeyType.PRIVATE,
            KeyOwner.CLIENT,
            suite_srv_dir=suite_srv_dir),
        "server_public_key": KeyInfo(
            KeyType.PUBLIC,
            KeyOwner.SERVER,
            suite_srv_dir=suite_srv_dir),
        "server_private_key": KeyInfo(
            KeyType.PRIVATE,
            KeyOwner.SERVER,
            suite_srv_dir=suite_srv_dir)
    }
    remove_keys_on_server(keys)
    create_server_keys(keys, suite_srv_dir)
