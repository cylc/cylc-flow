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

from pathlib import Path
import subprocess
import pytest
from typing import Any, Tuple

from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.post_install.log_vc_info import (
    get_diff, get_git_commit, get_status, get_vc_info
)

Fixture = Any


BASIC_FLOW_1 = """
[scheduling]
    [[graph]]
        R1 = foo
"""

BASIC_FLOW_2 = """
[scheduling]
    [[graph]]
        R1 = bar
"""


@pytest.fixture(scope='module')
def git_source_repo(tmp_path_factory: Fixture) -> Tuple[Path, str]:
    """Init a git repo for a workflow source dir.

    The repo has a flow.cylc file with uncomitted changes. This dir is reused
    by all tests requesting it in this module.

    Returns (source_dir_path, commit_hash)
    """
    source_dir: Path = tmp_path_factory.getbasetemp().joinpath('git_repo')
    source_dir.mkdir()
    subprocess.run(['git', 'init'], cwd=source_dir, check=True)
    flow_file = source_dir.joinpath('flow.cylc')
    flow_file.write_text(BASIC_FLOW_1)
    subprocess.run(['git', 'add', '-A'], cwd=source_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-am', 'Initial commit'], cwd=source_dir, check=True)
    # Overwrite file to introduce uncommitted changes:
    flow_file.write_text(BASIC_FLOW_2)
    commit_sha = subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=source_dir, check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    return (source_dir, commit_sha)


def test_get_git_commit(git_source_repo: Fixture):
    """Test get_git_commit()"""
    source_dir, commit_sha = git_source_repo
    assert get_git_commit(source_dir) == commit_sha


def test_get_status_git(git_source_repo: Fixture):
    """Test get_status() for a git repo"""
    source_dir, commit_sha = git_source_repo
    assert get_status('git', source_dir) == " M flow.cylc"


def test_get_vc_info_git(git_source_repo: Fixture):
    """Test get_vc_info() for a git repo"""
    source_dir, commit_sha = git_source_repo
    vc_info = get_vc_info(source_dir)
    expected = OrderedDictWithDefaults([
        ('version control system', "git"),
        ('repository version', f"{commit_sha[:7]}-dirty"),
        ('commit', commit_sha),
        ('working copy root path', source_dir),
        ('status', " M flow.cylc")
    ])
    assert vc_info == expected


def test_get_diff_git(git_source_repo: Fixture):
    """Test get_diff() for a git repo"""
    source_dir, commit_sha = git_source_repo
    diff_lines = get_diff('git', source_dir).splitlines()
    for line in ("diff --git a/flow.cylc b/flow.cylc",
                 "-        R1 = foo",
                 "+        R1 = bar"):
        assert line in diff_lines
