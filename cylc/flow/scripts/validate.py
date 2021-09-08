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

If the workflow definition uses include-files reported line numbers
will correspond to the inlined version seen by the parser; use
'cylc view -i,--inline WORKFLOW' for comparison."""

from ansimarkup import parse as cparse
from optparse import Values
import sys
import textwrap

from cylc.flow import LOG, __version__ as CYLC_VERSION
from cylc.flow.config import WorkflowConfig
from cylc.flow.exceptions import (
    WorkflowConfigError,
    TaskProxySequenceBoundsError,
    TriggerExpressionError
)
import cylc.flow.flags
from cylc.flow.loggingutil import disable_timestamps
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
    Options
)
from cylc.flow.profiler import Profiler
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.templatevars import get_template_vars
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import parse_reg


def get_option_parser():
    parser = COP(__doc__, jset=True, prep=True, icp=True)

    parser.add_option(
        "--check-circular",
        help="Check for circular dependencies in graphs when the number of "
             "tasks is greater than 100 (smaller graphs are always checked). "
             "This can be slow when the number of "
             "tasks is high.",
        action="store_true", default=False, dest="check_circular")

    parser.add_option(
        "--output", "-o",
        help="Specify a file name to dump the processed flow.cylc.",
        metavar="FILENAME", action="store", dest="output")

    parser.add_option(
        "--profile", help="Output profiling (performance) information",
        action="store_true", default=False, dest="profile_mode")

    parser.add_option(
        "-u", "--run-mode", help="Validate for run mode.", action="store",
        default="live", dest="run_mode",
        choices=['live', 'dummy', 'dummy-local', 'simulation'])

    parser.add_cylc_rose_options()

    parser.set_defaults(is_validate=True)

    return parser


ValidateOptions = Options(
    get_option_parser(),
    # defaults
    {
        'check_circular': False,
        'profile_mode': False,
        'run_mode': 'live'
    }
)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', reg: str) -> None:
    """cylc validate CLI."""
    profiler = Profiler(None, options.profile_mode)
    profiler.start()

    if cylc.flow.flags.verbosity < 2:
        disable_timestamps(LOG)

    workflow, flow_file = parse_reg(reg, src=True)
    cfg = WorkflowConfig(
        workflow,
        flow_file,
        options,
        get_template_vars(options, flow_file),
        output_fname=options.output,
        mem_log_func=profiler.log_memory
    )

    # Check bounds of sequences
    out_of_bounds = [str(seq) for seq in cfg.sequences
                     if seq.get_first_point(cfg.start_point) is None]
    if out_of_bounds:
        if len(out_of_bounds) > 1:
            # avoid spamming users with multiple warnings
            out_of_bounds_str = '\n'.join(
                textwrap.wrap(', '.join(out_of_bounds), 70))
            msg = (
                "multiple sequences out of bounds for initial cycle point "
                f"{cfg.start_point}:\n{out_of_bounds_str}")
        else:
            msg = (
                f"{out_of_bounds[0]}: sequence out of bounds for "
                f"initial cycle point {cfg.start_point}")
        LOG.warning(msg)

    # Instantiate tasks and force evaluation of trigger expressions.
    # (Taken from config.py to avoid circular import problems.)
    # TODO - This is not exhaustive, it only uses the initial cycle point.
    if cylc.flow.flags.verbosity > 0:
        print('Instantiating tasks to check trigger expressions')
    for name, taskdef in cfg.taskdefs.items():
        try:
            itask = TaskProxy(taskdef, cfg.start_point)
        except TaskProxySequenceBoundsError:
            # Should already failed above
            mesg = 'Task out of bounds for %s: %s\n' % (cfg.start_point, name)
            if cylc.flow.flags.verbosity > 0:
                sys.stderr.write(' + %s\n' % mesg)
            continue
        except Exception as exc:
            raise WorkflowConfigError(
                'failed to instantiate task %s: %s' % (name, exc))

        # force trigger evaluation now
        try:
            itask.state.prerequisites_eval_all()
        except TriggerExpressionError as exc:
            err = str(exc)
            if '@' in err:
                print(f"ERROR, {name}: xtriggers can't be in conditional"
                      f" expressions: {err}",
                      file=sys.stderr)
            else:
                print('ERROR, %s: bad trigger: %s' % (name, err),
                      file=sys.stderr)
            raise WorkflowConfigError("ERROR: bad trigger")
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            raise WorkflowConfigError(
                '%s: failed to evaluate triggers.' % name)
        if cylc.flow.flags.verbosity > 0:
            print('  + %s ok' % itask.identity)

    print(cparse('<green>Valid for cylc-%s</green>' % CYLC_VERSION))
    profiler.stop()
