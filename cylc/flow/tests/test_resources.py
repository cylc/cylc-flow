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

import os
import unittest
import tempfile
import shutil

from cylc.flow.resources import (
    resource_names, list_resources, extract_resources)


class TestPkgResources(unittest.TestCase):

    def test_list_resources(self):
        """Test resources.list_resources."""
        self.assertEqual(list_resources(), resource_names)

    def test_extract_resources_one(self):
        """Test extraction of a specific resource.

        Just check that a file of the right name gets extracted, but not its
        content - which may change in the future.
        """
        tmpdir = tempfile.gettempdir()
        extract_resources(tmpdir, resources=['etc/job.sh'])
        extracted = os.path.join(tmpdir, 'etc', 'job.sh')
        self.assertTrue(os.path.isfile(extracted))
        shutil.rmtree(os.path.dirname(extracted), ignore_errors=True)

    def test_extract_resources_all(self):
        """Test extraction of all resources under 'etc'.

        Just check that file of the right names gets extracted, but not their
        content - which may change in the future.

        """
        tmpdir = tempfile.gettempdir()
        extract_resources(tmpdir, None)
        for resource in resource_names:
            extracted = os.path.join(tmpdir, resource)
            self.assertTrue(os.path.isfile(extracted))
        shutil.rmtree(os.path.join(tmpdir, 'etc'), ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
