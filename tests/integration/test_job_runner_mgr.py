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

import errno
import logging
from pathlib import Path
import re
from textwrap import dedent

from cylc.flow.job_runner_mgr import JobRunnerManager
from cylc.flow.pathutil import get_workflow_run_job_dir
from cylc.flow.task_state import TASK_STATUS_RUNNING
from cylc.flow.subprocctx import SubProcContext
from cylc.flow.task_job_logs import JOB_LOG_OUT, JOB_LOG_ERR


async def test_kill_error(one, start, test_dir, capsys, log_filter):
    """It should report the failure to kill a job."""
    async with start(one):
        # make it look like the task is running
        itask = one.pool.get_tasks()[0]
        itask.submit_num += 1
        itask.state_reset(TASK_STATUS_RUNNING)

        # fake job details
        workflow_job_log_dir = Path(get_workflow_run_job_dir(one.workflow))
        job_id = itask.tokens.duplicate(job='01').relative_id
        job_log_dir = Path(workflow_job_log_dir, job_id)

        # create job status file (give it a fake pid)
        job_log_dir.mkdir(parents=True)
        (job_log_dir / 'job.status').write_text(dedent('''
            CYLC_JOB_RUNNER_NAME=background
            CYLC_JOB_ID=99999999
            CYLC_JOB_PID=99999999
        '''))

        # attempt to kill the job using the jobs-kill script
        # (note this is normally run via a subprocess)
        capsys.readouterr()
        JobRunnerManager().jobs_kill(str(workflow_job_log_dir), [job_id])

        # the kill should fail, the failure should be written to stdout
        # (the jobs-kill callback will read this in and handle it)
        out, err = capsys.readouterr()
        assert re.search(
            # # NOTE: ESRCH = no such process
            rf'TASK JOB ERROR.*{job_id}.*Errno {errno.ESRCH}',
            out,
        )

        # feed this jobs-kill output into the scheduler
        # (as if we had run the jobs-kill script as a subprocess)
        one.task_job_mgr._kill_task_jobs_callback(
            # mock the subprocess
            SubProcContext(
                one.task_job_mgr.JOBS_KILL,
                ['mock-cmd'],
                # provide it with the out/err the script produced
                out=out,
                err=err,
            ),
            one.workflow,
            [itask],
        )

        # a warning should be logged
        assert log_filter(
            regex=r'1/one/01:running.*job kill failed',
            level=logging.WARNING,
        )
        assert itask.state(TASK_STATUS_RUNNING)


async def test_create_nn_new(one, start, test_dir, capsys, log_filter):
    """Test _create_nn. 

    It should create the NN symlink.
    """
    async with start(one):
        itask = one.pool.get_tasks()[0]

        workflow_job_log_dir = Path(get_workflow_run_job_dir(one.workflow))
        job_id = itask.tokens.duplicate(job='01').relative_id
        job_log_dir = Path(workflow_job_log_dir, job_id)
        job_log_dir.mkdir(parents=True)

        # call _create_nn
        JobRunnerManager()._create_nn(job_log_dir / 'job.out')

        # check the symlink exists
        assert (job_log_dir.parent / "NN").is_symlink()


async def test_create_nn_old(one, start, test_dir, capsys, log_filter):
    """Test _create_nn.

    It should remove existing job logs, if the dir already exists.
    """
    async with start(one):
        itask = one.pool.get_tasks()[0]

        # fake some old job logs
        workflow_job_log_dir = Path(get_workflow_run_job_dir(one.workflow))
        job_id = itask.tokens.duplicate(job='01').relative_id
        job_log_dir = Path(workflow_job_log_dir, job_id)
        job_log_dir.mkdir(parents=True)

        job_logs = []
        for name in JOB_LOG_OUT, JOB_LOG_ERR:
            job_logs.append(job_log_dir / name)

        # create the logs
        for job_log in job_logs:
            job_log.touch()

        # check they exist
        for job_log in job_logs:
            assert job_log.is_file()

        # call _create_nn
        for job_log in job_logs:
            JobRunnerManager()._create_nn(job_log)

        # check they were removed
        for job_log in job_logs:
            assert not job_log.is_file()
