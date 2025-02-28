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

import pytest

from pathlib import Path
from shlex import split
from subprocess import run

from cylc.flow.resources import (
    RESOURCE_NAMES,
    get_resources,
    _backup,
)


def test_get_resources_one(tmpdir):
    """Test extraction of a specific resource.

    Check that a file of the right name gets extracted.
    Do not check file content becuase there is no assurance that it will
    remain constant.
    """
    get_resources('job.sh', tmpdir)
    assert (tmpdir / 'job.sh').isfile()


@pytest.mark.parametrize(
    'resource',
    [
        r for r
        in list(RESOURCE_NAMES.keys())
        if r[0] != '!'
    ] + ['tutorial/runtime-tutorial']
)
def test_get_resources_all(resource, tmpdir):
    get_resources(resource, tmpdir)
    assert (tmpdir / Path(resource).name).exists()


def test_cli(tmpdir):
    result = run(
        split(f'cylc get-resources job.sh {str(tmpdir)}'),
        capture_output=True
    )
    if result.returncode != 0:
        raise AssertionError(
            f'{result.stderr}'
        )


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
