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

"""cylc trigger [OPTIONS] ARGS

Trigger tasks manually.

Triggered tasks get all current active flow numbers by default, so those flows
- if/when they catch up - will see the triggered tasks (and their children) as
having run already, 

Examples:
  # trigger task foo in cycle 1234 in test
  $ cylc trigger test//1234/foo

  # trigger all failed tasks in test
  $ cylc trigger 'test//*:failed'

  # start a new flow by triggering 1234/foo in test
  $ cylc trigger --flow=new test//1234/foo

Triggering a waiting task queues it to submit regardless of prerequisites.
If already queued, it will submit immediately regardless of the queue limit.
(You may need to trigger queue-limited tasks twice to run them immediately).

Triggering a submitted or running task has no effect (already triggered).

Tasks in the n=0 window already belong to a flow. Triggering active-waiting (or
incomplete) tasks queues them to run (or rerun) in their own flow.

Tasks triggered outside of n=0 get all active flow numbers by default. Use the
--flow option to change this.
"""

from functools import partial
from typing import TYPE_CHECKING

from cylc.flow.exceptions import UserInputError
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.flow_mgr import FLOW_NONE, FLOW_NEW, FLOW_ALL

if TYPE_CHECKING:
    from optparse import Values


ERR_OPT_FLOW_VAL = "Flow values must be integer, 'all', 'new', or 'none'"
ERR_OPT_FLOW_INT = "Multiple flow options must all be integer valued"
ERR_OPT_FLOW_META = "Metadata is only for new flows"


MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
  $flow: [String],
  $flowDescr: String,
) {
  trigger (
    workflows: $wFlows,
    tasks: $tasks,
    flow: $flow,
    flowDescr: $flowDescr
  ) {
    result
  }
}
'''


def get_option_parser():
    parser = COP(
        __doc__,
        comms=True,
        multitask=True,
        multiworkflow=True,
        argdoc=[('ID [ID ...]', 'Cycle/Family/Task ID(s)')],
    )

    parser.add_option(
        "--flow", action="append", dest="flow", metavar="FLOW",
        help=f"Assign the triggered task to all active flows ({FLOW_ALL});"
             f" no flow ({FLOW_NONE}); a new flow ({FLOW_NEW});"
             f" or a specific flow (e.g. 2). The default is {FLOW_ALL}."
             " Reuse the option to assign multiple specific flows."
    )

    parser.add_option(
        "--meta", metavar="DESCRIPTION", action="store",
        dest="flow_descr", default=None,
        help="description of triggered flow (with --flow=new) ."
    )

    return parser


def check_flow_options(opt_flow, opt_flow_descr):
    """Check validity of flow-related options.

    Examples:
        >>> check_flow_options([FLOW_ALL], None)

        >>> check_flow_options([FLOW_NEW], "Denial is a deep river")

        >>> check_flow_options([FLOW_ALL, "1"], None)
        Traceback (most recent call last):
            ...
        UserInputError: Multiple flow options must all be integer valued

        >>> check_flow_options([FLOW_ALL], "the quick brown fox")
        Traceback (most recent call last):
            ...
        UserInputError: Metadata is only for new flows

        >>> check_flow_options(["cheese"], None)
        Traceback (most recent call last):
            ...
        UserInputError: Flow values must be integer, 'all', 'new', or 'none'

    """
    for val in opt_flow:
        if val in [FLOW_NONE, FLOW_NEW, FLOW_ALL]:
            if len(opt_flow) != 1:
                raise UserInputError(ERR_OPT_FLOW_INT)
        else:
            try:
                int(val)
            except ValueError:
                raise UserInputError(ERR_OPT_FLOW_VAL.format(val))

    if opt_flow_descr and opt_flow != [FLOW_NEW]:
        raise UserInputError(ERR_OPT_FLOW_META)


async def run(options: 'Values', workflow_id: str, *tokens_list):
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
            'tasks': [
                tokens.relative_id
                for tokens in tokens_list
            ],
            'flow': options.flow,
            'flowDescr': options.flow_descr,
        }
    }

    await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids: str):
    """CLI for "cylc trigger"."""

    if options.flow is None:
        # Default to all active flows.
        options.flow = [FLOW_ALL]
    check_flow_options(options.flow, options.flow_descr)

    call_multi(
        partial(run, options),
        *ids,
    )
