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

"""cylc clean [OPTIONS] ARGS

Delete a stopped workflow.

Remove workflow files from the local scheduler filesystem and any remote hosts
the workflow was installed on.

NOTE: this command is intended for workflows installed with `cylc install`. If
this is run for a workflow that was instead written directly in ~/cylc-run and
not backed up elsewhere, it will be lost.

It will also remove any symlink directory targets.

Workflow names can be hierarchical, corresponding to the path under ~/cylc-run.

Examples:
  # Remove the workflow at ~/cylc-run/foo/bar
  $ cylc clean foo/bar

  # Remove multiple workflows
  $ cylc clean one two three

  # Remove the workflow's log directory
  $ cylc clean foo/bar --rm log

  # Remove the log and work directories
  $ cylc clean foo/bar --rm log:work
  # or
  $ cylc clean foo/bar --rm log --rm work

  # Remove all job log files from the 2020 cycle points
  $ cylc clean foo/bar --rm 'log/job/2020*'

  # Remove all .csv files
  $ cylc clean foo/bar --rm '**/*.csv'

  # Only remove the workflow on the local filesystem
  $ cylc clean foo/bar --local-only

  # Only remove the workflow on remote install targets
  $ cylc clean foo/bar --remote-only
"""

import asyncio
import sys
from typing import TYPE_CHECKING, Iterable, List, Tuple

from cylc.flow import LOG
from cylc.flow.exceptions import CylcError, InputError
import cylc.flow.flags
from cylc.flow.id_cli import parse_ids_async
from cylc.flow.loggingutil import set_timestamps
from cylc.flow.option_parsers import (
    WORKFLOW_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
    Options,
)
from cylc.flow.terminal import cli_function, is_terminal
from cylc.flow.workflow_files import init_clean, get_contained_workflows

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser():
    parser = COP(
        __doc__,
        multiworkflow=True,
        argdoc=[WORKFLOW_ID_MULTI_ARG_DOC],
        segregated_log=True,
    )

    parser.add_option(
        '--rm', metavar='DIR[:DIR:...]',
        help=("Only clean the specified subdirectories (or files) in the "
              "run directory, rather than the whole run directory. "
              "Accepts quoted globs."),
        action='append', dest='rm_dirs', default=[]
    )

    parser.add_option(
        '--local-only', '--local',
        help="Only clean on the local filesystem (not remote hosts).",
        action='store_true', dest='local_only'
    )

    parser.add_option(
        '--remote-only', '--remote',
        help="Only clean on remote hosts (not the local filesystem).",
        action='store_true', dest='remote_only'
    )

    parser.add_option(
        '--yes', '-y',
        help=(
            "Skip interactive prompt if trying to clean multiple "
            "run directories at once."
        ),
        action='store_true', dest='skip_interactive'
    )

    parser.add_option(
        '--timeout',
        help=("The number of seconds to wait for cleaning to take place on "
              "remote hosts before cancelling."),
        action='store', default='120', dest='remote_timeout'
    )

    return parser


CleanOptions = Options(get_option_parser())


def prompt(workflows: Iterable[str]) -> None:
    """Ask user if they want to clean the given set of workflows."""
    print("Would clean the following workflows:")
    for workflow in workflows:
        print(f'  {workflow}')

    if is_terminal():
        while True:
            ret = input('Remove these workflows (y/n): ')
            if ret.lower() == 'y':
                return
            if ret.lower() == 'n':
                sys.exit(1)
    else:
        print(
            "Use --yes to remove multiple workflows in non-interactive mode.",
            file=sys.stderr
        )
        sys.exit(1)


async def scan(
    workflows: Iterable[str], multi_mode: bool
) -> Tuple[List[str], bool]:
    """Expand tuncated workflow IDs

    For example "one" might expand to "one/run1" & "one/run2"
    or "one/two/run1".

    Returns (workflows, multi_mode)
    """
    ret = []
    for workflow in list(workflows):
        contained_flows = await get_contained_workflows(workflow)
        if contained_flows:
            ret.extend(contained_flows)
            multi_mode = True
        else:
            ret.append(workflow)
    return ret, multi_mode


async def run(*ids: str, opts: 'Values') -> None:
    # parse ids from the CLI
    workflows, multi_mode = await parse_ids_async(
        *ids,
        constraint='workflows',
        match_workflows=True,
        match_active=False,
        infer_latest_runs=False,  # don't infer latest runs like other cmds
    )

    # expand partial workflow ids (including run names)
    workflows, multi_mode = await scan(workflows, multi_mode)

    if not workflows:
        LOG.warning(f"No workflows matching {', '.join(ids)}")
        return

    workflows.sort()
    if multi_mode and not opts.skip_interactive:
        prompt(workflows)  # prompt for approval or exit

    failed = {}
    for workflow in sorted(workflows):
        try:
            init_clean(workflow, opts)
        except Exception as exc:
            failed[workflow] = exc
    if failed:
        msg = "Clean failed:"
        for workflow, exc_message in failed.items():
            msg += f"\nWorkflow: {workflow}\nError: {exc_message}"
        raise CylcError(msg)


@cli_function(get_option_parser)
def main(_, opts: 'Values', *ids: str):
    if cylc.flow.flags.verbosity < 2:
        set_timestamps(LOG, False)

    if opts.local_only and opts.remote_only:
        raise InputError(
            "--local and --remote options are mutually exclusive"
        )

    asyncio.run(run(*ids, opts=opts))
