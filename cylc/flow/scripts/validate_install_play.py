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

"""cylc validate-install-play [OPTIONS] ARGS

Validate install and play a single workflow.

This script is equivalent to:

    $ cylc validate /path/to/myworkflow
    $ cylc install /path/to/myworkflow
    $ cylc play myworkflow

"""

import sys

from cylc.flow.scripts.validate import (
    VALIDATE_OPTIONS,
    _main as validate_main
)
from cylc.flow.scripts.install import (
    INSTALL_OPTIONS, install_cli as cylc_install, get_source_location
)
from cylc.flow import LOG
from cylc.flow.scheduler_cli import PLAY_OPTIONS
from cylc.flow.loggingutil import set_timestamps
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
    combine_options,
    cleanup_sysargv,
    log_subcommand,
)
from cylc.flow.scheduler_cli import _play
from cylc.flow.terminal import cli_function

from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from optparse import Values


CYLC_ROSE_OPTIONS = COP.get_cylc_rose_options()
VIP_OPTIONS = combine_options(
    VALIDATE_OPTIONS,
    INSTALL_OPTIONS,
    PLAY_OPTIONS,
    CYLC_ROSE_OPTIONS,
    modify={'cylc-rose': 'validate, install'}
)


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        jset=True,
        argdoc=[
            COP.optional((
                'SOURCE_NAME | PATH',
                'Workflow source name or path to source directory'
            ))
        ]
    )
    for option in VIP_OPTIONS:
        # Make a special exception for option against_source which makes
        # no sense in a VIP context.
        if option.kwargs.get('dest') != 'against_source':
            parser.add_option(*option.args, **option.kwargs)

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow_id: Optional[str] = None):
    """Run Cylc validate - install - play in sequence."""
    if not workflow_id:
        workflow_id = '.'
    orig_source = workflow_id
    source = get_source_location(workflow_id)
    log_subcommand('validate', source)
    validate_main(parser, options, str(source))

    log_subcommand('install', source)
    _, workflow_id = cylc_install(options, workflow_id)

    cleanup_sysargv(
        'play',
        workflow_id,
        options,
        compound_script_opts=VIP_OPTIONS,
        script_opts=(*PLAY_OPTIONS, *parser.get_std_options()),
        source=orig_source,
    )

    set_timestamps(LOG, options.log_timestamp)
    log_subcommand(*sys.argv[1:])
    _play(parser, options, workflow_id)
