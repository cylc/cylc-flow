# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

from typing import Any, Callable, Dict, Optional, Tuple, Type
from pathlib import Path
import pytest
import logging
from unittest.mock import Mock

from cylc.flow import CYLC_LOG
from cylc.flow.config import WorkflowConfig
from cylc.flow.cycling import loader
from cylc.flow.cycling.loader import INTEGER_CYCLING_TYPE, ISO8601_CYCLING_TYPE
from cylc.flow.exceptions import WorkflowConfigError, PointParsingError
from cylc.flow.workflow_files import WorkflowFiles
from cylc.flow.wallclock import get_utc_mode, set_utc_mode
from cylc.flow.xtrigger_mgr import XtriggerManager

Fixture = Any


class TestWorkflowConfig:
    """Test class for the Cylc WorkflowConfig object."""

    def test_xfunction_imports(
            self, mock_glbl_cfg: Fixture, tmp_path: Path,
            xtrigger_mgr: XtriggerManager):
        """Test for a workflow configuration with valid xtriggers"""
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
        flow_file = tmp_path / WorkflowFiles.FLOW_FILE
        flow_config = """
        [scheduler]
            allow implicit tasks = True
        [scheduling]
            initial cycle point = 2018-01-01
            [[xtriggers]]
                tree = name_a_tree()
            [[graph]]
                R1 = '@tree => qux'
        """
        flow_file.write_text(flow_config)
        workflow_config = WorkflowConfig(
            workflow="name_a_tree", fpath=flow_file, options=Mock(spec=[]),
            xtrigger_mgr=xtrigger_mgr
        )
        assert 'tree' in workflow_config.xtrigger_mgr.functx_map

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
        flow_file = tmp_path / WorkflowFiles.FLOW_FILE
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
            WorkflowConfig(
                workflow="caiman_workflow",
                fpath=flow_file,
                options=Mock(spec=[])
            )
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
        flow_file = tmp_path / WorkflowFiles.FLOW_FILE
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
            WorkflowConfig(workflow="capybara_workflow", fpath=flow_file,
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
        flow_file = tmp_path / WorkflowFiles.FLOW_FILE
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
            WorkflowConfig(
                workflow="workflow_with_not_callable",
                fpath=flow_file,
                options=Mock(spec=[])
            )
        assert "callable" in str(excinfo.value)


@pytest.mark.parametrize(
    'fam_txt',
    [pytest.param('"SOMEFAM"', id="double quoted"),
     pytest.param('\'SOMEFAM\'', id="single quoted"),
     pytest.param('SOMEFAM', id="unquoted")]
)
def test_family_inheritance_and_quotes(
    fam_txt: str,
    mock_glbl_cfg: Callable, tmp_path: Path
) -> None:
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
    cfg = f'''
        [scheduler]
            allow implicit tasks = True
        [task parameters]
            major = 1..5
            minor = 10..20
        [scheduling]
            [[graph]]
                R1 = """hello => MAINFAM<major, minor>
                        hello => SOMEFAM"""
        [runtime]
            [[root]]
                script = true
            [[MAINFAM<major, minor>]]
            [[SOMEFAM]]
            [[ goodbye_0<major, minor> ]]
                inherit = 'MAINFAM<major, minor>', {fam_txt}
    '''
    file_path = tmp_path / 'thing.cylc'
    file_path.write_text(cfg)
    config = WorkflowConfig(
        'test',
        str(file_path),
        template_vars={},
        options=Mock(spec=[])
    )
    assert ('goodbye_0_major1_minor10' in
            config.runtime['descendants']['MAINFAM_major1_minor10'])
    assert ('goodbye_0_major1_minor10' in
            config.runtime['descendants']['SOMEFAM'])


@pytest.mark.parametrize(
    ('cycling_type', 'scheduling_cfg', 'expected_icp', 'expected_opt_icp',
     'expected_err'),
    [
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': None,
                'initial cycle point constraints': []
            },
            None,
            None,
            (WorkflowConfigError, "requires an initial cycle point"),
            id="Lack of icp"
        ),
        pytest.param(
            INTEGER_CYCLING_TYPE,
            {
                'initial cycle point': None,
                'initial cycle point constraints': []
            },
            '1',
            None,
            None,
            id="Default icp for integer cycling type"
        ),
        pytest.param(
            INTEGER_CYCLING_TYPE,
            {
                'initial cycle point': "now",
                'initial cycle point constraints': []
            },
            None,
            None,
            (PointParsingError, "invalid literal for int()"),
            id="Non-integer ICP for integer cycling type"
        ),
        pytest.param(
            INTEGER_CYCLING_TYPE,
            {
                'initial cycle point': "20500808T0000Z",
                'initial cycle point constraints': []
            },
            None,
            None,
            (PointParsingError, "invalid literal for int()"),
            id="More non-integer ICP for integer cycling type"
        ),
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': "1",
                'initial cycle point constraints': []
            },
            None,
            None,
            (PointParsingError, "Invalid ISO 8601 date representation"),
            id="Non-ISO8601 ICP for ISO8601 cycling type"
        ),
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': 'now',
                'initial cycle point constraints': []
            },
            '20050102T0615+0530',
            '20050102T0615+0530',
            None,
            id="ICP = now"
        ),
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': '2013',
                'initial cycle point constraints': ['T00', 'T12']
            },
            '20130101T0000+0530',
            None,
            None,
            id="Constraints"
        ),
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': '2021-01-20',
                'initial cycle point constraints': ['--01-19', '--01-21']
            },
            None,
            None,
            (WorkflowConfigError, "does not meet the constraints"),
            id="Violated constraints"
        ),
    ]
)
def test_process_icp(
    cycling_type: str,
    scheduling_cfg: Dict[str, Any],
    expected_icp: Optional[str],
    expected_opt_icp: Optional[str],
    expected_err: Optional[Tuple[Type[Exception], str]],
    monkeypatch: pytest.MonkeyPatch, set_cycling_type: Fixture
) -> None:
    """Test WorkflowConfig.process_initial_cycle_point().

    "now" is assumed to be 2005-01-02T06:15+0530

    Params:
        cycling_type: Workflow cycling type.
        scheduling_cfg: 'scheduling' section of workflow config.
        expected_icp: The expected icp value that gets set.
        expected_opt_icp: The expected value of options.icp that gets set
            (this gets stored in the workflow DB).
        expected_err: Exception class expected to be raised plus the message.
    """
    set_cycling_type(cycling_type, time_zone="+0530")
    mocked_config = Mock(cycling_type=cycling_type)
    mocked_config.cfg = {
        'scheduling': scheduling_cfg
    }
    mocked_config.options.icp = None
    monkeypatch.setattr('cylc.flow.config.get_current_time_string',
                        lambda: '20050102T0615+0530')

    if expected_err:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            WorkflowConfig.process_initial_cycle_point(mocked_config)
        assert msg in str(exc.value)
    else:
        WorkflowConfig.process_initial_cycle_point(mocked_config)
        assert mocked_config.cfg[
            'scheduling']['initial cycle point'] == expected_icp
        assert str(mocked_config.initial_point) == expected_icp
        opt_icp = mocked_config.options.icp
        if opt_icp is not None:
            opt_icp = str(loader.get_point(opt_icp).standardise())
        assert opt_icp == expected_opt_icp


@pytest.mark.parametrize(
    'startcp, starttask, expected, expected_err',
    [
        (
            '20210120T1700+0530',
            None,
            '20210120T1700+0530',
            None
        ),
        (
            'now',
            None,
            '20050102T0615+0530',
            None
        ),
        (
            None,
            None,
            '18990501T0000+0530',
            None
        ),
        (
            None,
            ['foo.20090802T0615+0530', 'bar.20090802T0515+0530'],
            '20090802T0515+0530',
            None
        ),
        (
            '20210120T1700+0530',
            ['foo.20090802T0615+0530'],
            None,
            (
                WorkflowConfigError,
                "--start-cycle-point and --start-task are mutually exclusive"
            ),
        )
    ]
)
def test_process_startcp(
    startcp: Optional[str],
    starttask: Optional[str],
    expected: str,
    expected_err: Optional[Tuple[Type[Exception], str]],
    monkeypatch: pytest.MonkeyPatch, set_cycling_type: Fixture
) -> None:
    """Test WorkflowConfig.process_start_cycle_point().

    An icp of 1899-05-01T00+0530 is assumed, and "now" is assumed to be
    2005-01-02T06:15+0530

    Params:
        startcp: The start cycle point given by cli option.
        expected: The expected startcp value that gets set.
        expected_err: Expected exception.
    """
    set_cycling_type(ISO8601_CYCLING_TYPE, time_zone="+0530")
    mocked_config = Mock(initial_point='18990501T0000+0530')
    mocked_config.options.startcp = startcp
    mocked_config.options.starttask = starttask
    monkeypatch.setattr('cylc.flow.config.get_current_time_string',
                        lambda: '20050102T0615+0530')
    if expected_err is not None:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            WorkflowConfig.process_start_cycle_point(mocked_config)
        assert msg in str(exc.value)
    else:
        WorkflowConfig.process_start_cycle_point(mocked_config)
        assert str(mocked_config.start_point) == expected


@pytest.mark.parametrize(
    'cycling_type, scheduling_cfg, options_fcp, expected_fcp, expected_err',
    [
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
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
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': '2016',
                'final cycle point': '2021',
                'final cycle point constraints': []
            },
            None,
            '20210101T0000+0530',
            None,
            id="fcp in cfg"
        ),
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': '2016',
                'final cycle point': '2021',
                'final cycle point constraints': []
            },
            '2019',
            '20190101T0000+0530',
            None,
            id="Overriden by cli option"
        ),
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': '2017-02-11',
                'final cycle point': '+P4D',
                'final cycle point constraints': []
            },
            None,
            '20170215T0000+0530',
            None,
            id="Relative fcp"
        ),
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': '2017-02-11',
                'final cycle point': '---04',
                'final cycle point constraints': []
            },
            None,
            '20170215T0000+0530',
            None,
            id="Relative truncated fcp", marks=pytest.mark.xfail
            # https://github.com/metomi/isodatetime/issues/80
        ),
        pytest.param(
            INTEGER_CYCLING_TYPE,
            {
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
            INTEGER_CYCLING_TYPE,
            {
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
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': '2013',
                'final cycle point': '2009',
                'final cycle point constraints': []
            },
            None,
            None,
            (WorkflowConfigError,
             "initial cycle point:20130101T0000+0530 is after the "
             "final cycle point"),
            id="fcp before icp"
        ),
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': '2013',
                'final cycle point': '-PT1S',
                'final cycle point constraints': []
            },
            None,
            None,
            (WorkflowConfigError,
             "initial cycle point:20130101T0000+0530 is after the "
             "final cycle point"),
            id="Negative relative fcp"
        ),
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': '2013',
                'final cycle point': '2021',
                'final cycle point constraints': ['T00', 'T12']
            },
            None,
            '20210101T0000+0530',
            None,
            id="Constraints"
        ),
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': '2013',
                'final cycle point': '2021-01-19',
                'final cycle point constraints': ['--01-19', '--01-21']
            },
            '2021-01-20',
            None,
            (WorkflowConfigError, "does not meet the constraints"),
            id="Violated constraints"
        ),
        pytest.param(
            ISO8601_CYCLING_TYPE,
            {
                'initial cycle point': '2013',
                'final cycle point': '2021',
                'final cycle point constraints': []
            },
            'ignore',
            '20210101T0000+0530',
            None,
            id="--fcp=ignore"
        ),
    ]
)
def test_process_fcp(
    cycling_type: str,
    scheduling_cfg: dict,
    options_fcp: Optional[str],
    expected_fcp: Optional[str],
    expected_err: Optional[Tuple[Type[Exception], str]],
    set_cycling_type: Fixture
) -> None:
    """Test WorkflowConfig.process_final_cycle_point().

    Params:
        cycling_type: Workflow cycling type.
        scheduling_cfg: 'scheduling' section of workflow config.
        options_fcp: The fcp set by cli option.
        expected_fcp: The expected fcp value that gets set.
        expected_err: Exception class expected to be raised plus the message.
    """
    set_cycling_type(cycling_type, time_zone='+0530')
    mocked_config = Mock(cycling_type=cycling_type)
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
            WorkflowConfig.process_final_cycle_point(mocked_config)
        assert msg in str(exc.value)
    else:
        WorkflowConfig.process_final_cycle_point(mocked_config)
        assert mocked_config.cfg[
            'scheduling']['final cycle point'] == expected_fcp
        assert str(mocked_config.final_point) == str(expected_fcp)


@pytest.mark.parametrize(
    'scheduling_cfg, scheduling_expected, expected_err',
    [
        pytest.param(
            {
                'graph': {}
            },
            None,
            (WorkflowConfigError, "No workflow dependency graph defined"),
            id="Empty graph"
        ),
        pytest.param(
            {
                'graph': {'R1': 'foo'}
            },
            {
                'cycling mode': 'integer',
                'initial cycle point': '1',
                'final cycle point': '1',
                'graph': {'R1': 'foo'}
            },
            None,
            id="Pure acyclic graph"
        ),
        pytest.param(
            {
                'cycling mode': "",
                'graph': {'R1': 'foo'}
            },
            {
                'cycling mode': "",
                'graph': {'R1': 'foo'}
            },
            None,
            id="Pure acyclic graph but datetime cycling"
        ),
        pytest.param(
            {
                'graph': {'R1': 'foo', 'R2': 'bar'}
            },
            {
                'graph': {'R1': 'foo', 'R2': 'bar'}
            },
            None,
            id="Acyclic graph with >1 recurrence"
        ),
    ]
)
def test_prelim_process_graph(
        scheduling_cfg: Dict[str, Any],
        scheduling_expected: Optional[Dict[str, Any]],
        expected_err: Optional[Tuple[Type[Exception], str]]):
    """Test WorkflowConfig.prelim_process_graph().

    Params:
        scheduling_cfg: 'scheduling' section of workflow config.
        scheduling_expected: The expected scheduling section after preliminary
            processing.
        expected_err: Exception class expected to be raised plus the message.
    """
    mock_config = Mock(cfg={
        'scheduling': scheduling_cfg
    })

    if expected_err:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            WorkflowConfig.prelim_process_graph(mock_config)
        assert msg in str(exc.value)
    else:
        WorkflowConfig.prelim_process_graph(mock_config)
        assert mock_config.cfg['scheduling'] == scheduling_expected


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
                'UTC mode': utc_mode['workflow']
            }
        }
        mock_config.options.utc_mode = utc_mode['stored']
        WorkflowConfig.process_utc_mode(mock_config)
        assert mock_config.cfg['scheduler']['UTC mode'] is expected
        assert get_utc_mode() is expected
        assert len(caplog.record_tuples) == expected_warnings
        caplog.clear()

    tests = [
        {
            'utc_mode': {'glbl': True, 'workflow': None, 'stored': None},
            'expected': True
        },
        {
            'utc_mode': {'glbl': True, 'workflow': False, 'stored': None},
            'expected': False
        },
        {
            # On restart
            'utc_mode': {'glbl': False, 'workflow': None, 'stored': True},
            'expected': True
        },
        {
            # Changed config value between restarts
            'utc_mode': {'glbl': False, 'workflow': False, 'stored': True},
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
                'cycle point time zone': cp_tz['workflow']
            }
        }
        mock_config.options.cycle_point_tz = cp_tz['stored']
        WorkflowConfig.process_cycle_point_tz(mock_config)
        assert mock_config.cfg['scheduler'][
            'cycle point time zone'] == expected
        assert len(caplog.record_tuples) == expected_warnings
        caplog.clear()

    tests = [
        {
            'cp_tz': {'workflow': None, 'stored': None},
            'utc_mode': True,
            'expected': 'Z'
        },
        {
            'cp_tz': {'workflow': None, 'stored': None},
            'utc_mode': False,
            'expected': local_tz
        },
        {
            'cp_tz': {'workflow': '+0530', 'stored': None},
            'utc_mode': True,
            'expected': '+0530'
        },
        {
            # On restart
            'cp_tz': {'workflow': None, 'stored': '+0530'},
            'utc_mode': True,
            'expected': '+0530'
        },
        {
            # Changed config value between restarts
            'cp_tz': {'workflow': '+0530', 'stored': '-0030'},
            'utc_mode': True,
            'expected': '-0030',
            'expected_warnings': 1
        },
        {
            'cp_tz': {'workflow': 'Z', 'stored': 'Z'},
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
    flow_cylc = tmp_path.joinpath(WorkflowFiles.FLOW_FILE)
    flow_cylc.write_text(flow_cylc_content)

    with pytest.raises(WorkflowConfigError) as exc:
        WorkflowConfig(
            workflow="rsynctest",
            fpath=flow_cylc,
            options=Mock(spec=[])
        )
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
        allow implicit tasks = True
    """
    flow_cylc = tmp_path.joinpath(WorkflowFiles.FLOW_FILE)
    flow_cylc.write_text(flow_cylc_content)

    config = WorkflowConfig(workflow="rsynctest", fpath=flow_cylc,
                            options=Mock(spec=[]))

    rsync_includes = WorkflowConfig.get_validated_rsync_includes(config)
    assert rsync_includes == ['dir/', 'dir2/', 'file1', 'file2']


@pytest.mark.parametrize(
    'cycling_type, runahead_limit, valid',
    [
        (INTEGER_CYCLING_TYPE, 'P14', True),
        (ISO8601_CYCLING_TYPE, 'P14', True),
        (ISO8601_CYCLING_TYPE, 'PT12H', True),
        (ISO8601_CYCLING_TYPE, 'P7D', True),
        (ISO8601_CYCLING_TYPE, 'P2W', True),
        (ISO8601_CYCLING_TYPE, '4', True),

        (INTEGER_CYCLING_TYPE, 'PT12H', False),
        (INTEGER_CYCLING_TYPE, 'P7D', False),
        (INTEGER_CYCLING_TYPE, '4', False),
        (ISO8601_CYCLING_TYPE, '', False),
        (ISO8601_CYCLING_TYPE, 'asdf', False)
    ]
)
def test_process_runahead_limit(
    cycling_type: str, runahead_limit: str, valid: bool,
    set_cycling_type: Callable
) -> None:
    set_cycling_type(cycling_type)
    mock_config = Mock(cycling_type=cycling_type)
    mock_config.cfg = {
        'scheduling': {
            'runahead limit': runahead_limit
        }
    }
    if valid:
        WorkflowConfig.process_runahead_limit(mock_config)
    else:
        with pytest.raises(WorkflowConfigError) as exc:
            WorkflowConfig.process_runahead_limit(mock_config)
        assert "bad runahead limit" in str(exc.value).lower()


@pytest.mark.parametrize(
    'opt', [None, 'check_circular']
)
def test_check_circular(opt, monkeypatch, caplog, tmp_path):
    """Test WorkflowConfig._check_circular()."""
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
    flow_file = tmp_path.joinpath(WorkflowFiles.FLOW_FILE)
    flow_file.write_text(flow_config)

    def WorkflowConfig__assert_err_raised():
        with pytest.raises(WorkflowConfigError) as exc:
            WorkflowConfig(
                workflow='circular', fpath=flow_file, options=options)
        assert "circular edges detected" in str(exc.value)

    # ----- The actual test -----
    WorkflowConfig__assert_err_raised()
    # Now artificially lower the limit and re-test:
    monkeypatch.setattr(
        'cylc.flow.config.WorkflowConfig.CHECK_CIRCULAR_LIMIT', 4)
    if opt != 'check_circular':
        # Will no longer raise
        WorkflowConfig(workflow='circular', fpath=flow_file, options=options)
        msg = "will not check graph for circular dependencies"
        assert msg in caplog.text
    else:
        WorkflowConfig__assert_err_raised()
