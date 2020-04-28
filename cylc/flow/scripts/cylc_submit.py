#!/usr/bin/env python3

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

"""cylc [task] submit|single [OPTIONS] ARGS

Submit a single task to run just as it would be submitted by its suite.  Task
messaging commands will print to stdout but will not attempt to communicate
with the suite (which does not need to be running).

For tasks present in the suite graph the given cycle point is adjusted up to
the next valid cycle point for the task. For tasks defined under runtime but
not present in the graph, the given cycle point is assumed to be valid.

WARNING: do not 'cylc submit' a task that is running in its suite at the
same time - both instances will attempt to write to the same job logs."""

import sys
from cylc.flow.remote import remrun
if remrun():
    sys.exit(0)

from logging import WARNING
import os
from time import sleep

from cylc.flow import LOG
from cylc.flow.config import SuiteConfig
from cylc.flow.cycling.loader import get_point
from cylc.flow.exceptions import UserInputError
import cylc.flow.flags
from cylc.flow.subprocpool import SubProcPool
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.pathutil import make_suite_run_tree
from cylc.flow.suite_db_mgr import SuiteDatabaseManager
from cylc.flow.broadcast_mgr import BroadcastMgr
from cylc.flow.hostuserutil import get_user
from cylc.flow.job_pool import JobPool
from cylc.flow.resources import extract_resources
from cylc.flow.suite_files import get_suite_rc, get_suite_srv_dir
from cylc.flow.task_id import TaskID
from cylc.flow.task_job_mgr import TaskJobManager
from cylc.flow.task_events_mgr import TaskEventsManager
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_state import TASK_STATUS_SUBMIT_FAILED
from cylc.flow.templatevars import load_template_vars
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(
        __doc__, jset=True, icp=True,
        argdoc=[("REG", "Suite name"),
                ("TASK [...]", "Family or task ID (%s)" % TaskID.SYNTAX)])
    parser.set_defaults(sched=False, dry_run=False)
    parser.add_option(
        "-d", "--dry-run",
        help="Generate the job script for the task, but don't submit it.",
        action="store_true", dest="dry_run")

    return parser


class Schd:
    def __init__(self, suite, owner):
        self.suite = suite
        self.owner = owner
        self.config = None
        self.task_events_mgr = None


@cli_function(get_option_parser)
def main(parser, options, suite, *task_ids):
    """cylc submit CLI.

    No TASK EVENT HOOKS are set for the submit command because there is
    no scheduler instance watching for task failure etc.

    Note: a suite contact env file is not written by this command (it
    would overwrite the real one if the suite is running).
    """
    if not options.verbose and not options.debug:
        LOG.setLevel(WARNING)
    for task_id in task_ids:
        if not TaskID.is_valid_id(task_id):
            raise UserInputError("Invalid task ID %s" % task_id)
    suiterc = get_suite_rc(suite)
    suite_dir = os.path.dirname(suiterc)
    # For user-defined batch system handlers
    sys.path.append(os.path.join(suite_dir, 'python'))

    # Load suite config and tasks
    config = SuiteConfig(
        suite,
        suiterc,
        options,
        load_template_vars(options.templatevars, options.templatevars_file))
    itasks = []
    for task_id in task_ids:
        name_str, point_str = TaskID.split(task_id)
        taskdefs = config.find_taskdefs(name_str)
        if not taskdefs:
            raise UserInputError("No task found for %s" % task_id)
        for taskdef in taskdefs:
            itasks.append(TaskProxy(
                taskdef, get_point(point_str).standardise(), is_startup=True))

    # Initialise job submit environment
    make_suite_run_tree(suite)
    # Extract job.sh from library, for use in job scripts.
    extract_resources(
        get_suite_srv_dir(suite),
        ['etc/job.sh'])
    pool = SubProcPool()
    schd = Schd(suite, get_user())
    schd.config = config
    job_pool = JobPool(schd)
    db_mgr = SuiteDatabaseManager()
    schd.task_events_mgr = TaskEventsManager(
        suite,
        pool,
        db_mgr,
        BroadcastMgr(db_mgr),
        job_pool
    )
    task_job_mgr = TaskJobManager(
        suite,
        pool,
        db_mgr,
        schd.task_events_mgr,
        job_pool
    )
    task_job_mgr.task_remote_mgr.single_task_mode = True
    task_job_mgr.job_file_writer.set_suite_env({
        'CYLC_UTC': str(config.cfg['cylc']['UTC mode']),
        'CYLC_DEBUG': str(cylc.flow.flags.debug).lower(),
        'CYLC_VERBOSE': str(cylc.flow.flags.verbose).lower(),
        'CYLC_SUITE_NAME': suite,
        'CYLC_CYCLING_MODE': str(config.cfg['scheduling']['cycling mode']),
        'CYLC_SUITE_INITIAL_CYCLE_POINT': str(
            config.cfg['scheduling']['initial cycle point']),
        'CYLC_SUITE_FINAL_CYCLE_POINT': str(
            config.cfg['scheduling']['final cycle point']),
    })

    ret_code = 0
    waiting_tasks = list(itasks)
    if options.dry_run:
        while waiting_tasks:
            prep_tasks, bad_tasks = task_job_mgr.prep_submit_task_jobs(
                suite, waiting_tasks, dry_run=True)
            for itask in prep_tasks + bad_tasks:
                waiting_tasks.remove(itask)
            if waiting_tasks:
                task_job_mgr.proc_pool.process()
                sleep(1.0)

        for itask in itasks:
            if itask.local_job_file_path:
                print(('JOB SCRIPT=%s' % itask.local_job_file_path))
            else:
                print(('Unable to prepare job file for %s' % itask.identity),
                      file=sys.stderr)
                ret_code = 1
    else:
        while waiting_tasks:
            for itask in task_job_mgr.submit_task_jobs(suite, waiting_tasks):
                waiting_tasks.remove(itask)
            if waiting_tasks:
                task_job_mgr.proc_pool.process()
                sleep(1.0)
        while task_job_mgr.proc_pool.is_not_done():
            task_job_mgr.proc_pool.process()
        for itask in itasks:
            if itask.summary.get('submit_method_id') is not None:
                print(('[%s] Job ID: %s' % (
                    itask.identity, itask.summary['submit_method_id'])))
            if itask.state(TASK_STATUS_SUBMIT_FAILED):
                ret_code = 1
    sys.exit(ret_code)


if __name__ == "__main__":
    main()
