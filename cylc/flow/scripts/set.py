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

By default, it sets all required outputs (note "succeeded" may be optional).

Setting task prerequisites:
  - contributes to the task's readiness to run, and
  - promotes it to the scheduler's active task pool

Note --pre=all also promotes parentless tasks (with no task-prerequisites) to
the active pool where clock and xtriggers become active. This is needed to
start a new flow that continues to future cycle points, if you need the first
parentless tasks in the new flow to wait on clock or xtriggers before running.

Setting task outputs:
  - contributes to a task's completion, and
  - spawns downstream tasks that depend on those outputs

Note setting final outputs (succeeded, failed, expired) also sets task state.
Setting the started and submitted outputs spawns downstream tasks that depend
on them but does not affect task state, because there is no running job.

Implied outputs are set automatically:
  - started implies submitted
  - succeeded and failed imply started
  - custom outputs and expired do not imply other outputs

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

  # satisfy the 3/foo:succeeded prerequisite of 3/bar:
  $ cylc set --pre=3/foo my_workflow//3/bar
  #   or:
  $ cylc set --pre=3/foo:succeeded my_workflow//3/bar

  # satisfy all prerequisites (if any) of 3/bar and promote it to
  # the active window (and start checking its xtriggers, if any):
  $ cylc set --pre=all my_workflow//3/bar

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
from typing import TYPE_CHECKING, List, Optional

from cylc.flow.exceptions import InputError
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    FULL_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.id import Tokens
from cylc.flow.task_outputs import TASK_OUTPUT_SUCCEEDED
from cylc.flow.terminal import cli_function
from cylc.flow.flow_mgr import (
    add_flow_opts,
    validate_flow_opts
)


if TYPE_CHECKING:
    from optparse import Values


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
            " option, or give a comma-separated list of outputs, or"
            ' use "--out=required" to complete all required outputs.'
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


def validate_prereq(prereq: str) -> Optional[str]:
    """Return prereq (with :succeeded) if valid, else None.

    Format: cycle/task[:output]

    Examples:
        >>> validate_prereq('1/foo:succeeded')
        '1/foo:succeeded'

        >>> validate_prereq('1/foo')
        '1/foo:succeeded'

        >>> validate_prereq('all')
        'all'

        # Error:
        >>> validate_prereq('fish')

    """
    try:
        tokens = Tokens(prereq, relative=True)
    except ValueError:
        return None
    if (
        tokens["cycle"] == prereq
        and prereq != "all"
    ):
        # Error: --pre=<word> other than "all"
        return None

    if prereq != "all" and tokens["task_sel"] is None:
        prereq += f":{TASK_OUTPUT_SUCCEEDED}"

    return prereq


def split_opts(options: List[str]):
    """Return list from multi-use and comma-separated options.

    Examples:
        # --out='a,b,c'
        >>> split_opts(['a,b,c'])
        ['a', 'b', 'c']

        # --out='a' --out='a,b'
        >>> split_opts(['a', 'b,c'])
        ['a', 'b', 'c']

        # --out='a' --out='a,b'
        >>> split_opts(['a', 'a,b'])
        ['a', 'b']

        # --out='  a '
        >>> split_opts(['  a  '])
        ['a']

        # --out='a, b, c , d'
        >>> split_opts(['a, b, c , d'])
        ['a', 'b', 'c', 'd']

    """
    return sorted({
        item.strip()
        for option in (options or [])
        for item in option.strip().split(',')
    })


def get_prereq_opts(prereq_options: List[str]):
    """Convert prerequisites to a flat list with output selectors.

    Examples:
        # Set multiple at once:
        >>> get_prereq_opts(['1/foo:bar', '2/foo:baz,3/foo:qux'])
        ['1/foo:bar', '2/foo:baz', '3/foo:qux']

        # --pre=all
        >>> get_prereq_opts(["all"])
        ['all']

        # implicit ":succeeded"
        >>> get_prereq_opts(["1/foo"])
        ['1/foo:succeeded']

        # Error: invalid format:
        >>> get_prereq_opts(["fish"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...

        # Error: invalid format:
        >>> get_prereq_opts(["1/foo::bar"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...

        # Error: "all" must be used alone:
        >>> get_prereq_opts(["all", "2/foo:baz"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...

     """
    prereqs = split_opts(prereq_options)
    if not prereqs:
        return []

    prereqs2 = []
    bad: List[str] = []
    for pre in prereqs:
        p = validate_prereq(pre)
        if p is not None:
            prereqs2.append(p)
        else:
            bad.append(pre)
    if bad:
        raise InputError(
            "Use prerequisite format <cycle-point>/<task>:output\n"
            "\n  ".join(bad)
        )

    if len(prereqs2) > 1:  # noqa SIM102 (anticipates "cylc set --pre=cycle")
        if "all" in prereqs:
            raise InputError("--pre=all must be used alone")

    return prereqs2


def get_output_opts(output_options: List[str]):
    """Convert outputs options to a flat list, and validate.

    Examples:
        Good:
        >>> get_output_opts(['a', 'b,c'])
        ['a', 'b', 'c']
        >>> get_output_opts(["required"])  # "required" is explicit default
        []

        Bad:
        >>> get_output_opts(["required", "a"])  # "required" must be used alone
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: --out=required must be used alone
        >>> get_output_opts(["waiting"])  # cannot "reset" to waiting
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: Tasks cannot be set to waiting...

    """
    outputs = split_opts(output_options)

    # If "required" is explicit just ditch it (same as the default)
    if not outputs or outputs == ["required"]:
        return []

    if "required" in outputs:
        raise InputError("--out=required must be used alone")
    if "waiting" in outputs:
        raise InputError(
            "Tasks cannot be set to waiting, use a new flow to re-run"
        )

    return outputs


def validate_opts(output_opt: List[str], prereq_opt: List[str]):
    """Check global option consistency

    Examples:
        >>> validate_opts(["a"], None)  # OK

        >>> validate_opts(None, ["1/a:failed"])  #OK

        >>> validate_opts(["a"], ["1/a:failed"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...

    """
    if output_opt and prereq_opt:
        raise InputError("Use --prerequisite or --output, not both.")


def validate_tokens(tokens_list):
    """Check the cycles/tasks provided.

    This checks that cycle/task selectors have not been provided in the IDs.

    Examples:
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
    *tokens_list
) -> None:
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
            'outputs': get_output_opts(options.outputs),
            'prerequisites': get_prereq_opts(options.prerequisites),
            'flow': options.flow,
            'flowWait': options.flow_wait,
            'flowDescr': options.flow_descr
        }
    }

    await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids) -> None:
    validate_opts(options.outputs, options.prerequisites)
    validate_flow_opts(options)
    call_multi(
        partial(run, options),
        *ids,
    )
