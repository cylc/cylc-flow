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

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid1
from functools import partial

import pytest

from cylc.flow.exceptions import (
    WorkflowFilesError,
)
from cylc.flow.install import (
    reinstall_workflow,
)
from cylc.flow.option_parsers import Options
from cylc.flow.scripts.reinstall import (
    get_option_parser as reinstall_gop,
    reinstall_cli,
)
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import (
    WorkflowFiles,
)
from cylc.flow.network.multi import call_multi

ReInstallOptions = Options(reinstall_gop())

# cli opts

# interactive: yes no
# rose: yes no
# workflow_running: yes no


@pytest.fixture
def interactive(monkeypatch):
    monkeypatch.setattr(
        'cylc.flow.scripts.reinstall.is_terminal',
        lambda: True,
    )


@pytest.fixture
def non_interactive(monkeypatch):
    monkeypatch.setattr(
        'cylc.flow.scripts.reinstall.is_terminal',
        lambda: False,
    )


@pytest.fixture
def one_src(tmp_path):
    src_dir = tmp_path
    (src_dir / 'flow.cylc').touch()
    (src_dir / 'rose-suite.conf').touch()
    return SimpleNamespace(path=src_dir)


@pytest.fixture
def one_run(one_src, test_dir, run_dir):
    w_run_dir = test_dir / str(uuid1())
    w_run_dir.mkdir()
    (w_run_dir / 'flow.cylc').touch()
    (w_run_dir / 'rose-suite.conf').touch()
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


async def test_rejects_random_workflows(one, one_run):
    """It should only work with workflows installed by cylc install."""
    with pytest.raises(WorkflowFilesError) as exc_ctx:
        await reinstall_cli(opts=ReInstallOptions(), workflow_id=one.workflow)
    assert 'was not installed with cylc install' in str(exc_ctx.value)


async def test_invalid_source_dir(one_src, one_run):
    """It should detect & fail for an invalid source symlink"""
    source_link = Path(
        one_run.path,
        WorkflowFiles.Install.DIRNAME,
        WorkflowFiles.Install.SOURCE,
    )
    source_link.unlink()
    source_link.symlink_to(one_src.path / 'flow.cylc')

    with pytest.raises(WorkflowFilesError) as exc_ctx:
        await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id)
    assert 'Workflow source dir is not accessible' in str(exc_ctx.value)


async def test_no_changes_needed(one_src, one_run, capsys, interactive):
    """It should not reinstall if no changes are needed.

    This is not a hard requirement, in practice rsync output may differ
    from expectation so this is a nice-to-have, not expected to work 100%
    of the time.
    """
    assert not await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id)
    assert 'up to date with' in capsys.readouterr().out


async def test_non_interactive(one_src, one_run, capsys, capcall, non_interactive):
    """It should not perform a dry-run or prompt in non-interactive mode."""
    # capture reinstall calls
    reinstall_calls = capcall(
        'cylc.flow.scripts.reinstall.reinstall_workflow',
        reinstall_workflow,
    )
    # give it something to reinstall
    (one_src.path / 'a').touch()
    # reinstall
    assert await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id)
    # only one rsync call should have been made (i.e. no --dry-run)
    assert len(reinstall_calls) == 1
    assert 'Successfully reinstalled' in capsys.readouterr().out


async def test_interactive(
    one_src,
    one_run,
    capsys,
    capcall,
    interactive,
    monkeypatch
):
    """It should perform a dry-run and prompt in interactive mode."""
    # capture reinstall calls
    reinstall_calls = capcall(
        'cylc.flow.scripts.reinstall.reinstall_workflow',
        reinstall_workflow,
    )
    # give it something to reinstall
    (one_src.path / 'a').touch()

    # reinstall answering "no" to any prompt
    monkeypatch.setattr(
        'cylc.flow.scripts.reinstall._input',
        lambda x: 'n'
    )
    assert await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id) is False

    # only one rsync call should have been made (i.e. the --dry-run)
    assert [call[1].get('dry_run') for call in reinstall_calls] == [True]
    assert 'Reinstall canceled, no changes made.' in capsys.readouterr().out
    reinstall_calls.clear()

    # reinstall answering "yes" to any prompt
    monkeypatch.setattr(
        'cylc.flow.scripts.reinstall._input',
        lambda x: 'y'
    )
    assert await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id)

    # two rsync calls should have been made (i.e. the --dry-run and the real)
    assert [call[1].get('dry_run') for call in reinstall_calls] == [
        True, False
    ]
    assert 'Successfully reinstalled' in capsys.readouterr().out


async def test_workflow_running(
    one_src,
    one_run,
    monkeypatch,
    capsys,
    non_interactive,
):
    """It should advise running "cylc reload" where applicable."""
    # the message we are expecting
    reload_message = f'Run "cylc reload {one_run.id}"'

    # reinstall with a stopped workflow (reload message shouldn't show)
    assert await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id)
    assert reload_message not in capsys.readouterr().out

    # reinstall with a running workflow (reload message should show)
    monkeypatch.setattr(
        # make it look like the workflow is running
        'cylc.flow.scripts.reinstall.load_contact_file',
        lambda x: None,
    )
    assert await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id)
    assert reload_message in capsys.readouterr().out


async def test_rsync_stuff(one_src, one_run, capsys, non_interactive):
    """Make sure rsync is working correctly."""
    # src contains files: a, b
    (one_src.path / 'a').touch()
    with open(one_src.path / 'b', 'w+') as b_file:
        b_file.write('x')
    (one_src.path / 'b').touch()

    # run contains files: b, c (where b is different to the source copy)
    (one_run.path / 'b').touch()
    (one_run.path / 'c').touch()

    await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id)

    # a should have been left
    assert (one_run.path / 'a').exists()
    # b should have been updated
    assert (one_run.path / 'b').exists()
    with open(one_run.path / 'b', 'r') as b_file:
        assert b_file.read() == 'x'
    # c should have been removed
    assert not (one_run.path / 'c').exists()


async def test_rose_warning(one_src, one_run, capsys, interactive, monkeypatch):
    """It should warn that Rose installed files will be deleted.

    See https://github.com/cylc/cylc-rose/issues/149
    """
    # fragment of the message we expect
    rose_message = (
        'Files created by Rose file installation will show as deleted'
    )

    # reinstall answering "no" to any prompt
    monkeypatch.setattr(
        'cylc.flow.scripts.reinstall._input',
        lambda x: 'n'
    )
    (one_src.path / 'a').touch()  # give it something to install

    # reinstall (with rose-suite.conf file)
    await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id)
    assert rose_message in capsys.readouterr().err

    # reinstall (no rose-suite.conf file)
    (one_src.path / 'rose-suite.conf').unlink()
    await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id)
    assert rose_message not in capsys.readouterr().err


async def test_keyboard_interrupt(
    one_src,
    one_run,
    interactive,
    monkeypatch,
    capsys
):
    """It should handle a KeyboardInterrupt during dry-run elegantly.

    E.G. A user may ctrl+c rather than answering "n" (for no). To make it
    clear a canceled message should show.
    """
    def raise_keyboard_interrupt():
        raise KeyboardInterrupt()

    # currently the first call in the dry-run branch
    monkeypatch.setattr(
        'cylc.flow.scripts.reinstall.is_terminal',
        raise_keyboard_interrupt,
    )

    await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id)
    assert 'Reinstall canceled, no changes made' in capsys.readouterr().out


async def test_rsync_fail(one_src, one_run, mock_glbl_cfg, non_interactive):
    """It should raise an error on rsync failure."""
    mock_glbl_cfg(
        'cylc.flow.install.glbl_cfg',
        '''
            [platforms]
                [[localhost]]
                    rsync command = false
        ''',
    )

    (one_src.path / 'a').touch()  # give it something to install
    with pytest.raises(WorkflowFilesError) as exc_ctx:
        await reinstall_cli(opts=ReInstallOptions(), workflow_id=one_run.id)
    assert 'An error occurred reinstalling' in str(exc_ctx.value)
