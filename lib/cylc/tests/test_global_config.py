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

import os
import shutil
import unittest
from tempfile import mkdtemp

from cylc.cfgspec.globalcfg import GlobalConfig
from cylc.cfgvalidate import CylcConfigValidator


class TestGlobalConfig(unittest.TestCase):
    """Test class for the Cylc global config object."""

    def test_localhost_default_list_items(self):
        """List items shold default to localhost values, like non-list items.

        See GitHub 3508

        NOTE: still not working for batch system settings
        because globalcfg:transform() needs to distinguish empty dict from None
        and recurse into sub-sections to do the localhost defaulting:

        [[[batch systems]]]
          [[[[pbs]]]]
             execution time limit polling intervals = PT10S, PT30S

        """
        conf_dir = mkdtemp()
        os.environ["CYLC_CONF_PATH"] = conf_dir
        globalrc_file = os.path.join(conf_dir, "global.rc")

        items = {
            'copyable environment variables': 'FOO, BAR',
            'task event handler retry delays': 'PT99S, PT1H',
            'retrieve job logs retry delays': 'PT10S, PT30S, PT1M, PT3M',
            'submission polling intervals': 'PT10S, PT30S',
            'execution polling intervals': 'PT10S, PT30S'
        }

        globalrc_content = """
[hosts]
   [[localhost]]
"""
        for key, val in items.items():
            globalrc_content += "%s = %s\n" % (key, val)
        globalrc_content += """
   [[foo]]
      # (default to localhost!)"""

        # Write the global config file.
        with open(globalrc_file, mode="w") as f:
            f.write(globalrc_content)
            f.flush()

        # Parse the global config file and check values for host "foo" have
        # inherited localhost values.
        global_config = GlobalConfig.get_inst()
        validator = CylcConfigValidator()

        for key in items.keys():
            if key == 'copyable environment variables':
                coercer = validator.coerce_str_list
            else:
                coercer = validator.coerce_interval_list
            host_item = global_config.get_host_item(item=key, host='foo')
            self.assertTrue(host_item == coercer(items[key], []))

        shutil.rmtree(conf_dir)


if __name__ == '__main__':
    unittest.main()
