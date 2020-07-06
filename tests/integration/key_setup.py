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

"""Creates authentication keys for use in testing"""

from cylc.flow.suite_files import (
    create_server_keys,
    get_suite_srv_dir,
    KeyInfo,
    KeyOwner,
    KeyType,
    remove_keys_on_server)
from cylc.flow.task_remote_cmd import (
    remove_keys_on_platform, create_platform_keys)


def setup_keys(suite_name):
    suite_srv_dir = get_suite_srv_dir(suite_name)
    server_keys = {
        "client_public_key": KeyInfo(
            KeyType.PUBLIC,
            KeyOwner.CLIENT,
            suite_srv_dir=suite_srv_dir),
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
    remove_keys_on_server(server_keys)
    remove_keys_on_platform(suite_srv_dir)
    create_server_keys(server_keys, suite_srv_dir)
    create_platform_keys(suite_srv_dir)
