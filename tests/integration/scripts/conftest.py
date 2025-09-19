#!/usr/bin/env python3

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

from types import SimpleNamespace
from uuid import uuid1

import pytest

from cylc.flow.workflow_files import WorkflowFiles

from ..utils.flow_writer import flow_config_str


@pytest.fixture
def one_src(tmp_path, one_conf):
    src_dir = tmp_path
    (src_dir / 'flow.cylc').write_text(flow_config_str(one_conf))
    (src_dir / 'rose-suite.conf').touch()
    return SimpleNamespace(path=src_dir)


@pytest.fixture
def one_run(one_src, test_dir, run_dir):
    w_run_dir = test_dir / str(uuid1())
    w_run_dir.mkdir()
    (w_run_dir / 'flow.cylc').write_text(
        (one_src.path / 'flow.cylc').read_text()
    )
    (w_run_dir / 'rose-suite.conf').write_text(
        (one_src.path / 'rose-suite.conf').read_text()
    )
    install_dir = (w_run_dir / WorkflowFiles.Install.DIRNAME)
    install_dir.mkdir(parents=True)
    (install_dir / WorkflowFiles.Install.SOURCE).symlink_to(
        one_src.path,
        target_is_directory=True,
    )
    return SimpleNamespace(
        path=w_run_dir,
        id=str(w_run_dir.relative_to(run_dir)),
    )
