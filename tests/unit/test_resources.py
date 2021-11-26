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
    resource_names, list_resources, extract_resources)


def test_list_resources():
    """Test resources.list_resources."""
    result = '\n'.join(list_resources())
    for item in resource_names:
        assert item in result


def test_extract_resources_one(tmpdir):
    """Test extraction of a specific resource.

    Check that a file of the right name gets extracted.
    Do not check file content becuase there is no assurance that it will
    remain constant.
    """
    extract_resources(tmpdir, resources=['etc/job.sh'])
    assert (tmpdir / 'job.sh').isfile()


@pytest.mark.parametrize(
    'resource',
    resource_names.keys()
)
def test_extract_resources_all(resource, tmpdir):
    extract_resources(tmpdir, None)
    assert (tmpdir / Path(resource).name).exists()


def test_cli(tmpdir):
    result = run(
        split(f'cylc get-resources etc/job.sh {str(tmpdir)}'),
        capture_output=True
    )
    if result.returncode != 0:
        raise AssertionError(
            f'{result.stderr}'
        )
