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
import pytest
from unittest.mock import Mock
from tempfile import TemporaryDirectory, NamedTemporaryFile
from pathlib import Path

from cylc.flow.config import SuiteConfig
from cylc.flow.cycling import loader
from cylc.flow.exceptions import SuiteConfigError
from cylc.flow.tests.conftest import mock_glbl_cfg


def get_test_inheritance_quotes():
    """Provide test data for test_family_inheritance_and_quotes."""
    return [
        # first case, second family name surrounded by double quotes
        b'''
[cylc]
    [[parameters]]
        major = 1..5
        minor = 10..20
[scheduling]
    [[graph]]
        R1 = """hello => MAINFAM<major, minor>
                hello => SOMEFAM
        """
[runtime]
    [[root]]
        script = true
    [[MAINFAM<major, minor>]]
    [[SOMEFAM]]
    [[ goodbye_0<major, minor> ]]
        inherit = 'MAINFAM<major, minor>', "SOMEFAM"
        ''',
        # second case, second family surrounded by single quotes
        b'''
[cylc]
    [[parameters]]
        major = 1..5
        minor = 10..20
[scheduling]
    [[graph]]
        R1 = """hello => MAINFAM<major, minor>
                hello => SOMEFAM
        """
[runtime]
    [[root]]
        script = true
    [[MAINFAM<major, minor>]]
    [[SOMEFAM]]
    [[ goodbye_0<major, minor> ]]
        inherit = 'MAINFAM<major, minor>', 'SOMEFAM'
        ''',
        # third case, second family name without quotes
        b'''
[cylc]
    [[parameters]]
        major = 1..5
        minor = 10..20
[scheduling]
    [[graph]]
        R1 = """hello => MAINFAM<major, minor>
                hello => SOMEFAM
        """
[runtime]
    [[root]]
        script = true
    [[MAINFAM<major, minor>]]
    [[SOMEFAM]]
    [[ goodbye_0<major, minor> ]]
        inherit = 'MAINFAM<major, minor>', SOMEFAM
        '''
    ]


class TestSuiteConfig(object):
    """Test class for the Cylc SuiteConfig object."""

    def test_xfunction_imports(self, mock_glbl_cfg):
        """Test for a suite configuration with valid xtriggers"""
        mock_glbl_cfg(
            'cylc.flow.platform_lookup.glbl_cfg',
            '''
            [job platforms]
                [[localhost]]
                    remote hosts = localhost
            '''
        )
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
        [[graph]]
            R1 = '@tree => qux'
                """)
                f.flush()
                suite_config = SuiteConfig(suite="name_a_tree", fpath=f.name)
                config = suite_config
                assert 'tree' in config.xtrigger_mgr.functx_map

    def test_xfunction_import_error(self, mock_glbl_cfg):
        """Test for error when a xtrigger function cannot be imported."""
        mock_glbl_cfg(
            'cylc.flow.platform_lookup.glbl_cfg',
            '''
            [job platforms]
                [[localhost]]
                    remote hosts = localhost
            '''
        )
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
        [[graph]]
            R1 = '@oopsie => qux'
                """)
                f.flush()
                with pytest.raises(ImportError) as excinfo:
                    SuiteConfig(suite="caiman_suite", fpath=f.name)
                assert "not found" in str(excinfo.value)

    def test_xfunction_attribute_error(self, mock_glbl_cfg):
        """Test for error when a xtrigger function cannot be imported."""
        mock_glbl_cfg(
            'cylc.flow.platform_lookup.glbl_cfg',
            '''
            [job platforms]
                [[localhost]]
                    remote hosts = localhost
            '''
        )
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
        [[graph]]
            R1 = '@oopsie => qux'
                """)
                f.flush()
                with pytest.raises(AttributeError) as excinfo:
                    SuiteConfig(suite="capybara_suite", fpath=f.name)
                assert "not found" in str(excinfo.value)

    def test_xfunction_not_callable(self, mock_glbl_cfg):
        """Test for error when a xtrigger function is not callable."""
        mock_glbl_cfg(
            'cylc.flow.platform_lookup.glbl_cfg',
            '''
            [job platforms]
                [[localhost]]
                    remote hosts = localhost
            '''
        )
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
        [[graph]]
            R1 = '@oopsie => qux'
                """)
                f.flush()
                with pytest.raises(ValueError) as excinfo:
                    SuiteConfig(suite="suite_with_not_callable", fpath=f.name)
                assert "callable" in str(excinfo.value)

    def test_family_inheritance_and_quotes(self, mock_glbl_cfg):
        """Test that inheritance does not ignore items, if not all quoted.

        For example:

            inherit = 'MAINFAM<major, minor>', SOMEFAM
            inherit = 'BIGFAM', SOMEFAM

        See bug #2700 for more/
        """
        mock_glbl_cfg(
            'cylc.flow.platform_lookup.glbl_cfg',
            '''
            [job platforms]
                [[localhost]]
                    remote hosts = localhost
            '''
        )
        template_vars = {}
        for content in get_test_inheritance_quotes():
            with NamedTemporaryFile() as tf:
                tf.write(content)
                tf.flush()
                config = SuiteConfig(
                    'test',
                    tf.name,
                    template_vars=template_vars)
                assert 'goodbye_0_major1_minor10' in \
                       (config.runtime['descendants']
                        ['MAINFAM_major1_minor10'])
                assert 'goodbye_0_major1_minor10' in \
                       config.runtime['descendants']['SOMEFAM']


def test_queue_config_repeated(caplog, tmp_path):
    """Test repeated assignment to same queue."""
    suiterc_content = """
[scheduling]
   [[queues]]
       [[[q1]]]
           members = A, B
       [[[q2]]]
           members = x
   [[dependencies]]
       graph = "x => y"
[runtime]
   [[A]]
   [[B]]
   [[x]]
       inherit = A, B
   [[y]]
    """
    suite_rc = tmp_path / "suite.rc"
    suite_rc.write_text(suiterc_content)
    config = SuiteConfig(suite="qtest", fpath=suite_rc.absolute())
    log = caplog.messages[0].split('\n')
    assert log[0] == "Queue configuration warnings:"
    assert log[1] == "+ q2: ignoring x (already assigned to a queue)"


def test_queue_config_not_used_not_defined(caplog, tmp_path):
    """Test task not defined vs no used, in queue config."""
    suiterc_content = """
[scheduling]
   [[queues]]
       [[[q1]]]
           members = foo
       [[[q2]]]
           members = bar
   [[dependencies]]
       # foo and bar not used
       graph = "beef => wellington"
[runtime]
   [[beef]]
   [[wellington]]
   [[foo]]
   # bar not even defined
    """
    suite_rc = tmp_path / "suite.rc"
    suite_rc.write_text(suiterc_content)
    config = SuiteConfig(suite="qtest", fpath=suite_rc.absolute())
    log = caplog.messages[0].split('\n')
    assert log[0] == "Queue configuration warnings:"
    assert log[1] == "+ q1: ignoring foo (task not used in the graph)"
    assert log[2] == "+ q2: ignoring bar (task not defined)"


def test_missing_initial_cycle_point():
    """Test that validation fails when the initial cycle point is
    missing for datetime cycling"""
    mocked_config = Mock()
    mocked_config.cfg = {
        'scheduling': {
            'cycling mode': None,
            'initial cycle point': None
        }
    }
    with pytest.raises(SuiteConfigError) as exc:
        SuiteConfig.process_initial_cycle_point(mocked_config)
    assert "This suite requires an initial cycle point" in str(exc.value)


def test_integer_cycling_default_initial_point(cycling_mode):
    """Test that the initial cycle point defaults to 1 for integer cycling
    mode."""
    cycling_mode()  # This is a pytest fixture; sets integer cycling mode
    mocked_config = Mock()
    mocked_config.cfg = {
        'scheduling': {
            'cycling mode': 'integer',
            'initial cycle point': None
        }
    }
    SuiteConfig.process_initial_cycle_point(mocked_config)
    assert mocked_config.cfg['scheduling']['initial cycle point'] == '1'
    assert mocked_config.initial_point == loader.get_point(1)
