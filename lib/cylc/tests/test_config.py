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
import pytest
from tempfile import TemporaryDirectory
from pathlib import Path
from cylc.config import SuiteConfig, SuiteConfigError


class TestSuiteConfig(object):
    """Test class for the Cylc SuiteConfig object."""

    def test_xfunction_imports(self):
        """Test for a suite configuration with valid xtriggers"""
        with TemporaryDirectory() as temp_dir:
            python_dir = Path(os.path.join(temp_dir, "lib", "python"))
            python_dir.mkdir(parents=True)
            name_a_tree_file = python_dir / "name_a_tree.py"
            with name_a_tree_file.open(mode="w") as f:
                # NB: we are not returning a lambda, instead we have a scalar
                f.write("""name_a_tree = lambda: 'jacaranda'""")
                f.flush()
            suite_rc = Path(temp_dir, "suite.rc")
            with suite_rc.open(mode="w") as f:
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
                assert 'tree' in config.xtriggers['qux']

    def test_xfunction_import_error(self):
        """Test for error when a xtrigger function cannot be imported."""
        with TemporaryDirectory() as temp_dir:
            python_dir = Path(os.path.join(temp_dir, "lib", "python"))
            python_dir.mkdir(parents=True)
            caiman_file = python_dir / "caiman.py"
            with caiman_file.open(mode="w") as f:
                # NB: we are not returning a lambda, instead we have a scalar
                f.write("""caiman = lambda: True""")
                f.flush()
            suite_rc = Path(temp_dir, "suite.rc")
            with suite_rc.open(mode="w") as f:
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
                with pytest.raises(SuiteConfigError) as excinfo:
                    SuiteConfig(suite="caiman_suite", fpath=f.name)
                assert "not found" in str(excinfo.value)

    def test_xfunction_attribute_error(self):
        """Test for error when a xtrigger function cannot be imported."""
        with TemporaryDirectory() as temp_dir:
            python_dir = Path(os.path.join(temp_dir, "lib", "python"))
            python_dir.mkdir(parents=True)
            capybara_file = python_dir / "capybara.py"
            with capybara_file.open(mode="w") as f:
                # NB: we are not returning a lambda, instead we have a scalar
                f.write("""toucan = lambda: True""")
                f.flush()
            suite_rc = Path(temp_dir, "suite.rc")
            with suite_rc.open(mode="w") as f:
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
                with pytest.raises(SuiteConfigError) as excinfo:
                    SuiteConfig(suite="capybara_suite", fpath=f.name)
                assert "not found" in str(excinfo.value)

    def test_xfunction_not_callable(self):
        """Test for error when a xtrigger function is not callable."""
        with TemporaryDirectory() as temp_dir:
            python_dir = Path(os.path.join(temp_dir, "lib", "python"))
            python_dir.mkdir(parents=True)
            not_callable_file = python_dir / "not_callable.py"
            with not_callable_file.open(mode="w") as f:
                # NB: we are not returning a lambda, instead we have a scalar
                f.write("""not_callable = 42""")
                f.flush()
            suite_rc = Path(temp_dir, "suite.rc")
            with suite_rc.open(mode="w") as f:
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
                with pytest.raises(SuiteConfigError) as excinfo:
                    SuiteConfig(suite="suite_with_not_callable", fpath=f.name)
                assert "callable" in str(excinfo.value)
