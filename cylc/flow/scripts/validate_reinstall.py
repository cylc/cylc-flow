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

Validate, reinstall and apply changes to a workflow.

Validate and reinstall a workflow then either:

* "Reload" the workflow (if it is running),
* or "play" it (if it is stopped).

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

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from optparse import Values

from cylc.flow import LOG
from cylc.flow.exceptions import (
    ContactFileExists,
    CylcError,
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
from cylc.flow.scheduler_cli import PLAY_OPTIONS, scheduler_cli
from cylc.flow.scripts.validate import (
    VALIDATE_OPTIONS,
    run as cylc_validate,
)
from cylc.flow.scripts.reinstall import (
    REINSTALL_CYLC_ROSE_OPTIONS,
    REINSTALL_OPTIONS,
    reinstall_cli as cylc_reinstall,
)
from cylc.flow.scripts.reload import (
    run as cylc_reload
)
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import detect_old_contact_file

import asyncio

CYLC_ROSE_OPTIONS = COP.get_cylc_rose_options()
VR_OPTIONS = combine_options(
    VALIDATE_OPTIONS,
    REINSTALL_OPTIONS,
    REINSTALL_CYLC_ROSE_OPTIONS,
    PLAY_OPTIONS,
    CYLC_ROSE_OPTIONS,
    modify={'cylc-rose': 'validate, install'}
)


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        jset=True,
        argdoc=[WORKFLOW_ID_ARG_DOC],
    )
    for option in VR_OPTIONS:
        parser.add_option(*option.args, **option.kwargs)
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
    sys.exit(asyncio.run(vr_cli(parser, options, workflow_id)))


async def vr_cli(parser: COP, options: 'Values', workflow_id: str):
    """Run Cylc (re)validate - reinstall - reload in sequence."""
    # Attempt to work out whether the workflow is running.
    # We are trying to avoid reinstalling then subsequently being
    # unable to play or reload because we cannot identify workflow state.
    unparsed_wid = workflow_id
    workflow_id, *_ = await parse_id_async(
        workflow_id,
        constraint='workflows',
    )

    # Use this interface instead of scan, because it can have an ambiguous
    # outcome which we want to capture before we install.
    try:
        detect_old_contact_file(workflow_id)
    except ContactFileExists:
        # Workflow is definitely running:
        workflow_running = True
    except CylcError as exc:
        LOG.error(exc)
        LOG.critical(
            'Cannot tell if the workflow is running'
            '\nNote, Cylc 8 cannot restart Cylc 7 workflows.'
        )
        raise
    else:
        # Workflow is definitely stopped:
        workflow_running = False

    # options.tvars and tvars_file are _only_ valid when playing a stopped
    # workflow: Fail if they are set and workflow running:
    if not check_tvars_and_workflow_stopped(
        workflow_running, options.templatevars, options.templatevars_file
    ):
        return 1

    # Force on the against_source option:
    options.against_source = True   # Make validate check against source.
    log_subcommand('validate --against-source', workflow_id)
    await cylc_validate(parser, options, workflow_id)

    log_subcommand('reinstall', workflow_id)
    reinstall_ok = await cylc_reinstall(
        options, workflow_id,
        [],
        print_reload_tip=False
    )
    if not reinstall_ok:
        LOG.warning(
            'No changes to source: No reinstall or'
            f' {"reload" if workflow_running else "play"} required.'
        )
        return 1

    # Run reload if workflow is running or paused:
    if workflow_running:
        log_subcommand('reload', workflow_id)
        await cylc_reload(options, workflow_id)

    # run play anyway, to play a stopped workflow:
    else:
        set_timestamps(LOG, options.log_timestamp)
        cleanup_sysargv(
            'play',
            unparsed_wid,
            options,
            compound_script_opts=VR_OPTIONS,
            script_opts=(*PLAY_OPTIONS, *parser.get_std_options()),
            source='',  # Intentionally blank
        )
        log_subcommand(*sys.argv[1:])
        await scheduler_cli(options, workflow_id, parse_workflow_id=False)
