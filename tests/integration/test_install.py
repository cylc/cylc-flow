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

from pathlib import Path

import pytest

from .test_scan import init_flows

from cylc.flow.workflow_files import WorkflowFiles
from cylc.flow.scripts.install import (
    InstallOptions,
    install_cli
)


SRV_DIR = Path(WorkflowFiles.Service.DIRNAME)
CONTACT = Path(WorkflowFiles.Service.CONTACT)
RUN_N = Path(WorkflowFiles.RUN_N)
INSTALL = Path(WorkflowFiles.Install.DIRNAME)


@pytest.fixture()
def src_run_dirs(mock_glbl_cfg, monkeypatch, tmp_path: Path):
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


def test_install_scan(src_run_dirs, capsys):
    """At install, any running intances should be reported."""

    opts = InstallOptions()
    # Don't ping the scheduler: it's not really running here.
    opts.no_ping = True

    install_cli(opts, reg='w1')
    assert '1 run of "w1" is already active:' in capsys.readouterr().out

    install_cli(opts, reg='w2')
    assert '1 run of "w2" is already active:' not in capsys.readouterr().out
