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

"""cylc validate-reinstall [OPTIONS] ARGS

Validate, reinstall, and reload or restart a workflow.

If there are source changes and the user chooses (via prompt) to reinstall, or
if there are no changes but the user chooses (via prompt) to continue anyway:
* reload the workflow, if it is running) (see `cylc reload`)
* or restart the workflow, if it is stopped (see `cylc play`)

If the command is not running interactively, it will automatically
reinstall and reload or restart if there are any source changes.

With --yes (skip prompts) the command will reinstall and reload or restart
regardless of source changes.

This command is equivalent to:
  $ cylc validate myworkflow --against-source
  $ cylc reinstall myworkflow
  # if myworkflow is running:
  $ cylc reload myworkflow
  # else:
  $ cylc play myworkflow

Note:
  "cylc validate --against-source" checks the code in the workflow source
  directory against any options (e.g. template variables) which have been set
  in the installed workflow to ensure the change can be safely applied.
"""

from ansimarkup import parse as cparse
import asyncio
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from optparse import Values

from cylc.flow import LOG
from cylc.flow.exceptions import (
    WorkflowStopped,
)
from cylc.flow.id_cli import parse_id_async
from cylc.flow.loggingutil import set_timestamps
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
    combine_options,
    log_subcommand,
    cleanup_sysargv
)
from cylc.flow.scheduler_cli import PLAY_OPTIONS, cylc_play
from cylc.flow.scripts.ping import run as cylc_ping
from cylc.flow.scripts.validate import (
    VALIDATE_OPTIONS,
    VALIDATE_AGAINST_SOURCE_OPTION,
    run as cylc_validate,
)
from cylc.flow.scripts.reinstall import (
    REINSTALL_CYLC_ROSE_OPTIONS,
    REINSTALL_OPTIONS,
    reinstall_cli as cylc_reinstall,
)
from cylc.flow.scripts.reload import (
    RELOAD_OPTIONS,
    run as cylc_reload
)
from cylc.flow.terminal import cli_function, is_terminal
from cylc.flow.workflow_files import get_workflow_run_dir


CYLC_ROSE_OPTIONS = COP.get_cylc_rose_options()
VR_OPTIONS = combine_options(
    VALIDATE_OPTIONS,
    REINSTALL_OPTIONS,
    REINSTALL_CYLC_ROSE_OPTIONS,
    RELOAD_OPTIONS,
    PLAY_OPTIONS,
    CYLC_ROSE_OPTIONS,
    modify={'cylc-rose': 'validate, install'}
)

_input = input  # to enable testing


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        jset=True,
        argdoc=[WORKFLOW_ID_ARG_DOC],
    )
    for option in VR_OPTIONS:
        parser.add_option(*option.args, **option.kwargs)
    parser.set_defaults(is_validate=True)

    return parser


def check_tvars_and_workflow_stopped(
    is_running: bool, tvars: list, tvars_file: list
) -> bool:
    """are template variables set and workflow stopped?

    Template vars set by --set (options.templatevars) or --set-file
    (optiions.templatevars_file) are only valid if the workflow is stopped
    and vr will play it.

    args:
        is_running: Is workflow running?
        tvars: options.tvars, from `--set`
        tvars_file: options.tvars_file, from `--set-file`
    """
    if is_running and (tvars or tvars_file):
        LOG.warning(
            'Template variables (from --set/--set-file) can '
            'only be changed if the workflow is stopped.'
        )
        return False
    return True


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow_id: str):
    ret = asyncio.run(vr_cli(parser, options, workflow_id))
    if isinstance(ret, str):
        # NOTE: cylc_play must be called from sync code (not async code)
        cylc_play(options, ret, parse_workflow_id=False)
    elif ret is False:
        sys.exit(1)


async def vr_cli(
    parser: COP, options: 'Values', workflow_id: str
) -> Union[bool, str]:
    """Validate and reinstall and optionally reload workflow.

    Runs:
    * Validate
    * Reinstall
    * Reload (if the workflow is already running)

    Returns:
        The workflow_id or a True/False outcome.

        workflow_id: If the workflow is stopped and requires restarting.
        True: If workflow is running and does not require restarting.
        False: If this command should "exit 1".

    """
    unparsed_wid = workflow_id
    workflow_id, *_ = await parse_id_async(
        workflow_id,
        constraint='workflows',
    )

    # First attempt to work out whether the workflow is running.
    # We are trying to avoid reinstalling then subsequently being
    # unable to play or reload because we cannot identify workflow state.
    log_subcommand('ping', workflow_id)
    try:
        result = await cylc_ping(options, workflow_id)
        # (don't catch CylcError: unable to determine if running or not)
    except WorkflowStopped:
        print(cparse(f"<green>{workflow_id} is not running</green>"))
        workflow_running = False
    else:
        print(cparse(f"<green>{workflow_id}: {result['stdout'][0]}</green>"))
        workflow_running = True

    # options.tvars and tvars_file are _only_ valid when playing a stopped
    # workflow: Fail if they are set and workflow running:
    if not check_tvars_and_workflow_stopped(
        workflow_running, options.templatevars, options.templatevars_file
    ):
        return False

    # Save the location of the existing workflow run dir in the
    # against source option:
    options.against_source = Path(get_workflow_run_dir(workflow_id))

    # Run "cylc validate"
    log_subcommand('validate --against-source', workflow_id)
    await cylc_validate(parser, options, workflow_id)

    # Unset options that do not apply after validation:
    delattr(options, 'against_source')
    delattr(options, 'is_validate')

    # Run "cylc reinstall"
    log_subcommand('reinstall', workflow_id)
    reinstall_ok = await cylc_reinstall(
        options,
        workflow_id,
        [],
        print_reload_tip=False
    )

    if not reinstall_ok:
        # No changes OR user said No to the reinstall prompt.

        # If not a terminal and not --yes do nothing.
        if not is_terminal() and not options.skip_interactive:
            return False

        # Else if not --yes, prompt user to continue or not.
        if not options.skip_interactive:
            usr = None
            if not workflow_running:
                # No changes to install, and the workflow is not running.
                # Can still restart with no changes.
                action = "Restart"
            else:
                # No changes to install, and the workflow is running.
                # Reload is probably pointless, but not necessarily (the user
                # could modify the run dir and do 'vr' to restart or reload).
                action = "Reload"
            while usr not in ['y', 'n']:
                usr = _input(
                    cparse(f'<bold>{action} anyway?</bold> [y/n]: ')
                ).lower()
                if usr == 'n':
                    return False

    # Run "cylc reload" (if workflow is running or paused)
    if workflow_running:
        log_subcommand('reload', workflow_id)
        await cylc_reload(options, workflow_id)
        return True

    # Run "cylc play" (if workflow is stopped)
    else:
        set_timestamps(LOG, options.log_timestamp)
        cleanup_sysargv(
            'play',
            unparsed_wid,
            options,
            compound_script_opts=[*VR_OPTIONS, VALIDATE_AGAINST_SOURCE_OPTION],
            script_opts=(*PLAY_OPTIONS, *parser.get_std_options()),
            source='',  # Intentionally blank
        )

        log_subcommand(*sys.argv[1:])
        return workflow_id
