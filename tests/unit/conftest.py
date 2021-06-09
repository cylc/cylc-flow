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
from typing import Any, Callable, Optional
from unittest.mock import create_autospec, Mock

import pytest

from cylc.flow.cycling.iso8601 import init as iso8601_init
from cylc.flow.cycling.loader import (
    ISO8601_CYCLING_TYPE,
    INTEGER_CYCLING_TYPE
)
from cylc.flow.data_store_mgr import DataStoreMgr
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
        installed: named or no-name. Creates 
    """
    def _tmp_run_dir(reg: Optional[str] = None, installed = None) -> Path:
        cylc_run_dir = tmp_path / 'cylc-run'
        cylc_run_dir.mkdir(exist_ok=True)
        monkeypatch.setattr('cylc.flow.pathutil._CYLC_RUN_DIR', cylc_run_dir)
        if reg:
            run_dir = cylc_run_dir.joinpath(reg)
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / WorkflowFiles.FLOW_FILE).touch(exist_ok=True)
            (run_dir / WorkflowFiles.Service.DIRNAME).mkdir(exist_ok=True)
            if installed == 'named':
                (run_dir.parent / WorkflowFiles.Install.DIRNAME).mkdir(exist_ok=True)
            elif installed == 'no-name':
                (run_dir / WorkflowFiles.Install.DIRNAME).mkdir(exist_ok=True)

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
