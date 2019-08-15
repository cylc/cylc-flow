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

from cylc.config import SuiteConfig, SuiteConfigError


class TestSuiteConfig(unittest.TestCase):
    """Test class for the Cylc SuiteConfig object."""

    def test_xfunction_imports(self):
        """Test for a suite configuration with valid xtriggers"""
        temp_dir = mkdtemp()
        python_dir = os.path.join(temp_dir, "lib", "python")
        if not os.path.exists(python_dir):
            os.makedirs(python_dir)
        name_a_tree_file = os.path.join(python_dir, "name_a_tree.py")
        with open(name_a_tree_file, mode="w") as f:
            # NB: we are not returning a lambda, instead we have a scalar
            f.write("""name_a_tree = lambda: 'jacaranda'""")
            f.flush()
        suite_rc = os.path.join(temp_dir, "suite.rc")
        with open(suite_rc, mode="w") as f:
            f.write("""
[scheduling]
    initial cycle point = 2018-01-01
    [[xtriggers]]
        tree = name_a_tree()
    [[dependencies]]
        [[[R1]]]
            graph = '@tree => qux'
            """)
            f.flush()
            suite_config = SuiteConfig(suite="name_a_tree", fpath=f.name)
            config = suite_config
            self.assertTrue('tree' in config.xtrigger_mgr.functx_map)
        shutil.rmtree(temp_dir)

    def test_xfunction_import_error(self):
        """Test for error when a xtrigger function cannot be imported."""
        temp_dir = mkdtemp()
        python_dir = os.path.join(temp_dir, "lib", "python")
        if not os.path.exists(python_dir):
            os.makedirs(python_dir)
        caiman_file = os.path.join(python_dir, "caiman.py")
        with open(caiman_file, mode="w") as f:
            # NB: we are not returning a lambda, instead we have a scalar
            f.write("""caiman = lambda: True""")
            f.flush()
        suite_rc = os.path.join(temp_dir, "suite.rc")
        with open(suite_rc, mode="w") as f:
            f.write("""
[scheduling]
    initial cycle point = 2018-01-01
    [[xtriggers]]
        oopsie = piranha()
    [[dependencies]]
        [[[R1]]]
            graph = '@oopsie => qux'
            """)
            f.flush()
            with self.assertRaises(ImportError) as ex:
                SuiteConfig(suite="caiman_suite", fpath=f.name)
                self.assertTrue("not found" in str(ex))
        shutil.rmtree(temp_dir)

    def test_xfunction_attribute_error(self):
        """Test for error when a xtrigger function cannot be imported."""
        temp_dir = mkdtemp()
        python_dir = os.path.join(temp_dir, "lib", "python")
        if not os.path.exists(python_dir):
            os.makedirs(python_dir)
        capybara_file = os.path.join(python_dir, "capybara.py")
        with open(capybara_file, mode="w") as f:
            # NB: we are not returning a lambda, instead we have a scalar
            f.write("""toucan = lambda: True""")
            f.flush()
        suite_rc = os.path.join(temp_dir, "suite.rc")
        with open(suite_rc, mode="w") as f:
            f.write("""
[scheduling]
    initial cycle point = 2018-01-01
    [[xtriggers]]
        oopsie = capybara()
    [[dependencies]]
        [[[R1]]]
            graph = '@oopsie => qux'
            """)
            f.flush()
            with self.assertRaises(AttributeError) as ex:
                SuiteConfig(suite="capybara_suite", fpath=f.name)
                self.assertTrue("not found" in str(ex))
        shutil.rmtree(temp_dir)

    def test_xfunction_not_callable(self):
        """Test for error when a xtrigger function is not callable."""
        temp_dir = mkdtemp()
        python_dir = os.path.join(temp_dir, "lib", "python")
        if not os.path.exists(python_dir):
            os.makedirs(python_dir)
        not_callable_file = os.path.join(python_dir, "not_callable.py")
        with open(not_callable_file, mode="w") as f:
            # NB: we are not returning a lambda, instead we have a scalar
            f.write("""not_callable = 42""")
            f.flush()
        suite_rc = os.path.join(temp_dir, "suite.rc")
        with open(suite_rc, mode="w") as f:
            f.write("""
[scheduling]
    initial cycle point = 2018-01-01
    [[xtriggers]]
        oopsie = not_callable()
    [[dependencies]]
        [[[R1]]]
            graph = '@oopsie => qux'
            """)
            f.flush()
            with self.assertRaises(ValueError) as ex:
                SuiteConfig(suite="suite_with_not_callable", fpath=f.name)
                self.assertTrue("callable" in str(ex))
        shutil.rmtree(temp_dir)


if __name__ == '__main__':
    unittest.main()
