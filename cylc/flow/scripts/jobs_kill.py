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
"""cylc jobs-kill [OPTIONS] ARGS

(This command is for internal use. Users should use "cylc kill".)

Read job status files to obtain the names of the job runners and the job IDs
in the runners. Invoke the relevant job runner commands to ask the job runners
to terminate the jobs.
"""

from cylc.flow.job_runner_mgr import JobRunnerManager
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function

INTERNAL = True


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[
            ("JOB-LOG-ROOT", "The log/job sub-directory for the workflow"),
            COP.optional(
                ("JOB-LOG-DIR ...", "A point/name/submit_num sub-directory")
            )
        ],
    )

    return parser


@cli_function(get_option_parser)
def main(parser, options, job_log_root, *job_log_dirs):
    """CLI main."""
    JobRunnerManager().jobs_kill(job_log_root, job_log_dirs)
