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

"""Test cylc install."""

import pytest
from pathlib import Path

from .test_scan import init_flows

from cylc.flow.async_util import pipe
from cylc.flow.scripts import scan
from cylc.flow.workflow_files import WorkflowFiles
from cylc.flow.scripts.install import (
    InstallOptions,
    install_cli
)

from typing import Callable, Tuple

SRV_DIR = Path(WorkflowFiles.Service.DIRNAME)
CONTACT = Path(WorkflowFiles.Service.CONTACT)
RUN_N = Path(WorkflowFiles.RUN_N)
INSTALL = Path(WorkflowFiles.Install.DIRNAME)

INSTALLED_MSG = "INSTALLED {wfrun} from"
WF_ACTIVE_MSG = '1 run of "{wf}" is already active:'
BAD_CONTACT_MSG = "Bad contact file:"


@pytest.fixture()
def patch_graphql_query(
    monkeypatch: pytest.MonkeyPatch
):
    # Define a mocked graphql_query pipe function.
    @pipe
    async def _graphql_query(flow, fields, filters=None):
        flow.update({"status": "running"})
        return flow

    # Swap out the function that cylc.flow.scripts.scan.
    monkeypatch.setattr(
        'cylc.flow.scripts.scan.graphql_query',
        _graphql_query,
    )


@pytest.fixture()
def src_run_dirs(
    mock_glbl_cfg: Callable,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path
) -> Tuple[Path, Path]:
    """Create some workflow source and run dirs for testing.

    Source dirs:
      <tmp-src>/w1
      <tmp-src>/w2

    Run dir:
      <tmp-run>/w1/run1

    """
    tmp_src_path = tmp_path / 'cylc-src'
    tmp_run_path = tmp_path / 'cylc-run'
    tmp_src_path.mkdir()
    tmp_run_path.mkdir()

    init_flows(
        tmp_run_path=tmp_run_path,
        running=('w1/run1',),
        tmp_src_path=tmp_src_path,
        src=('w1', 'w2')
    )
    mock_glbl_cfg(
        'cylc.flow.workflow_files.glbl_cfg',
        f'''
            [install]
                source dirs = {tmp_src_path}
        '''
    )
    monkeypatch.setattr('cylc.flow.pathutil._CYLC_RUN_DIR', tmp_run_path)

    return tmp_src_path, tmp_run_path


def test_install_scan_no_ping(
    src_run_dirs: Callable,
    capsys: pytest.CaptureFixture,
    caplog: pytest.LogCaptureFixture
) -> None:
    """At install, running intances should be reported.

    Ping = False case: don't query schedulers.
    """

    opts = InstallOptions()
    opts.no_ping = True

    install_cli(opts, reg='w1')
    out = capsys.readouterr().out
    assert INSTALLED_MSG.format(wfrun='w1/run2') in out
    assert WF_ACTIVE_MSG.format(wf='w1') in out
    # Empty contact file faked with "touch":
    assert f"{BAD_CONTACT_MSG} w1/run1" in caplog.text

    install_cli(opts, reg='w2')
    out = capsys.readouterr().out
    assert WF_ACTIVE_MSG.format(wf='w2') not in out
    assert INSTALLED_MSG.format(wfrun='w2/run1') in out


def test_install_scan_ping(
    src_run_dirs: Callable,
    capsys: pytest.CaptureFixture,
    caplog: pytest.LogCaptureFixture,
    patch_graphql_query: Callable
) -> None:
    """At install, running intances should be reported.

    Ping = True case: but mock scan's scheduler query method.
    """
    opts = InstallOptions()
    opts.no_ping = False

    install_cli(opts, reg='w1')
    out = capsys.readouterr().out
    assert INSTALLED_MSG.format(wfrun='w1/run2') in out
    assert WF_ACTIVE_MSG.format(wf='w1') in out
    assert scan.FLOW_STATE_SYMBOLS["running"] in out
    # Empty contact file faked with "touch":
    assert f"{BAD_CONTACT_MSG} w1/run1" in caplog.text

    install_cli(opts, reg='w2')
    out = capsys.readouterr().out
    assert INSTALLED_MSG.format(wfrun='w2/run1') in out
    assert WF_ACTIVE_MSG.format(wf='w2') not in out


def test_install_gets_back_compat_mode_for_plugins(
    src_run_dirs: Callable,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
):
    """Assert that pre cylc install will detect whether a workflow
    should use back compat mode _before_ running pre_configure plugins
    so that those plugins can use that information.
    """
    class failIfDeprecated:
        """A fake Cylc Plugin entry point"""
        @staticmethod
        def resolve():
            return failIfDeprecated.raiser

        @staticmethod
        def raiser(*_, **__):
            import cylc.flow.flags
            if cylc.flow.flags.cylc7_back_compat:
                print('Plugin:True')
                return True
            print('Plugin:False')
            return False

    # Monkeypatch our fake entry point into iter_entry_points:
    monkeypatch.setattr(
        'cylc.flow.scripts.install.iter_entry_points',
        lambda x: [failIfDeprecated]
    )
    opts = InstallOptions()

    monkeypatch.setattr('cylc.flow.flags.cylc7_back_compat', False)
    install_cli(opts, reg='w1')
    assert capsys.readouterr()[0].split('\n')[0] == 'Plugin:False'

    monkeypatch.setattr('cylc.flow.flags.cylc7_back_compat', True)
    install_cli(opts, reg='w1')
    assert capsys.readouterr()[0].split('\n')[0] == 'Plugin:True'
