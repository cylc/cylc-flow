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

import logging
import mock
import os
import pytest
import shutil
import unittest
from tempfile import mkdtemp

from cylc.config import SuiteConfig
from cylc.wallclock import get_utc_mode, set_utc_mode


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


@pytest.mark.parametrize(
    'utc_mode, expected, expected_warnings',
    [
        pytest.param(
            {'glbl': True, 'suite': None, 'stored': None},
            True,
            0,
            id="global: True"
        ),
        pytest.param(
            {'glbl': True, 'suite': False, 'stored': None},
            False,
            0,
            id="suite: False; global: True"
        ),
        pytest.param(
            {'glbl': False, 'suite': None, 'stored': True},
            True,
            0,
            id="Restart DB: True; global: False"
        ),
        pytest.param(
            {'glbl': False, 'suite': False, 'stored': True},
            True,
            1,
            id="Changed config value between restarts"
        )
    ]
)
def test_utc_mode(
    utc_mode, expected, expected_warnings,
    caplog, monkeypatch
):
    """Test that UTC mode is handled correctly."""
    # -- Setup --
    caplog.set_level(logging.WARNING, 'cylc')

    def mock_glbl_cfg_get(item):
        if item == ['cylc', 'UTC mode']:
            return utc_mode['glbl']
    mock_glbl_cfg = mock.Mock(return_value=mock.Mock(
        get=mock_glbl_cfg_get
    ))
    monkeypatch.setattr('cylc.config.glbl_cfg', mock_glbl_cfg)
    mock_config = mock.Mock(
        spec=SuiteConfig,
        cfg={
            'cylc': {
                'UTC mode': utc_mode['suite']
            }
        },
        options=mock.Mock(utc_mode=utc_mode['stored'])
    )
    # -- Test --
    SuiteConfig.process_utc_mode(mock_config)
    assert mock_config.cfg['cylc']['UTC mode'] is expected
    assert get_utc_mode() is expected
    assert len(caplog.record_tuples) == expected_warnings


@pytest.mark.parametrize(
    'cp_tz, utc_mode, expected, expected_warnings',
    [
        pytest.param(
            {'suite': None, 'stored': None},
            True,
            'Z',
            0,
            id="Z when UTC mode = True"
        ),
        pytest.param(
            {'suite': None, 'stored': None},
            False,
            '{local}',
            0,
            id="Local when UTC mode = False"
        ),
        pytest.param(
            {'suite': '+0530', 'stored': None},
            True,
            '+0530',
            0,
            id="Suite config tz precedes UTC mode"
        ),
        pytest.param(
            {'suite': 'Z', 'stored': 'Z'},
            False,
            'Z',
            0,
            id="Stored tz on restart"
        ),
        pytest.param(
            {'suite': None, 'stored': '+0530'},
            True,
            '+0530',
            0,
            id="Stored tz on restart precedes UTC mode"
        ),
        pytest.param(
            {'suite': '+0530', 'stored': '-0030'},
            True,
            '-0030',
            1,
            id="Changed config value between restarts"
        ),
    ]
)
def test_cycle_point_tz(
    cp_tz, utc_mode, expected, expected_warnings,
    caplog, monkeypatch
):
    """Test that `[cylc]cycle point time zone` is handled correctly."""
    # -- Setup --
    caplog.set_level(logging.WARNING, 'cylc')
    local_tz = '-0230'
    monkeypatch.setattr('cylc.config.get_local_time_zone_format',
                        lambda: local_tz)
    expected = expected.format(local=local_tz)
    set_utc_mode(utc_mode)
    mock_config = mock.Mock(
        spec=SuiteConfig,
        cfg={
            'cylc': {
                'cycle point time zone': cp_tz['suite']
            }
        },
        options=mock.Mock(cycle_point_tz=cp_tz['stored'])
    )
    # -- Test --
    SuiteConfig.process_cycle_point_tz(mock_config)
    assert mock_config.cfg['cylc']['cycle point time zone'] == expected
    assert len(caplog.record_tuples) == expected_warnings


if __name__ == '__main__':
    unittest.main()
