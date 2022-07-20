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
"""cylc jobs-submit [OPTIONS] ARGS

(This command is for internal use.)

Submit task jobs to relevant job runners.
On a remote job host, this command reads the job files from STDIN.
"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.job_runner_mgr import JobRunnerManager

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
    parser.add_option(
        "--remote-mode",
        help="Is this being run on a remote job host?",
        action="store_true",
        dest="remote_mode",
        default=False,
    )
    parser.add_option(
        "--utc-mode",
        help="(for remote mode) is the workflow running in UTC mode?",
        action="store_true",
        dest="utc_mode",
        default=False,
    )
    parser.add_option(
        "--clean-env",
        help="Clean job submission environment.",
        action="store_true",
        dest="clean_env",
        default=False,
    )
    parser.add_option(
        "--env",
        help="Variable to pass from parent environment to job submit "
        "environment. This option can be used multiple times.",
        action="append",
        metavar="VAR=VALUE",
        dest="env",
        default=[]
    )
    parser.add_option(
        "--path",
        help="Executable location to pass to job submit environment. "
        "This option can be used multiple times.",
        action="append",
        metavar="PATH",
        dest="path",
        default=[]
    )
    return parser


@cli_function(get_option_parser)
def main(parser, opts, job_log_root, *job_log_dirs):
    """CLI main."""
    JobRunnerManager(opts.clean_env, opts.env, opts.path).jobs_submit(
        job_log_root,
        job_log_dirs,
        remote_mode=opts.remote_mode,
        utc_mode=opts.utc_mode,
    )
