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

"""cylc [control] trigger [OPTIONS] ARGS

Manually trigger tasks.
  cylc trigger REG - trigger all tasks in a running workflow
  cylc trigger REG TASK_GLOB ... - trigger some tasks in a running workflow

NOTE waiting tasks that are queue-limited will be queued if triggered, to
submit as normal when released by the queue; queued tasks will submit
immediately if triggered, even if that violates the queue limit (so you may
need to trigger a queue-limited task twice to get it to submit immediately).

"""

import re
import os
import time
import shutil
import difflib
from subprocess import call

from cylc.flow.exceptions import CylcError, UserInputError
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.task_job_logs import JOB_LOG_DIFF
from cylc.flow.terminal import prompt, cli_function


def get_option_parser():
    parser = COP(
        __doc__, comms=True, multitask_nocycles=True,
        argdoc=[
            ('REG', 'Suite name'),
            ('[TASK_GLOB ...]', 'Task matching patterns')])

    parser.add_option(
        "-r", "--reflow",
        help="Start a new flow from the triggered task.",
        action="store_true", default=False, dest="reflow")

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite, *task_globs):
    """CLI for "cylc trigger"."""
    msg = 'Trigger task(s) %s in %s' % (task_globs, suite)
    prompt(msg, options.force)

    pclient = SuiteRuntimeClient(suite, timeout=options.comms_timeout)

    pclient(
        'force_trigger_tasks',
        {
            'tasks': task_globs,
            'reflow': options.reflow
        }
    )


if __name__ == "__main__":
    main()
