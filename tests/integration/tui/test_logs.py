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

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.exceptions import ClientError
from cylc.flow.task_job_logs import get_task_job_log
from cylc.flow.task_state import (
    TASK_STATUS_FAILED,
    TASK_STATUS_SUCCEEDED,
)
from cylc.flow.tui.data import _get_log

import pytest

if TYPE_CHECKING:
    from cylc.flow.id import Tokens


def get_job_log(tokens: 'Tokens', suffix: str) -> Path:
    """Return the path to a job log file.

    Args:
        tokens: Job tokens.
        suffix: Filename.

    """
    return Path(get_task_job_log(
        tokens['workflow'],
        tokens['cycle'],
        tokens['task'],
        tokens['job'],
        suffix=suffix,
    ))


@pytest.fixture(scope='module')
def standarise_host_and_path(mod_monkeypatch):
    """Replace variable content in the log view.

    The log view displays the "Host" and "Path" of the log file. These will
    differer from user to user, so we mock away the difference to produce
    stable results.
    """
    def _parse_log_header(contents):
        _header, text = contents.split('\n', 1)
        return 'myhost', 'mypath', text

    mod_monkeypatch.setattr(
        'cylc.flow.tui.data._parse_log_header',
        _parse_log_header,
    )


@pytest.fixture
def wait_log_loaded(monkeypatch):
    """Wait for Tui to successfully open a log file."""
    # previous log open count
    before = 0
    # live log open count
    count = 0

    # wrap the Tui "_get_log" method to count the number of times it has
    # returned
    def __get_log(*args, **kwargs):
        nonlocal count
        try:
            ret = _get_log(*args, **kwargs)
        except ClientError as exc:
            count += 1
            raise exc
        count += 1
        return ret
    monkeypatch.setattr(
        'cylc.flow.tui.data._get_log',
        __get_log,
    )

    async def _wait_log_loaded(tries: int = 25, delay: float = 0.1):
        """Wait for the log file to be loaded.

        Args:
            tries: The number of (re)tries to attempt before failing.
            delay: The delay between retries.

        """
        nonlocal before
        for _try in range(tries):
            if count > before:
                await asyncio.sleep(0)
                before += 1
                return
            await asyncio.sleep(delay)
        raise Exception(f'Log file was not loaded within {delay * tries}s')

    return _wait_log_loaded


@pytest.fixture(scope='module')
async def workflow(
    mod_flow, mod_scheduler, mod_start, standarise_host_and_path
):
    """Test fixture providing a workflow with some log files to poke at."""
    id_ = mod_flow({
        'scheduling': {
            'graph': {
                'R1': 'a',
            }
        },
        'runtime': {
            'a': {},
        }
    }, name='one')
    schd = mod_scheduler(id_)
    async with mod_start(schd):
        # create some log files for tests to inspect

        # create a scheduler log
        # (note the scheduler log doesn't get created in integration tests)
        scheduler_log = Path(schd.workflow_log_dir, '01-start-01.log')
        with open(scheduler_log, 'w+') as logfile:
            logfile.write(
                'this is the scheduler log file'
                + '\n'
                + '\n'.join(f'line {x}' for x in range(2, 1000))
            )

        # task 1/a
        itask = schd.pool.get_task(IntegerPoint('1'), 'a')
        itask.submit_num = 2

        # mark 1/a/01 as failed
        job_1 = schd.tokens.duplicate(cycle='1', task='a', job='01')
        schd.data_store_mgr.insert_job(
            'a',
            IntegerPoint('1'),
            TASK_STATUS_SUCCEEDED,
            {'submit_num': 1, 'platform': {'name': 'x'}}
        )
        schd.data_store_mgr.delta_job_state(job_1, TASK_STATUS_FAILED)

        # mark 1/a/02 as succeeded
        job_2 = schd.tokens.duplicate(cycle='1', task='a', job='02')
        schd.data_store_mgr.insert_job(
            'a',
            IntegerPoint('1'),
            TASK_STATUS_SUCCEEDED,
            {'submit_num': 2, 'platform': {'name': 'x'}}
        )
        schd.data_store_mgr.delta_job_state(job_1, TASK_STATUS_SUCCEEDED)
        schd.data_store_mgr.delta_task_state(itask)

        # mark 1/a as succeeded
        itask.state_reset(TASK_STATUS_SUCCEEDED)
        schd.data_store_mgr.delta_task_state(itask)

        # 1/a/01 - job.out
        job_1_out = get_job_log(job_1, 'job.out')
        job_1_out.parent.mkdir(parents=True)
        with open(job_1_out, 'w+') as log:
            log.write(f'job: {job_1.relative_id}\nthis is a job log\n')

        # 1/a/02 - job.out
        job_2_out = get_job_log(job_2, 'job.out')
        job_2_out.parent.mkdir(parents=True)
        with open(job_2_out, 'w+') as log:
            log.write(f'job: {job_2.relative_id}\nthis is a job log\n')

        # 1/a/02 - job.err
        job_2_err = get_job_log(job_2, 'job.err')
        with open(job_2_err, 'w+') as log:
            log.write(f'job: {job_2.relative_id}\nthis is a job error\n')

        # 1/a/NN -> 1/a/02
        (job_2_out.parent.parent / 'NN').symlink_to(
            (job_2_out.parent.parent / '02'),
            target_is_directory=True,
        )

        # populate the data store
        await schd.update_data_structure()

        yield schd


async def test_scheduler_logs(
    workflow,
    mod_rakiura,
    wait_log_loaded,
):
    """Test viewing the scheduler log files."""
    with mod_rakiura(size='80,30') as rk:
        # wait for the workflow to appear (collapsed)
        rk.wait_until_loaded('#spring')

        # open the workflow in Tui
        rk.user_input('down', 'right')
        rk.wait_until_loaded(workflow.tokens.id)

        # open the log view for the workflow
        rk.user_input('enter')
        rk.user_input('down', 'down', 'enter')

        # wait for the default log file to load
        await wait_log_loaded()
        rk.compare_screenshot(
            'scheduler-log-file',
            'the scheduler log file should be open',
        )

        # jump to the bottom of the file
        rk.user_input('end')
        rk.compare_screenshot(
            'scheduler-log-file-bottom',
            'we should be looking at the bottom of the file'
        )

        # jump back to the top of the file
        rk.user_input('home')
        rk.compare_screenshot(
            'scheduler-log-file',
            'we should be looking at the bottom of the file'
        )

        # open the list of log files
        rk.user_input('enter')
        rk.compare_screenshot(
            'log-file-selection',
            'the list of available log files should be displayed'
        )

        # select the processed workflow configuration file
        rk.user_input('down', 'enter')

        # wait for the file to load
        await wait_log_loaded()
        rk.compare_screenshot(
            'workflow-configuration-file',
            'the workflow configuration file should be open'
        )


async def test_task_logs(
    workflow,
    mod_rakiura,
    wait_log_loaded,
):
    """Test viewing task log files.

    I.E. Test viewing job log files by opening the log view on a task.
    """
    with mod_rakiura(size='80,30') as rk:
        # wait for the workflow to appear (collapsed)
        rk.wait_until_loaded('#spring')

        # open the workflow in Tui
        rk.user_input('down', 'right')
        rk.wait_until_loaded(workflow.tokens.id)

        # open the context menu for the task 1/a
        rk.user_input('down', 'down', 'enter')

        # open the log view for the task 1/a
        rk.user_input('down', 'down', 'down', 'enter')

        # wait for the default log file to load
        await wait_log_loaded()
        rk.compare_screenshot(
            'latest-job.out',
            'the job.out file for the second job should be open',
        )

        rk.user_input('enter')
        rk.user_input('enter')

        # wait for the job.err file to load
        await wait_log_loaded()
        rk.compare_screenshot(
            'latest-job.err',
            'the job.out file for the second job should be open',
        )


async def test_job_logs(
    workflow,
    mod_rakiura,
    wait_log_loaded,
):
    """Test viewing the job log files.

    I.E. Test viewing job log files by opening the log view on a job.
    """
    with mod_rakiura(size='80,30') as rk:
        # wait for the workflow to appear (collapsed)
        rk.wait_until_loaded('#spring')

        # open the workflow in Tui
        rk.user_input('down', 'right')
        rk.wait_until_loaded(workflow.tokens.id)

        # open the context menu for the job 1/a/02
        rk.user_input('down', 'down', 'right', 'down', 'enter')

        # open the log view for the job 1/a/02
        rk.user_input('down', 'down', 'down', 'enter')

        # wait for the default log file to load
        await wait_log_loaded()
        rk.compare_screenshot(
            '02-job.out',
            'the job.out file for the *second* job should be open',
        )

        # close log view
        rk.user_input('q')

        # open the log view for the job 1/a/01
        rk.user_input('down', 'enter')
        rk.user_input('down', 'down', 'down', 'enter')

        # wait for the default log file to load
        await wait_log_loaded()
        rk.compare_screenshot(
            '01-job.out',
            'the job.out file for the *first* job should be open',
        )


async def test_errors(
    workflow,
    mod_rakiura,
    wait_log_loaded,
    monkeypatch,
):
    """Test error handing of cat-log commands."""
    # make it look like cat-log commands are failing
    def cli_cmd_fail(*args, **kwargs):
        raise ClientError('Something went wrong :(')

    monkeypatch.setattr(
        'cylc.flow.tui.data.cli_cmd',
        cli_cmd_fail,
    )

    with mod_rakiura(size='80,30') as rk:
        # wait for the workflow to appear (collapsed)
        rk.wait_until_loaded('#spring')

        # open the log view on scheduler
        rk.user_input('down', 'enter', 'down', 'down', 'enter')

        # it will fail to open
        await wait_log_loaded()
        rk.compare_screenshot(
            'open-error',
            'the error message should be displayed in the log view header',
        )

        # open the file selector
        rk.user_input('enter')

        # it will fail to list avialable log files
        rk.compare_screenshot(
            'list-error',
            'the error message should be displayed in a pop up',
        )


async def test_external_editor(
    workflow,
    mod_rakiura,
    wait_log_loaded,
    monkeypatch,
    capsys,
):
    """Test the "open in external editor" functionality.

    This test covers the relevant code about as well as we can in an
    integration test.

    * The integration tests write HTML fragments to a file rather ANSI to a
      terminal.
    * Suspending / restoring the Tui session involves shell interaction that
      we cannot simulate here.
    * We're also not testing subprocesses in this integration test.

    But this test passing tells us that the relevant code does indeed run
    without falling over in a heap, so it will detect interface breakages and
    the like which is useful.
    """
    fake_popen_instances = []

    class FakePopen:
        def __init__(self, cmd, *args, raises=None, **kwargs):
            fake_popen_instances
            fake_popen_instances.append(self)
            self.cmd = cmd
            self.args = args
            self.kwargs = kwargs
            self.raises = raises

        def wait(self):
            if self.raises:
                raise self.raises()
            return 0

    # mock out subprocess.Popen
    monkeypatch.setattr(
        'cylc.flow.tui.overlay.Popen',
        FakePopen,
    )
    # mock out time.sleep
    monkeypatch.setattr(
        'cylc.flow.tui.overlay.sleep',
        lambda x: None,
    )

    with mod_rakiura(size='80,30') as rk:
        # wait for the workflow to appear (collapsed)
        rk.wait_until_loaded('#spring')

        # open the log view on scheduler
        rk.user_input('down', 'enter', 'down', 'down', 'enter')

        # it will fail to open
        await wait_log_loaded()

        assert len(fake_popen_instances) == 0
        assert capsys.readouterr()[1] == ''

        # select the open in "$EDITOR" option
        rk.user_input('down', 'left', 'left', 'left')

        # make a note of what the screen looks like
        rk.compare_screenshot(
            'before-opening-editor',
            'The open in $EDITOR option should be selected',
        )

        # launch the external tool
        rk.user_input('enter')

        # the subprocess should be started and a message logged to stderr
        assert len(fake_popen_instances) == 1
        assert 'launching external tool' in capsys.readouterr()[1].lower()

        # once the subprocess exist, the Tui session should be restored
        # exactly as it was before
        rk.compare_screenshot(
            'before-opening-editor',
            'The Tui session should restore exactly as it was before',
        )

        # get the subprocess to fail in a nasty way
        from functools import partial
        monkeypatch.setattr(
            'cylc.flow.tui.overlay.Popen',
            partial(FakePopen, raises=OSError),
        )

        # launch the external tool
        rk.user_input('enter')

        # the subprocess should be started, the error should be logged
        # to stderr
        assert len(fake_popen_instances) == 2
        assert 'error running' in capsys.readouterr()[1].lower()

        # once the subprocess exist, the Tui session should be restored
        # exactly as it was before
        rk.compare_screenshot(
            'before-opening-editor',
            'The Tui session should restore exactly as it was before',
        )
