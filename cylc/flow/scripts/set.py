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

"""cylc set [OPTIONS] ARGS

Command to manually set task prerequisites and outputs in running workflows.

By default, it sets all required outputs (including "submitted", "started" and
"succeeded" even if they are optional).

Setting task prerequisites:
  - contributes to the task's readiness to run, and
  - promotes it to the scheduler's active task pool

Format for prerequisite tasks: <cycle>/<task>[:output], or --pre=all
  - you cannot unsatisfy a task prerequisite

Note "--pre=all" promotes all tasks, including parentless tasks, to the active
task pool where the schedule can beging checking clock and xtriggers. Use this
instead of "trigger" to start a flow from tasks that first wait on xtriggers.

Format for prerequisite xtriggers: xtrigger/<label>[:(succeeded or waiting)
  - you can both set (succeeded, the default) and unset (waiting) xtriggers

Setting task outputs:
  - contributes to a task's completion, and
  - spawns downstream tasks that depend on those outputs

Note setting final outputs ("succeeded", "failed", "expired") also sets task
state. Setting the "started" and "submitted" outputs spawns downstream tasks
that depend on them but does not affect task state, because there is no
running job.

Implied outputs are set automatically:
  - "started" implies "submitted"
  - "succeeded" and "failed" imply "started"
  - custom outputs and "expired" do not imply other outputs

For custom outputs, use the output names not the associated task messages:
[runtime]
  [[my-task]]
    # ...
    [[[outputs]]]
      # <output-name> = <task-message>
      x = "file x completed and archived"

CLI Completion:
  Cylc can auto-complete prerequisites and outputs for active tasks if you
  specify the task in the command before attempting TAB-completion.

Examples:
  # complete all required outputs of 3/bar:
  $ cylc set my_workflow//3/bar
  #   or:
  $ cylc set --out=required my_workflow//3/bar

  # complete the succeeded output of 3/bar:
  $ cylc set --out=succeeded my_workflow//3/bar

  # complete the outputs defined in [runtime][task][skip]
  $ cylc set --out=skip my_workflow//3/bar

  # satisfy the 3/foo:succeeded prerequisite of 3/bar:
  $ cylc set --pre=3/foo my_workflow//3/bar
  #   or:
  $ cylc set --pre=3/foo:succeeded my_workflow//3/bar

  # satisfy all prerequisites (if any) of 3/bar and promote it to
  # the active window (and start checking its xtriggers, if any):
  $ cylc set --pre=all my_workflow//3/bar

  # satisfy the clock-trigger @clock1 of 3000/bar:
  $ cylc set --pre=xtrigger/clock1 my_worklfow//3000/bar
  #   or:
  $ cylc set --pre=xtrigger/clock1:succeeded my_worklfow//3000/bar

  # unsatisfy (to start checking again) the xtrigger @data of 3000/bar:
  $ cylc set --pre=xtrigger/data:waiting my_worklfow//3000/bar

  # complete the "file1" custom output of 3/bar:
  $ cylc set --out=file1 my_workflow//3/bar

  # satisfy the "3/bar:file1" prerequisite of 3/qux:
  $ cylc set --pre=3/bar:file1 my_workflow//3/qux

  # set multiple outputs at once:
  $ cylc set --out=a --out=b,c my_workflow//3/bar

  # set multiple prerequisites at once:
  $ cylc set --pre=3/foo:x --pre=3/foo:y,3/foo:z my_workflow//3/bar

"""

from functools import partial
import sys
from typing import Iterable, TYPE_CHECKING

from cylc.flow.exceptions import InputError
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    FULL_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import (
    cli_function,
    flatten_cli_lists
)
from cylc.flow.flow_mgr import add_flow_opts


if TYPE_CHECKING:
    from optparse import Values
    from cylc.flow.id import Tokens


MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
  $prerequisites: [PrerequisiteString],
  $outputs: [OutputLabel],
  $flow: [Flow!],
  $flowWait: Boolean,
  $flowDescr: String,
) {
  set (
    workflows: $wFlows,
    tasks: $tasks,
    prerequisites: $prerequisites,
    outputs: $outputs,
    flow: $flow,
    flowWait: $flowWait,
    flowDescr: $flowDescr
  ) {
    result
  }
}
'''


SELECTOR_ERROR = (
    'Use "--output={1}" to specify outputs, not "{0}:{1}"'
)


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        multitask=True,
        multiworkflow=True,
        argdoc=[FULL_ID_MULTI_ARG_DOC],
    )

    parser.add_option(
        "-o", "--out", "--output", metavar="OUTPUT(s)",
        help=(
            "Complete task outputs. For multiple outputs re-use the"
            " option, or give a comma-separated list of outputs."
            " Use '--out=required' to complete all required outputs."
            " Use '--out=skip' to complete outputs defined in the task's"
            " [skip] configuration."
            " OUTPUT format: trigger names as used in the graph."
        ),
        action="append", default=None, dest="outputs"
    )

    parser.add_option(
        "-p", "--pre", "--prerequisite", metavar="PREREQUISITE(s)",
        help=(
            "Satisfy task prerequisites. For multiple prerequisites"
            " re-use the option, or give a comma-separated list, or"
            ' use "--pre=all" to satisfy all prerequisites, if any.'
            " PREREQUISITE format: 'cycle/task[:OUTPUT]', where"
            " :OUTPUT defaults to :succeeded."
        ),
        action="append", default=None, dest="prerequisites"
    )

    add_flow_opts(parser)
    return parser


def validate_tokens(tokens_list: Iterable['Tokens']) -> None:
    """Check the cycles/tasks provided.

    This checks that cycle/task selectors have not been provided in the IDs.

    Examples:
        >>> from cylc.flow.id import Tokens

        Good:
        >>> validate_tokens([Tokens('w//c')])
        >>> validate_tokens([Tokens('w//c/t')])

        Bad:
        >>> validate_tokens([Tokens('w//c:s')])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...
        >>> validate_tokens([Tokens('w//c/t:s')])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...

    """
    for tokens in tokens_list:
        if tokens['cycle_sel']:
            raise InputError(SELECTOR_ERROR.format(
                tokens['cycle'],
                tokens['cycle_sel'],
            ))
        if tokens['task_sel']:
            raise InputError(SELECTOR_ERROR.format(
                tokens['task'],
                tokens['task_sel'],
            ))


async def run(
    options: 'Values',
    workflow_id: str,
    *tokens_list: 'Tokens'
):
    validate_tokens(tokens_list)

    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
            'tasks': [
                tokens.relative_id_with_selectors
                for tokens in tokens_list
            ],
            'outputs': flatten_cli_lists(options.outputs),
            'prerequisites': flatten_cli_lists(options.prerequisites),
            'flow': options.flow,
            'flowWait': options.flow_wait,
            'flowDescr': options.flow_descr
        }
    }

    return await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids) -> None:
    rets = call_multi(partial(run, options), *ids)
    sys.exit(all(rets.values()) is False)
