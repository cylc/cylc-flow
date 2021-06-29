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
"""Standard pytest fixtures for unit tests."""

from pathlib import Path
import pytest
from shutil import rmtree
from typing import Any, Callable, Optional
from unittest.mock import create_autospec, Mock

from cylc.flow.cfgspec.globalcfg import SPEC
from cylc.flow.cycling.iso8601 import init as iso8601_init
from cylc.flow.cycling.loader import (
    ISO8601_CYCLING_TYPE,
    INTEGER_CYCLING_TYPE
)
from cylc.flow.data_store_mgr import DataStoreMgr
from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.scheduler import Scheduler
from cylc.flow.workflow_files import WorkflowFiles
from cylc.flow.xtrigger_mgr import XtriggerManager


# Type alias for monkeymock()
MonkeyMock = Callable[..., Mock]


@pytest.fixture
def monkeymock(monkeypatch: pytest.MonkeyPatch):
    """Fixture that patches a function/attr with a Mock and returns that Mock.

    Args:
        pypath: The Python-style import path to be patched.
        **kwargs: Any kwargs to set on the Mock.

    Example:
        mock_clean = monkeymock('cylc.flow.workflow_files.clean')
        something()  # calls workflow_files.clean
        assert mock_clean.called is True
    """
    def inner(pypath: str, **kwargs: Any) -> Mock:
        _mock = Mock(**kwargs)
        monkeypatch.setattr(pypath, _mock)
        return _mock
    return inner


@pytest.fixture
def tmp_run_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fixture that patches the cylc-run dir to the tests's {tmp_path}/cylc-run
    and optionally creates a workflow run dir inside.

    Args:
        reg: Workflow name.
    """
    def _tmp_run_dir(reg: Optional[str] = None) -> Path:
        cylc_run_dir = tmp_path / 'cylc-run'
        cylc_run_dir.mkdir(exist_ok=True)
        monkeypatch.setattr('cylc.flow.pathutil._CYLC_RUN_DIR', cylc_run_dir)
        if reg:
            run_dir = cylc_run_dir.joinpath(reg)
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / WorkflowFiles.FLOW_FILE).touch(exist_ok=True)
            (run_dir / WorkflowFiles.Service.DIRNAME).mkdir(exist_ok=True)
            return run_dir
        return cylc_run_dir
    return _tmp_run_dir


@pytest.fixture
def set_cycling_type(monkeypatch: pytest.MonkeyPatch):
    """Initialize the Cylc cycling type.

    Args:
        ctype: The cycling type (integer or iso8601).
        time_zone: If using ISO8601/datetime cycling type, you can specify a
            custom time zone to use.
    """
    def _set_cycling_type(
        ctype: str = INTEGER_CYCLING_TYPE, time_zone: Optional[str] = None
    ) -> None:
        class _DefaultCycler:
            TYPE = ctype
        monkeypatch.setattr(
            'cylc.flow.cycling.loader.DefaultCycler', _DefaultCycler)
        if ctype == ISO8601_CYCLING_TYPE:
            iso8601_init(time_zone=time_zone)
    return _set_cycling_type


@pytest.fixture
def mock_glbl_cfg(tmp_path, monkeypatch):
    """A Pytest fixture for fiddling global config values.

    * Hacks the specified `glbl_cfg` object.
    * Can be called multiple times within a test function.

    Args:
        pypath (str):
            The python-like path to the global configuation object you want
            to fiddle.
            E.G. if you want to hack the `glbl_cfg` in
            `cylc.flow.scheduler` you would provide
            `cylc.flow.scheduler.glbl_cfg`
        global_config (str):
            The globlal configuration as a multi-line string.

    Example:
        Change the value of `UTC mode` in the global config as seen from
        `the scheduler` module.

        def test_something(mock_glbl_cfg):
            mock_glbl_cfg(
                'cylc.flow.scheduler.glbl_cfg',
                '''
                    [scheduler]
                        UTC mode = True
                '''
            )

    """
    # TODO: modify Parsec so we can use StringIO rather than a temp file.
    def _mock(pypath, global_config):
        nonlocal tmp_path, monkeypatch
        global_config_path = tmp_path / 'global.cylc'
        global_config_path.write_text(global_config)
        glbl_cfg = ParsecConfig(SPEC)
        glbl_cfg.loadcfg(global_config_path)

        def _inner(cached=False):
            nonlocal glbl_cfg
            return glbl_cfg

        monkeypatch.setattr(pypath, _inner)

    yield _mock
    rmtree(tmp_path)


@pytest.fixture
def xtrigger_mgr() -> XtriggerManager:
    """A fixture to build an XtriggerManager which uses a mocked proc_pool,
    and uses a mocked broadcast_mgr."""
    return XtriggerManager(
        workflow="sample_workflow",
        user="john-foo",
        proc_pool=Mock(put_command=lambda *a, **k: True),
        broadcast_mgr=Mock(put_broadcast=lambda *a, **k: True),
        data_store_mgr=DataStoreMgr(create_autospec(Scheduler))
    )
