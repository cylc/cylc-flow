# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) Earth Sciences New Zealand & British Crown (Met Office)
# & Contributors.
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

from pathlib import Path
from shlex import split
from subprocess import run

import pytest

from cylc.flow.resources import (
    RESOURCE_NAMES,
    _backup,
    get_resources,
)


def test_get_resources_one(tmp_path: Path):
    """Test extraction of a specific resource.

    Check that a file of the right name gets extracted.
    Do not check file content because there is no assurance that it will
    remain constant.
    """
    get_resources('job.sh', tmp_path)
    assert (tmp_path / 'job.sh').is_file()


@pytest.mark.parametrize('target_dir', [True, None])
@pytest.mark.parametrize(
    'resource',
    [r for r in RESOURCE_NAMES if not r.startswith('!')],
)
def test_get_resources_all(
    target_dir, resource, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    if not target_dir:
        monkeypatch.chdir(tmp_path)
    get_resources(resource, tmp_path if target_dir else None)
    assert (tmp_path / Path(resource).name).exists()


def test_get_resources_tutorial(tmp_path: Path):
    """It extracts a tutorial workflow to the specified target directory."""
    get_resources('tutorial/runtime-tutorial', tmp_path)
    assert (tmp_path / 'runtime-tutorial').is_dir()


def test_get_resources_tutorial_no_target(tmp_path: Path, mock_glbl_cfg):
    """It extracts a tutorial workflow to configured source dir when no target
    is specified."""
    cylc_src_dir = tmp_path / 'cylc-src'
    mock_glbl_cfg(
        'cylc.flow.resources.glbl_cfg',
        f"""
            [install]
                source dirs = {cylc_src_dir}
        """,
    )
    get_resources('tutorial/runtime-tutorial', None)
    assert (cylc_src_dir / 'runtime-tutorial').is_dir()


def test_cli(tmp_path: Path):
    result = run(
        split(f'cylc get-resources job.sh {tmp_path}'),
        capture_output=True
    )
    assert result.returncode == 0, result.stderr.decode()


def test_backup(tmp_path, caplog):
    a = tmp_path / 'a'
    abc = tmp_path / 'a' / 'b' / 'c'
    abc.mkdir(parents=True)
    before = set(tmp_path.glob('*'))

    _backup(a)
    assert len(caplog.record_tuples) == 1

    after = set(tmp_path.glob('*'))
    assert len(after - before) == 1

    new = list(after - before)[0]
    assert new.name.startswith(a.name)

    new_abc = new / 'b' / 'c'
    assert new_abc.exists()


def test_vim_deprecated():
    """It fails, returning a warning if user asks for obsolete syntax file
    """
    output = run(
        ['cylc', 'get-resources', 'syntax/cylc.vim'],
        capture_output=True
    )
    assert 'has been replaced' in output.stderr.decode()
