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

"""cylc validate [OPTIONS] ARGS

Validate a workflow configuration.

If the workflow definition uses include-files, reported line numbers will
correspond to the inlined version seen by the parser;
use 'cylc view -i,--inline WORKFLOW' for comparison.
"""

import asyncio
from ansimarkup import parse as cparse
from copy import deepcopy
import sys
from typing import TYPE_CHECKING

from cylc.flow import LOG, __version__ as CYLC_VERSION
from cylc.flow.config import WorkflowConfig
from cylc.flow.exceptions import (
    WorkflowConfigError,
    TaskProxySequenceBoundsError,
    TriggerExpressionError
)
import cylc.flow.flags
from cylc.flow.id import Tokens
from cylc.flow.id_cli import parse_id_async
from cylc.flow.loggingutil import set_timestamps
from cylc.flow.option_parsers import (
    AGAINST_SOURCE_OPTION,
    WORKFLOW_ID_OR_PATH_ARG_DOC,
    CylcOptionParser as COP,
    OptionSettings,
    Options,
    ICP_OPTION,
)
from cylc.flow.profiler import Profiler
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.templatevars import get_template_vars
from cylc.flow.terminal import cli_function
from cylc.flow.run_modes import RunMode

if TYPE_CHECKING:
    from cylc.flow.option_parsers import Values


VALIDATE_ICP_OPTION = deepcopy(ICP_OPTION)
VALIDATE_ICP_OPTION.sources = {'validate'}
VALIDATE_AGAINST_SOURCE_OPTION = deepcopy(AGAINST_SOURCE_OPTION)
VALIDATE_AGAINST_SOURCE_OPTION.sources = {'validate'}


VALIDATE_OPTIONS = [
    OptionSettings(
        ["--check-circular"],
        help=(
            "Check for circular dependencies in graphs when the number of"
            " tasks is greater than 100 (smaller graphs are always"
            " checked). This can be slow when the number of"
            " tasks is high."),
        action="store_true",
        default=False,
        dest="check_circular",
        sources={'validate'}
    ),
    OptionSettings(
        ["--output", "-o"],
        help="Specify a file name to dump the processed flow.cylc.",
        metavar="FILENAME",
        action="store",
        dest="output",
        sources={'validate'}
    ),
    OptionSettings(
        ["--profile"],
        help="Output profiling (performance) information",
        action="store_true",
        default=False,
        dest="profile_mode",
        sources={'validate'}
    ),
    VALIDATE_ICP_OPTION,
]


def get_option_parser():
    parser = COP(
        __doc__,
        jset=True,
        argdoc=[WORKFLOW_ID_OR_PATH_ARG_DOC],
    )

    for option in [
        *parser.get_cylc_rose_options(),
        *VALIDATE_OPTIONS,
        VALIDATE_AGAINST_SOURCE_OPTION,
    ]:
        parser.add_option(*option.args, **option.kwargs)

    parser.set_defaults(is_validate=True)

    return parser


ValidateOptions = Options(
    get_option_parser(),
    # defaults
    {
        'check_circular': False,
        'profile_mode': False,
        'run_mode': RunMode.LIVE.value
    }
)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow_id: str) -> None:
    asyncio.run(run(parser, options, workflow_id))


async def run(
    parser: COP, options: 'Values', workflow_id: str
) -> None:
    """cylc validate CLI."""
    profiler = Profiler(None, options.profile_mode)
    profiler.start()

    if cylc.flow.flags.verbosity < 2:
        set_timestamps(LOG, False)

    workflow_id, _, flow_file = await parse_id_async(
        workflow_id,
        src=True,
        constraint='workflows',
    )
    cfg = WorkflowConfig(
        workflow_id,
        flow_file,
        options,
        get_template_vars(options),
        output_fname=options.output,
        mem_log_func=profiler.log_memory
    )

    # Instantiate tasks and force evaluation of trigger expressions.
    # (Taken from config.py to avoid circular import problems.)
    # TODO - This is not exhaustive, it only uses the initial cycle point.
    if cylc.flow.flags.verbosity > 0:
        print('Instantiating tasks to check trigger expressions')
    for name, taskdef in cfg.taskdefs.items():
        try:
            itask = TaskProxy(
                Tokens(workflow_id),
                taskdef,
                cfg.start_point,
            )
        except TaskProxySequenceBoundsError:
            # Should already failed above
            mesg = 'Task out of bounds for %s: %s\n' % (cfg.start_point, name)
            if cylc.flow.flags.verbosity > 0:
                sys.stderr.write(' + %s\n' % mesg)
            continue
        except Exception as exc:
            raise WorkflowConfigError(
                'failed to instantiate task %s: %s' % (name, exc)
            ) from None

        # force trigger evaluation now
        try:
            itask.state.prerequisites_eval_all()
        except TriggerExpressionError as exc:
            err = str(exc)
            if '@' in err:
                print(
                    f"ERROR, {name}: xtriggers can't be in conditional"
                    f" expressions: {err}",
                    file=sys.stderr,
                )
            else:
                print(
                    'ERROR, %s: bad trigger: %s' % (name, err), file=sys.stderr
                )
            raise WorkflowConfigError("ERROR: bad trigger") from None
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            raise WorkflowConfigError(
                '%s: failed to evaluate triggers.' % name
            ) from None
        if cylc.flow.flags.verbosity > 0:
            print('  + %s ok' % itask.identity)

    print(cparse('<green>Valid for cylc-%s</green>' % CYLC_VERSION))
    profiler.stop()
