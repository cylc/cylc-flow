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

from cylc.flow.post_install.log_vc_info import (
    get_diff, get_git_commit, get_status, get_vc_info, main
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


def skip_if_not_installed(command: str) -> None:
    """Skip test if command is not installed"""
    proc = subprocess.run(['command', '-v', command])
    if proc.returncode != 0:
        pytest.skip(f"{command} is not installed")


@pytest.fixture(scope='module')
def git_source_repo(tmp_path_factory: Fixture) -> Tuple[Path, str]:
    """Init a git repo for a workflow source dir.

    The repo has a flow.cylc file with uncommitted changes. This dir is reused
    by all tests requesting it in this module.

    Returns (source_dir_path, commit_hash)
    """
    skip_if_not_installed('git')
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


@pytest.fixture(scope='module')
def svn_source_repo(
        tmp_path_factory: Fixture) -> Tuple[Path, str, Path]:
    """Init an svn repo & working copy for a workflow source dir.

    The working copy has a flow.cylc file with uncommitted changes. This dir
    is reused by all tests requesting it in this module.

    Returns (source_dir_path, repository_UUID, repository_path)
    """
    skip_if_not_installed('svn')
    tmp_path: Path = tmp_path_factory.getbasetemp()
    repo = tmp_path.joinpath('svn_repo')
    subprocess.run(
        ['svnadmin', 'create', 'svn_repo'], cwd=tmp_path, check=True)
    uuid = subprocess.run(
        ['svnlook', 'uuid', repo],
        check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    project_dir = tmp_path.joinpath('project')
    project_dir.mkdir()
    project_dir.joinpath('flow.cylc').write_text(BASIC_FLOW_1)
    subprocess.run(
        ['svn', 'import', project_dir, f'file://{repo}/project/trunk',
         '-m', 'Initial import'], check=True)
    source_dir = tmp_path.joinpath('svn_working_copy')
    subprocess.run(
        ['svn', 'checkout', f'file://{repo}/project/trunk', source_dir],
        check=True)

    flow_file = source_dir.joinpath('flow.cylc')
    # Overwrite file to introduce uncommitted changes:
    flow_file.write_text(BASIC_FLOW_2)

    return (source_dir, uuid, repo)


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
    expected = [
        ('version control system', "git"),
        ('repository version', f"{commit_sha[:7]}-dirty"),
        ('commit', commit_sha),
        ('working copy root path', source_dir),
        ('status', " M flow.cylc")
    ]
    assert list(vc_info.items()) == expected


def test_get_diff_git(git_source_repo: Fixture):
    """Test get_diff() for a git repo"""
    source_dir, commit_sha = git_source_repo
    diff_lines = get_diff('git', source_dir).splitlines()
    for line in ("diff --git a/flow.cylc b/flow.cylc",
                 "-        R1 = foo",
                 "+        R1 = bar"):
        assert line in diff_lines


def test_get_vc_info_svn(svn_source_repo: Fixture):
    """Test get_vc_info() for an svn working copy"""
    source_dir, uuid, repo_path = svn_source_repo
    vc_info = get_vc_info(source_dir)
    expected = [
        ('version control system', "svn"),
        ('working copy root path', str(source_dir)),
        ('url', f"file://{repo_path}/project/trunk"),
        ('repository uuid', uuid),
        ('revision', "1"),
        ('status', "M       flow.cylc")
    ]
    assert list(vc_info.items()) == expected


def test_get_diff_svn(svn_source_repo: Fixture):
    """Test get_diff() for an svn working copy"""
    source_dir, uuid, repo_path = svn_source_repo
    diff_lines = get_diff('svn', source_dir).splitlines()
    for line in ("--- flow.cylc	(revision 1)",
                 "+++ flow.cylc	(working copy)",
                 "-        R1 = foo",
                 "+        R1 = bar"):
        assert line in diff_lines


def test_not_repo(tmp_path: Fixture, monkeypatch: Fixture):
    """Test get_vc_info() and main() for a dir that is not a supported repo"""
    source_dir = Path(tmp_path, 'git_repo')
    source_dir.mkdir()
    flow_file = source_dir.joinpath('flow.cylc')
    flow_file.write_text(BASIC_FLOW_1)
    monkeypatch.setattr('cylc.flow.post_install.log_vc_info.write_vc_info',
                        lambda *a, **k: None)
    monkeypatch.setattr('cylc.flow.post_install.log_vc_info.write_diff',
                        lambda *a, **k: None)

    assert get_vc_info(source_dir) is None
    assert main(source_dir, None, None) is False


def test_no_base_commit_git(tmp_path: Fixture):
    """Test get_vc_info() and get_diff() for a recently init'd git source dir
    that does not have a base commit yet."""
    skip_if_not_installed('git')
    source_dir = Path(tmp_path, 'new_git_repo')
    source_dir.mkdir()
    subprocess.run(['git', 'init'], cwd=source_dir, check=True)
    flow_file = source_dir.joinpath('flow.cylc')
    flow_file.write_text(BASIC_FLOW_1)

    vc_info = get_vc_info(source_dir)
    expected = [
        ('version control system', "git"),
        ('working copy root path', source_dir),
        ('status', "?? flow.cylc")
    ]
    assert list(vc_info.items()) == expected
    assert get_diff('git', source_dir) is None
