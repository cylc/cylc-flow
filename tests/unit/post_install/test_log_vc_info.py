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

import json
from pathlib import Path
import pytest
from pytest import MonkeyPatch, TempPathFactory
import shutil
import subprocess
from typing import Any, Callable, Tuple
from unittest.mock import Mock

from cylc.flow.install_plugins.log_vc_info import (
    INFO_FILENAME,
    LOG_VERSION_DIR,
    _get_git_commit,
    get_status,
    get_vc_info,
    main,
    write_diff,
)

from cylc.flow.workflow_files import WorkflowFiles

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


require_git = pytest.mark.skipif(
    shutil.which('git') is None,
    reason="git is not installed"
)

require_svn = pytest.mark.skipif(
    shutil.which('svn') is None,
    reason="svn is not installed"
)


@pytest.fixture(scope='module')
def git_source_repo(tmp_path_factory: TempPathFactory) -> Tuple[str, str]:
    """Init a git repo for a workflow source dir.

    The repo has uncommitted changes. This dir is reused
    by all tests requesting it in this module.

    Returns (source_dir_path, commit_hash)
    """
    source_dir: Path = tmp_path_factory.getbasetemp() / 'git_repo'
    source_dir.mkdir()
    subprocess.run(['git', 'init'], cwd=source_dir, check=True)
    flow_file = source_dir / 'flow.cylc'
    flow_file.write_text(BASIC_FLOW_1)
    subprocess.run(['git', 'add', '-A'], cwd=source_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-am', '"Initial commit"'],
        cwd=source_dir, check=True, capture_output=True)
    # Overwrite file to introduce uncommitted changes:
    flow_file.write_text(BASIC_FLOW_2)
    # Also add new file:
    (source_dir / 'gandalf.md').touch()
    commit_sha = subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=source_dir, check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    return (str(source_dir), commit_sha)


@pytest.fixture(scope='module')
def svn_source_repo(tmp_path_factory: TempPathFactory) -> Tuple[str, str, str]:
    """Init an svn repo & working copy for a workflow source dir.

    The working copy has a flow.cylc file with uncommitted changes. This dir
    is reused by all tests requesting it in this module.

    Returns (source_dir_path, repository_UUID, repository_path)
    """
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
         '-m', '"Initial import"'], check=True)
    source_dir = tmp_path.joinpath('svn_working_copy')
    subprocess.run(
        ['svn', 'checkout', f'file://{repo}/project/trunk', source_dir],
        check=True)

    flow_file = source_dir.joinpath('flow.cylc')
    # Overwrite file to introduce uncommitted changes:
    flow_file.write_text(BASIC_FLOW_2)

    return (str(source_dir), uuid, str(repo))


@require_git
def test_get_git_commit(git_source_repo: Tuple[str, str]):
    """Test get_git_commit()"""
    source_dir, commit_sha = git_source_repo
    assert _get_git_commit(source_dir) == commit_sha


@require_git
def test_get_status_git(git_source_repo: Tuple[str, str]):
    """Test get_status() for a git repo"""
    source_dir, commit_sha = git_source_repo
    assert get_status('git', source_dir) == [
        " M flow.cylc",
        "?? gandalf.md"
    ]


@require_git
def test_get_vc_info_git(git_source_repo: Tuple[str, str]):
    """Test get_vc_info() for a git repo"""
    source_dir, commit_sha = git_source_repo
    vc_info = get_vc_info(source_dir)
    assert vc_info is not None
    expected = [
        ('version control system', "git"),
        ('repository version', f"{commit_sha[:7]}-dirty"),
        ('commit', commit_sha),
        ('working copy root path', source_dir),
        ('status', [
            " M flow.cylc",
            "?? gandalf.md"
        ])
    ]
    assert list(vc_info.items()) == expected


@require_git
def test_write_diff_git(git_source_repo: Tuple[str, str], tmp_path: Path):
    """Test write_diff() for a git repo"""
    source_dir, _ = git_source_repo
    run_dir = tmp_path / 'run_dir'
    (run_dir / WorkflowFiles.LOG_DIR).mkdir(parents=True)
    diff_file = write_diff('git', source_dir, run_dir)
    diff_lines = diff_file.read_text().splitlines()
    assert diff_lines[0].startswith("# Auto-generated diff")
    for line in ("diff --git a/flow.cylc b/flow.cylc",
                 "-        R1 = foo",
                 "+        R1 = bar"):
        assert line in diff_lines


@require_git
def test_main_git(git_source_repo: Tuple[str, str], tmp_run_dir: Callable):
    """Test the written JSON info file."""
    source_dir, _ = git_source_repo
    run_dir: Path = tmp_run_dir('frodo')
    main(source_dir, None, run_dir)
    with open(run_dir / LOG_VERSION_DIR / INFO_FILENAME, 'r') as f:
        loaded = json.loads(f.read())
    assert isinstance(loaded, dict)
    assert loaded['version control system'] == 'git'
    assert isinstance(loaded['status'], list)
    assert len(loaded['status']) == 2


@require_svn
def test_get_vc_info_svn(svn_source_repo: Tuple[str, str, str]):
    """Test get_vc_info() for an svn working copy"""
    source_dir, uuid, repo_path = svn_source_repo
    vc_info = get_vc_info(source_dir)
    assert vc_info is not None
    expected = [
        ('version control system', "svn"),
        ('working copy root path', str(source_dir)),
        ('url', f"file://{repo_path}/project/trunk"),
        ('repository uuid', uuid),
        ('revision', "1"),
        ('status', ["M       flow.cylc"])
    ]
    assert list(vc_info.items()) == expected


@require_svn
def test_write_diff_svn(svn_source_repo: Tuple[str, str, str], tmp_path: Path):
    """Test write_diff() for an svn working copy"""
    source_dir, _, _ = svn_source_repo
    run_dir = tmp_path / 'run_dir'
    (run_dir / WorkflowFiles.LOG_DIR).mkdir(parents=True)
    diff_file = write_diff('svn', source_dir, run_dir)
    diff_lines = diff_file.read_text().splitlines()
    assert diff_lines[0].startswith("# Auto-generated diff")
    for line in (f"--- {source_dir}/flow.cylc	(revision 1)",
                 f"+++ {source_dir}/flow.cylc	(working copy)",
                 "-        R1 = foo",
                 "+        R1 = bar"):
        assert line in diff_lines


def test_not_repo(tmp_path: Path, monkeypatch: MonkeyPatch):
    """Test get_vc_info() and main() for a dir that is not a supported repo"""
    source_dir = Path(tmp_path, 'git_repo')
    source_dir.mkdir()
    flow_file = source_dir.joinpath('flow.cylc')
    flow_file.write_text(BASIC_FLOW_1)
    mock_write_vc_info = Mock()
    monkeypatch.setattr('cylc.flow.install_plugins.log_vc_info.write_vc_info',
                        mock_write_vc_info)
    mock_write_diff = Mock()
    monkeypatch.setattr('cylc.flow.install_plugins.log_vc_info.write_diff',
                        mock_write_diff)

    assert get_vc_info(source_dir) is None
    assert main(source_dir, None, None) is False  # type: ignore
    assert mock_write_vc_info.called is False
    assert mock_write_diff.called is False


@require_git
def test_no_base_commit_git(tmp_path: Path):
    """Test get_vc_info() and write_diff() for a recently init'd git source dir
    that does not have a base commit yet."""
    source_dir = Path(tmp_path, 'new_git_repo')
    source_dir.mkdir()
    subprocess.run(['git', 'init'], cwd=source_dir, check=True)
    flow_file = source_dir.joinpath('flow.cylc')
    flow_file.write_text(BASIC_FLOW_1)
    run_dir = tmp_path / 'run_dir'
    (run_dir / WorkflowFiles.LOG_DIR).mkdir(parents=True)

    vc_info = get_vc_info(source_dir)
    assert vc_info is not None
    assert list(vc_info.items()) == [
        ('version control system', "git"),
        ('working copy root path', str(source_dir)),
        ('status', ["?? flow.cylc"])
    ]

    # Diff file expected to be empty (only containing comment lines),
    # but should work without raising
    diff_file = write_diff('git', source_dir, run_dir)
    for line in diff_file.read_text().splitlines():
        assert line.startswith('#')
