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

from typing import Any, Dict, Optional, Tuple, Type
import pytest
import logging
from unittest.mock import Mock
from tempfile import NamedTemporaryFile

from cylc.flow import CYLC_LOG
from cylc.flow.config import SuiteConfig
from cylc.flow.cycling import iso8601, loader
from cylc.flow.exceptions import SuiteConfigError
from cylc.flow.suite_files import SuiteFiles
from cylc.flow.wallclock import get_utc_mode, set_utc_mode

Fixture = Any


def get_test_inheritance_quotes():
    """Provide test data for test_family_inheritance_and_quotes."""
    return [
        # first case, second family name surrounded by double quotes
        b'''
[task parameters]
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
[task parameters]
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
[task parameters]
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


class TestSuiteConfig:
    """Test class for the Cylc SuiteConfig object."""

    def test_xfunction_imports(self, mock_glbl_cfg, tmp_path):
        """Test for a suite configuration with valid xtriggers"""
        mock_glbl_cfg(
            'cylc.flow.platforms.glbl_cfg',
            '''
            [platforms]
                [[localhost]]
                    hosts = localhost
            '''
        )
        python_dir = tmp_path / "lib" / "python"
        python_dir.mkdir(parents=True)
        name_a_tree_file = python_dir / "name_a_tree.py"
        # NB: we are not returning a lambda, instead we have a scalar
        name_a_tree_file.write_text("""name_a_tree = lambda: 'jacaranda'""")
        flow_file = tmp_path / SuiteFiles.FLOW_FILE
        flow_config = """
        [scheduling]
            initial cycle point = 2018-01-01
            [[xtriggers]]
                tree = name_a_tree()
            [[graph]]
                R1 = '@tree => qux'
        """
        flow_file.write_text(flow_config)
        suite_config = SuiteConfig(suite="name_a_tree", fpath=flow_file,
                                   options=Mock(spec=[]))
        assert 'tree' in suite_config.xtrigger_mgr.functx_map

    def test_xfunction_import_error(self, mock_glbl_cfg, tmp_path):
        """Test for error when a xtrigger function cannot be imported."""
        mock_glbl_cfg(
            'cylc.flow.platforms.glbl_cfg',
            '''
            [platforms]
                [[localhost]]
                    hosts = localhost
            '''
        )
        python_dir = tmp_path / "lib" / "python"
        python_dir.mkdir(parents=True)
        caiman_file = python_dir / "caiman.py"
        # NB: we are not returning a lambda, instead we have a scalar
        caiman_file.write_text("""caiman = lambda: True""")
        flow_file = tmp_path / SuiteFiles.FLOW_FILE
        flow_config = """
        [scheduling]
            initial cycle point = 2018-01-01
            [[xtriggers]]
                oopsie = piranha()
            [[graph]]
                R1 = '@oopsie => qux'
        """
        flow_file.write_text(flow_config)
        with pytest.raises(ImportError) as excinfo:
            SuiteConfig(suite="caiman_suite", fpath=flow_file,
                        options=Mock(spec=[]))
        assert "not found" in str(excinfo.value)

    def test_xfunction_attribute_error(self, mock_glbl_cfg, tmp_path):
        """Test for error when a xtrigger function cannot be imported."""
        mock_glbl_cfg(
            'cylc.flow.platforms.glbl_cfg',
            '''
            [platforms]
                [[localhost]]
                    hosts = localhost
            '''
        )
        python_dir = tmp_path / "lib" / "python"
        python_dir.mkdir(parents=True)
        capybara_file = python_dir / "capybara.py"
        # NB: we are not returning a lambda, instead we have a scalar
        capybara_file.write_text("""toucan = lambda: True""")
        flow_file = tmp_path / SuiteFiles.FLOW_FILE
        flow_config = """
        [scheduling]
            initial cycle point = 2018-01-01
            [[xtriggers]]
                oopsie = capybara()
            [[graph]]
                R1 = '@oopsie => qux'
        """
        flow_file.write_text(flow_config)
        with pytest.raises(AttributeError) as excinfo:
            SuiteConfig(suite="capybara_suite", fpath=flow_file,
                        options=Mock(spec=[]))
        assert "not found" in str(excinfo.value)

    def test_xfunction_not_callable(self, mock_glbl_cfg, tmp_path):
        """Test for error when a xtrigger function is not callable."""
        mock_glbl_cfg(
            'cylc.flow.platforms.glbl_cfg',
            '''
            [platforms]
                [[localhost]]
                    hosts = localhost
            '''
        )
        python_dir = tmp_path / "lib" / "python"
        python_dir.mkdir(parents=True)
        not_callable_file = python_dir / "not_callable.py"
        # NB: we are not returning a lambda, instead we have a scalar
        not_callable_file.write_text("""not_callable = 42""")
        flow_file = tmp_path / SuiteFiles.FLOW_FILE
        flow_config = """
        [scheduling]
            initial cycle point = 2018-01-01
            [[xtriggers]]
                oopsie = not_callable()
            [[graph]]
                R1 = '@oopsie => qux'
        """
        flow_file.write_text(flow_config)
        with pytest.raises(ValueError) as excinfo:
            SuiteConfig(suite="suite_with_not_callable", fpath=flow_file,
                        options=Mock(spec=[]))
        assert "callable" in str(excinfo.value)

    def test_family_inheritance_and_quotes(self, mock_glbl_cfg):
        """Test that inheritance does not ignore items, if not all quoted.

        For example:

            inherit = 'MAINFAM<major, minor>', SOMEFAM
            inherit = 'BIGFAM', SOMEFAM

        See bug #2700 for more/
        """
        mock_glbl_cfg(
            'cylc.flow.platforms.glbl_cfg',
            '''
            [platforms]
                [[localhost]]
                    hosts = localhost
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
                    template_vars=template_vars,
                    options=Mock(spec=[]))
                assert 'goodbye_0_major1_minor10' in \
                       (config.runtime['descendants']
                        ['MAINFAM_major1_minor10'])
                assert 'goodbye_0_major1_minor10' in \
                       config.runtime['descendants']['SOMEFAM']


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


@pytest.mark.parametrize(
    'scheduling_cfg, expected_icp, expected_opt_icp, expected_err',
    [
        (  # Lack of icp
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': None,
                'initial cycle point constraints': []
            },
            None,
            None,
            (SuiteConfigError, "requires an initial cycle point")
        ),
        (  # Default icp for integer cycling mode
            {
                'cycling mode': loader.INTEGER_CYCLING_TYPE,
                'initial cycle point': None,
                'initial cycle point constraints': []
            },
            '1',
            None,
            None
        ),
        (  # "now"
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': 'now',
                'initial cycle point constraints': []
            },
            '20050102T0615Z',
            '20050102T0615Z',
            None
        ),
        (  # Constraints
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2013',
                'initial cycle point constraints': ['T00', 'T12']
            },
            '20130101T0000Z',
            None,
            None
        ),
        (  # Violated constraints
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2021-01-20',
                'initial cycle point constraints': ['--01-19', '--01-21']
            },
            None,
            None,
            (SuiteConfigError, "does not meet the constraints")
        ),
    ]
)
def test_process_icp(
        scheduling_cfg: Dict[str, Any], expected_icp: Optional[str],
        expected_opt_icp: Optional[str],
        expected_err: Optional[Tuple[Type[Exception], str]],
        monkeypatch: Fixture, cycling_mode: Fixture):
    """Test SuiteConfig.process_initial_cycle_point().

    "now" is assumed to be 2005-01-02T06:15Z

    Params:
        scheduling_cfg: 'scheduling' section of workflow config.
        expected_icp: The expected icp value that gets set.
        expected_opt_icp: The expected value of options.icp that gets set
            (this gets stored in the workflow DB).
        expected_err: Exception class expected to be raised plus the message.
    """
    int_cycling_mode = True
    if scheduling_cfg['cycling mode'] == loader.ISO8601_CYCLING_TYPE:
        int_cycling_mode = False
        iso8601.init()
    cycling_mode(integer=int_cycling_mode)
    mocked_config = Mock()
    mocked_config.cfg = {
        'scheduling': scheduling_cfg
    }
    mocked_config.options.icp = None
    monkeypatch.setattr('cylc.flow.config.get_current_time_string',
                        lambda: '20050102T0615Z')

    if expected_err:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            SuiteConfig.process_initial_cycle_point(mocked_config)
        assert msg in str(exc.value)
    else:
        SuiteConfig.process_initial_cycle_point(mocked_config)
        assert mocked_config.cfg[
            'scheduling']['initial cycle point'] == expected_icp
        assert str(mocked_config.initial_point) == expected_icp
        opt_icp = mocked_config.options.icp
        if opt_icp is not None:
            opt_icp = str(loader.get_point(opt_icp).standardise())
        assert opt_icp == expected_opt_icp


@pytest.mark.parametrize(
    'startcp, expected',
    [('2021-01-20T17Z', '20210120T1700Z'),
     ('now', '20050102T0615Z'),
     (None, '18990501T0000Z')]
)
def test_process_startcp(startcp: Optional[str], expected: str,
                         monkeypatch: Fixture, cycling_mode: Fixture):
    """Test SuiteConfig.process_start_cycle_point().

    An icp of 1899-05-01T00Z is assumed, and "now" is assumed to be
    2005-01-02T06:15Z

    Params:
        startcp: The start cycle point given by cli option.
        expected: The expected startcp value that gets set.
    """
    iso8601.init()
    cycling_mode(integer=False)
    mocked_config = Mock(initial_point='18990501T0000Z')
    mocked_config.options.startcp = startcp
    monkeypatch.setattr('cylc.flow.config.get_current_time_string',
                        lambda: '20050102T0615Z')

    SuiteConfig.process_start_cycle_point(mocked_config)
    assert str(mocked_config.start_point) == expected


@pytest.mark.parametrize(
    'scheduling_cfg, options_fcp, expected_fcp, expected_err',
    [
        pytest.param(
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2021',
                'final cycle point': None,
                'final cycle point constraints': []
            },
            None,
            None,
            None,
            id="No fcp"
        ),
        pytest.param(
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2016',
                'final cycle point': '2021',
                'final cycle point constraints': []
            },
            None,
            '20210101T0000Z',
            None,
            id="fcp in cfg"
        ),
        pytest.param(
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2016',
                'final cycle point': '2021',
                'final cycle point constraints': []
            },
            '2019',
            '20190101T0000Z',
            None,
            id="Overriden by cli option"
        ),
        pytest.param(
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2017-02-11',
                'final cycle point': '+P4D',
                'final cycle point constraints': []
            },
            None,
            '20170215T0000Z',
            None,
            id="Relative fcp"
        ),
        pytest.param(
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2017-02-11',
                'final cycle point': '---04',
                'final cycle point constraints': []
            },
            None,
            '20170215T0000Z',
            None,
            id="Relative truncated fcp", marks=pytest.mark.xfail
            # https://github.com/metomi/isodatetime/issues/80
        ),
        pytest.param(
            {
                'cycling mode': loader.INTEGER_CYCLING_TYPE,
                'initial cycle point': '1',
                'final cycle point': '4',
                'final cycle point constraints': []
            },
            None,
            '4',
            None,
            id="Integer cycling"
        ),
        pytest.param(
            {
                'cycling mode': loader.INTEGER_CYCLING_TYPE,
                'initial cycle point': '1',
                'final cycle point': '+P2',
                'final cycle point constraints': []
            },
            None,
            '3',
            None,
            id="Relative fcp, integer cycling"
        ),
        pytest.param(
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2013',
                'final cycle point': '2009',
                'final cycle point constraints': []
            },
            None,
            None,
            (SuiteConfigError,
             "initial cycle point:20130101T0000Z is after the "
             "final cycle point"),
            id="fcp before icp"
        ),
        pytest.param(
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2013',
                'final cycle point': '-PT1S',
                'final cycle point constraints': []
            },
            None,
            None,
            (SuiteConfigError,
             "initial cycle point:20130101T0000Z is after the "
             "final cycle point"),
            id="Negative relative fcp"
        ),
        pytest.param(
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2013',
                'final cycle point': '2021',
                'final cycle point constraints': ['T00', 'T12']
            },
            None,
            '20210101T0000Z',
            None,
            id="Constraints"
        ),
        pytest.param(
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2013',
                'final cycle point': '2021-01-19',
                'final cycle point constraints': ['--01-19', '--01-21']
            },
            '2021-01-20',
            None,
            (SuiteConfigError, "does not meet the constraints"),
            id="Violated constraints"
        ),
        pytest.param(
            {
                'cycling mode': loader.ISO8601_CYCLING_TYPE,
                'initial cycle point': '2013',
                'final cycle point': '2021',
                'final cycle point constraints': []
            },
            'ignore',
            '20210101T0000Z',
            None,
            id="--fcp=ignore"
        ),
    ]
)
def test_process_fcp(scheduling_cfg: dict, options_fcp: Optional[str],
                     expected_fcp: Optional[str],
                     expected_err: Optional[Tuple[Type[Exception], str]],
                     cycling_mode: Fixture):
    """Test SuiteConfig.process_final_cycle_point().

    Params:
        scheduling_cfg: 'scheduling' section of workflow config.
        options_fcp: The fcp set by cli option.
        expected_fcp: The expected fcp value that gets set.
        expected_err: Exception class expected to be raised plus the message.
    """
    if scheduling_cfg['cycling mode'] == loader.ISO8601_CYCLING_TYPE:
        iso8601.init()
        cycling_mode(integer=False)
    else:
        cycling_mode(integer=True)
    mocked_config = Mock(cycling_type=scheduling_cfg['cycling mode'])
    mocked_config.cfg = {
        'scheduling': scheduling_cfg
    }
    mocked_config.initial_point = loader.get_point(
        scheduling_cfg['initial cycle point']).standardise()
    mocked_config.final_point = None
    mocked_config.options.fcp = options_fcp

    if expected_err:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            SuiteConfig.process_final_cycle_point(mocked_config)
        assert msg in str(exc.value)
    else:
        SuiteConfig.process_final_cycle_point(mocked_config)
        assert mocked_config.cfg[
            'scheduling']['final cycle point'] == expected_fcp
        assert str(mocked_config.final_point) == str(expected_fcp)


def test_utc_mode(caplog, mock_glbl_cfg):
    """Test that UTC mode is handled correctly."""
    caplog.set_level(logging.WARNING, CYLC_LOG)

    def _test(utc_mode, expected, expected_warnings=0):
        mock_glbl_cfg(
            'cylc.flow.config.glbl_cfg',
            f'''
            [scheduler]
                UTC mode = {utc_mode['glbl']}
            '''
        )
        mock_config = Mock()
        mock_config.cfg = {
            'scheduler': {
                'UTC mode': utc_mode['suite']
            }
        }
        mock_config.options.utc_mode = utc_mode['stored']
        SuiteConfig.process_utc_mode(mock_config)
        assert mock_config.cfg['scheduler']['UTC mode'] is expected
        assert get_utc_mode() is expected
        assert len(caplog.record_tuples) == expected_warnings
        caplog.clear()

    tests = [
        {
            'utc_mode': {'glbl': True, 'suite': None, 'stored': None},
            'expected': True
        },
        {
            'utc_mode': {'glbl': True, 'suite': False, 'stored': None},
            'expected': False
        },
        {
            # On restart
            'utc_mode': {'glbl': False, 'suite': None, 'stored': True},
            'expected': True
        },
        {
            # Changed config value between restarts
            'utc_mode': {'glbl': False, 'suite': False, 'stored': True},
            'expected': True,
            'expected_warnings': 1
        }
    ]
    for case in tests:
        _test(**case)


def test_cycle_point_tz(caplog, monkeypatch):
    """Test that `[scheduler]cycle point time zone` is handled correctly."""
    caplog.set_level(logging.WARNING, CYLC_LOG)

    local_tz = '-0230'
    monkeypatch.setattr(
        'cylc.flow.config.get_local_time_zone_format',
        lambda: local_tz
    )

    def _test(cp_tz, utc_mode, expected, expected_warnings=0):
        set_utc_mode(utc_mode)
        mock_config = Mock()
        mock_config.cfg = {
            'scheduler': {
                'cycle point time zone': cp_tz['suite']
            }
        }
        mock_config.options.cycle_point_tz = cp_tz['stored']
        SuiteConfig.process_cycle_point_tz(mock_config)
        assert mock_config.cfg['scheduler'][
            'cycle point time zone'] == expected
        assert len(caplog.record_tuples) == expected_warnings
        caplog.clear()

    tests = [
        {
            'cp_tz': {'suite': None, 'stored': None},
            'utc_mode': True,
            'expected': 'Z'
        },
        {
            'cp_tz': {'suite': None, 'stored': None},
            'utc_mode': False,
            'expected': local_tz
        },
        {
            'cp_tz': {'suite': '+0530', 'stored': None},
            'utc_mode': True,
            'expected': '+0530'
        },
        {
            # On restart
            'cp_tz': {'suite': None, 'stored': '+0530'},
            'utc_mode': True,
            'expected': '+0530'
        },
        {
            # Changed config value between restarts
            'cp_tz': {'suite': '+0530', 'stored': '-0030'},
            'utc_mode': True,
            'expected': '-0030',
            'expected_warnings': 1
        },
        {
            'cp_tz': {'suite': 'Z', 'stored': 'Z'},
            'utc_mode': False,
            'expected': 'Z'
        }
    ]
    for case in tests:
        _test(**case)


def test_rsync_includes_will_not_accept_sub_directories(tmp_path):

    flow_cylc_content = """
    [scheduling]
        initial cycle point = 2020-01-01
        [[dependencies]]
            graph = "blah => deeblah"
    [scheduler]
        install = dir/, dir2/subdir2/, file1, file2
    """
    flow_cylc = tmp_path.joinpath(SuiteFiles.FLOW_FILE)
    flow_cylc.write_text(flow_cylc_content)

    with pytest.raises(SuiteConfigError) as exc:
        SuiteConfig(suite="rsynctest", fpath=flow_cylc, options=Mock(spec=[]))
    assert "Directories can only be from the top level" in str(exc.value)


def test_valid_rsync_includes_returns_correct_list(tmp_path):
    """Test that the rsync includes in the correct """

    flow_cylc_content = """
    [scheduling]
        initial cycle point = 2020-01-01
        [[dependencies]]
            graph = "blah => deeblah"
    [scheduler]
        install = dir/, dir2/, file1, file2
    """
    flow_cylc = tmp_path.joinpath(SuiteFiles.FLOW_FILE)
    flow_cylc.write_text(flow_cylc_content)

    config = SuiteConfig(suite="rsynctest", fpath=flow_cylc,
                         options=Mock(spec=[]))

    rsync_includes = SuiteConfig.get_validated_rsync_includes(config)
    assert rsync_includes == ['dir/', 'dir2/', 'file1', 'file2']


@pytest.mark.parametrize(
    'cfg_scheduling, valid',
    [
        ({'cycling mode': 'integer', 'runahead limit': 'P14'}, True),
        ({'cycling mode': 'gregorian', 'runahead limit': 'P14'}, True),
        ({'cycling mode': 'gregorian', 'runahead limit': 'PT12H'}, True),
        ({'cycling mode': 'gregorian', 'runahead limit': 'P7D'}, True),
        ({'cycling mode': 'gregorian', 'runahead limit': 'P2W'}, True),
        ({'cycling mode': 'gregorian', 'runahead limit': '4'}, True),

        ({'cycling mode': 'integer', 'runahead limit': 'PT12H'}, False),
        ({'cycling mode': 'integer', 'runahead limit': 'P7D'}, False),
        ({'cycling mode': 'integer', 'runahead limit': '4'}, False),
        ({'cycling mode': 'gregorian', 'runahead limit': ''}, False),
        ({'cycling mode': 'gregorian', 'runahead limit': 'asdf'}, False)
    ]
)
def test_process_runahead_limit(cfg_scheduling, valid, cycling_mode):
    is_integer_mode = cfg_scheduling['cycling mode'] == 'integer'
    mock_config = Mock()
    mock_config.cycling_type = cycling_mode(integer=is_integer_mode)
    mock_config.cfg = {'scheduling': cfg_scheduling}
    if valid:
        SuiteConfig.process_runahead_limit(mock_config)
    else:
        with pytest.raises(SuiteConfigError) as exc:
            SuiteConfig.process_runahead_limit(mock_config)
        assert "bad runahead limit" in str(exc.value).lower()


@pytest.mark.parametrize(
    'opt', [None, 'check_circular', 'strict']
)
def test_check_circular(opt, monkeypatch, caplog, tmp_path):
    """Test SuiteConfig._check_circular()."""
    # ----- Setup -----
    caplog.set_level(logging.WARNING, CYLC_LOG)

    options = Mock(spec=[], is_validate=True)
    if opt:
        setattr(options, opt, True)

    flow_config = """
    [scheduling]
        cycling mode = integer
        [[graph]]
            R1 = "a => b => c => d => e => a"
    [runtime]
        [[a, b, c, d, e]]
            script = True
    """
    flow_file = tmp_path.joinpath(SuiteFiles.FLOW_FILE)
    flow_file.write_text(flow_config)

    def SuiteConfig__assert_err_raised():
        with pytest.raises(SuiteConfigError) as exc:
            SuiteConfig(suite='circular', fpath=flow_file, options=options)
        assert "circular edges detected" in str(exc.value)

    # ----- The actual test -----
    SuiteConfig__assert_err_raised()
    # Now artificially lower the limit and re-test:
    monkeypatch.setattr('cylc.flow.config.SuiteConfig.CHECK_CIRCULAR_LIMIT', 4)
    if opt != 'check_circular':
        # Will no longer raise
        SuiteConfig(suite='circular', fpath=flow_file, options=options)
        msg = "will not check graph for circular dependencies"
        assert msg in caplog.text
    else:
        SuiteConfig__assert_err_raised()
