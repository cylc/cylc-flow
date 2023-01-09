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

Validate and reinstall a single workflow. Then if:
- Workflow running => reload.
- Workflow paused => resume.
- Workflow stopped => play.

This command is equivalent to:

    $ cylc validate myworkflow --against-source     # See note 1
    $ cylc reinstall myworkflow
    # if myworkflow is running:
    $ cylc reload myworkflow
    # else:
    $ cylc play myworkflow

Note 1:

Cylc validate myworkflow --against-source is equivalent of (without writing
any temporary files though):

    # Install from run directory
    $ cylc install ~/cylc-run/myworkflow -n temporary
    # Install from source directory over the top
    $ cylc install /path/to/myworkflow -n temporary
    # Validate combined config
    $ cylc validate ~/cylc-run/temporary
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from optparse import Values

from cylc.flow.exceptions import ServiceFileError
from cylc.flow.scheduler_cli import PLAY_OPTIONS, scheduler_cli
from cylc.flow.scripts.validate import (
    VALIDATE_OPTIONS,
    _main as cylc_validate
)
from cylc.flow.scripts.reinstall import (
    REINSTALL_CYLC_ROSE_OPTIONS, reinstall_cli as cylc_reinstall
)
from cylc.flow.scripts.reload import (
    reload_cli as cylc_reload
)
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
    combine_options,
    log_subcommand,
    cleanup_sysargv
)
from cylc.flow.id_cli import parse_id
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import detect_old_contact_file


CYLC_ROSE_OPTIONS = COP.get_cylc_rose_options()
VRO_OPTIONS = combine_options(
    VALIDATE_OPTIONS,
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
    for option in VRO_OPTIONS:
        parser.add_option(*option.args, **option.kwargs)
    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow_id: str):
    vro_cli(parser, options, workflow_id)


def vro_cli(parser: COP, options: 'Values', workflow_id: str):
    """Run Cylc (re)validate - reinstall - reload in sequence."""
    # Attempt to work out whether the workflow is running.
    # We are trying to avoid reinstalling then subsequently being
    # unable to play or reload because we cannot identify workflow state.
    workflow_id, *_ = parse_id(
        workflow_id,
        constraint='workflows',
    )

    # Use this interface instead of scan, because it can have an ambiguous
    # outcome which we want to capture before we install.
    try:
        detect_old_contact_file(workflow_id, quiet=True)
    except ServiceFileError:
        # Workflow is definately stopped:
        workflow_running = True
    else:
        # Workflow is definately running:
        workflow_running = False

    # Force on the against_source option:
    options.against_source = True   # Make validate check against source.
    log_subcommand('validate --against-source', workflow_id)
    cylc_validate(parser, options, workflow_id)

    log_subcommand('reinstall', workflow_id)
    reinstall_ok = cylc_reinstall(options, workflow_id)
    if not reinstall_ok:
        exit(0)

    # Run reload if workflow is running, else play:
    if workflow_running:
        log_subcommand('reload', workflow_id)
        cylc_reload(options, workflow_id)

    # run play anyway, to resume a paused workflow:
    else:
        cleanup_sysargv(
            'play',
            workflow_id,
            options,
            compound_script_opts=VRO_OPTIONS,
            script_opts=(
                PLAY_OPTIONS + CYLC_ROSE_OPTIONS
                + parser.get_std_options()
            ),
            source='',  # Intentionally blank
        )
        log_subcommand('play', workflow_id)
        scheduler_cli(options, workflow_id)
