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

Manually set task prerequisites or outputs in a running workflow.

Default: set all required outputs (note "succeeded" can be optional).

Prerequitistes:
  Setting prerequisites contributes to a task's readiness and promotes it
  to the scheduler's active window, where clock and xtriggers become active.

Outputs:
  Setting outputs affects task completion and spawns dependent tasks.

  Some implied outputs may be set automatically:
    - started implies submitted
    - succeeded and failed imply started
    - custom outputs and expired do not imply other outputs

  Setting final outputs (succeeded, failed, expired) also sets task state.

  WARNING: setting a task's "expired" output, like clock-expire, means the
  workflow can successfully complete without running the task and any
  (non-expire) sub-graph that depends onit. This is dangerous, so potential
  expiry must be flagged in the graph with "<task>:expire?", for visibility.
  If you expire an active task its job will be killed.

CLI Completion:
  Cylc can auto-complete prerequisites and outputs for active tasks if you
  specify the task in the command before attempting TAB-completion.

Examples:
  # complete all required outputs of 3/bar:
  $ cylc set my_workflow//3/bar

  # complete the succeeded output of 3/bar:
  $ cylc set --out=succeeded my_workflow//3/bar

  # satisfy the `3/foo:succeeded` prerequisite of 3/bar:
  $ cylc set --pre=3/foo my_workflow//3/bar
  #   or:
  $ cylc set --pre=3/foo:succeeded my_workflow//3/bar

  # satisfy all prerequisites of 3/bar and start checking its xtriggers:
  $ cylc set --pre=all my_workflow//3/bar

  # complete the ":file1" custom output of 3/bar:
  $ cylc set --out=file1 my_workflow//3/bar
  # or use the associated output message from the task definition:
  $ cylc set --out="file 1 ready" my_workflow//3/bar

  # set multiple outputs at once:
  $ cylc set --out=a --out=b,c my_workflow//3/bar

  # set multiple prerequisites at once:
  $ cylc set --pre=3/foo:x --pre=3/foo:y,3/foo:z my_workflow//3/bar
"""

from functools import partial
from typing import TYPE_CHECKING, List

from cylc.flow.exceptions import InputError
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    FULL_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.id import Tokens
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
  $prerequisites: [String],
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
            "Set task outputs complete, along with any implied outputs."
            " Specify OUTPUT labels (as used in the graph) or associated"
            " messages. Multiple use allowed, items may be comma separated."
        ),
        action="append", default=None, dest="outputs"
    )

    parser.add_option(
        "-p", "--pre", "--prerequisite", metavar="PREREQUISITE(s)",
        help=(
            "Set task prerequisites satisfied."
            " PREREQUISITE format: 'point/task:message'."
            " Multiple use allowed, items may be comma separated."
            " Use 'all' to satisfy all prerequisites, if any."
        ),
        action="append", default=None, dest="prerequisites"
    )

    add_flow_opts(parser)
    return parser


def validate_prereq(prereq: str) -> bool:
    """Return True if prereq is valid, else False.

    Examples:
        >>> validate_prereq('1/foo:succeeded')
        True

        >>> validate_prereq('1/foo::succeeded')
        False

        >>> validate_prereq('all')
        True

        >>> validate_prereq('fish')
        False

    """
    try:
        tokens = Tokens(prereq, relative=True)
    except ValueError:
        return False
    if (
        tokens["cycle"] == prereq
        and prereq not in ["all"]
    ):
        # Error: --pre=<word> other than "all"
        return False
    return True


def split_opts(options: List[str]):
    """Return list from multi-use and comma-separated single-use options.

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

    """
    if options is None:
        return []
    splat = []  # (past tense of split)
    for p in options:
        splat += p.split(',')
    return sorted(set(splat))


def get_prerequisite_opts(prereq_options: List[str]):
    """Validate prerequisite inputs and return them as a flat list.

    Examples:
        >>> get_prerequisite_opts(['1/foo:bar', '2/foo:baz,3/foo:qux'])
        ['1/foo:bar', '2/foo:baz', '3/foo:qux']

        >>> get_prerequisite_opts(['all'])
        ['all']

        >>> get_prerequisite_opts(['fish'])
        Traceback (most recent call last):
        ...
        InputError:

        >>> get_prerequisite_opts(['all', '2/foo:baz'])
        Traceback (most recent call last):
        ...
        InputError:

        >>> get_prerequisite_opts(['1/foo::bar'])
        Traceback (most recent call last):
        ...
        InputError:

     """
    prereqs = split_opts(prereq_options)
    if not prereqs:
        return []

    msg = '\n'.join(
        [
            p for p in prereqs
            if not validate_prereq(p)
        ]
    )
    if msg:
        raise InputError(f"Invalid prerequisite(s):\n{msg}")

    if len(prereqs) > 1:  # noqa SIM102 (anticipates "cylc set --pre=cycle")
        if "all" in prereqs:
            raise InputError("--pre=all must be used alone")

    return prereqs


def get_output_opts(output_options: List[str]):
    """Convert outputs options to a single list, and validate.

    Examples:
        >>> get_output_opts(['a', 'b,c'])
        ['a', 'b', 'c']

    """
    # (No current validation)
    return split_opts(output_options)


async def run(
    options: 'Values',
    workflow_id: str,
    *tokens_list
) -> None:

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
            'prerequisites': get_prerequisite_opts(options.prerequisites),
            'flow': options.flow,
            'flowWait': options.flow_wait,
            'flowDescr': options.flow_descr
        }
    }

    await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids) -> None:
    if options.outputs and options.prerequisites:
        raise InputError("Use --prerequisite or --output, not both.")
    validate_flow_opts(options)
    call_multi(
        partial(run, options),
        *ids,
    )
